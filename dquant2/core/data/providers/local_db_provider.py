"""本地 SQLite 数据库数据提供者

直接读取本地 quant.db 数据库，无需网络请求，适合快速回测。

数据库表结构来自 data/db/db_init.sql：
  - daily:       日线行情 (ts_code, trade_date, open, high, low, close, vol, amount)
  - adj_factor:  复权因子 (ts_code, trade_date, adj_factor)
  - trade_cal:   交易日历 (exchange, cal_date, is_open)
  - stock_basic: 股票基础信息 (ts_code, symbol, name, ...)
  - daily_basic: 每日指标 (ts_code, trade_date, pe, pb, ...)
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict

import pandas as pd

from dquant2.core.data.interface import BaseDataProvider

logger = logging.getLogger(__name__)

# Default database path (resolved relative to this file's location):
# local_db_provider.py lives at:  <project>/dquant2/core/data/providers/
# quant.db lives at:              <project>/data/db/quant.db
# So we need to go up 4 levels:   providers/ -> data/ -> core/ -> dquant2/ -> <project>/
_PROVIDERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_PROVIDERS_DIR, '..', '..', '..', '..'))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, 'data', 'db', 'quant.db')


class LocalDBProvider(BaseDataProvider):
    """本地 SQLite 数据库数据提供者

    直接查询 quant.db，支持前复权（qfq），带内存缓存加速。
    股票代码同时兼容 '000001' 和 '000001.SZ' 两种格式。
    """

    def __init__(self, db_path: Optional[str] = None):
        super().__init__(name="local_db")
        self.db_path = db_path or _DEFAULT_DB_PATH
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"本地数据库文件不存在: {self.db_path}\n"
                "请确认 data/db/quant.db 已放置在项目中。"
            )
        logger.info(f"LocalDBProvider 已连接: {self.db_path}")

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        """创建只读连接"""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _normalize_ts_code(symbol: str) -> str:
        """将 '000001' 或 '000001.SZ'/'600000.SH' 统一为 ts_code 格式 'XXXXXX.XX'"""
        if '.' in symbol:
            return symbol.upper()
        # 根据开头数字推断市场
        if symbol.startswith('6'):
            return f"{symbol}.SH"
        else:
            return f"{symbol}.SZ"

    @staticmethod
    def _extract_pure_code(symbol: str) -> str:
        """提取纯数字代码，如 '000001.SZ' -> '000001'"""
        return symbol.split('.')[0]

    # ------------------------------------------------------------------ #
    # IDataProvider interface
    # ------------------------------------------------------------------ #

    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """获取前复权 K 线数据

        Args:
            symbol: 股票代码，支持 '000001' 和 '000001.SZ' 两种格式
            start:  开始日期 YYYYMMDD
            end:    结束日期 YYYYMMDD
            freq:   频率，目前仅支持日线 'd'

        Returns:
            DataFrame，index 为 datetime，列为 open/high/low/close/volume
        """
        if freq != 'd':
            logger.warning(f"LocalDBProvider 暂只支持日线数据，忽略 freq={freq}")

        # 检查缓存
        cache_key = self._get_cache_key(symbol, start, end, freq)
        cached = self._use_cache(cache_key)
        if cached is not None:
            return cached

        ts_code = self._normalize_ts_code(symbol)
        start_int = int(start)
        end_int = int(end)

        sql_daily = """
            SELECT d.trade_date, d.open, d.high, d.low, d.close, d.vol AS volume, d.amount,
                   db.turnover_rate AS turnover,
                   db.pe_ttm AS peTTM,
                   db.pb AS pbMRQ,
                   db.total_mv,
                   db.circ_mv
            FROM daily d
            LEFT JOIN daily_basic db ON d.ts_code = db.ts_code AND d.trade_date = db.trade_date
            WHERE d.ts_code = ?
              AND d.trade_date BETWEEN ? AND ?
            ORDER BY d.trade_date ASC
        """

        sql_adj = """
            SELECT trade_date, adj_factor
            FROM adj_factor
            WHERE ts_code = ?
              AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
        """

        try:
            with self._connect() as conn:
                df = pd.read_sql_query(
                    sql_daily,
                    conn,
                    params=(ts_code, start_int, end_int),
                )

                if df.empty:
                    logger.warning(f"LocalDB: {ts_code} [{start}, {end}] 无行情数据")
                    return pd.DataFrame()

                adj_df = pd.read_sql_query(
                    sql_adj,
                    conn,
                    params=(ts_code, start_int, end_int),
                )

            # 数值转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'turnover', 'peTTM', 'pbMRQ']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 前复权：adj_factor_i / adj_factor_latest
            if not adj_df.empty:
                adj_df['adj_factor'] = pd.to_numeric(adj_df['adj_factor'], errors='coerce')
                latest_adj = adj_df['adj_factor'].iloc[-1]
                adj_map: Dict[int, float] = dict(
                    zip(adj_df['trade_date'], adj_df['adj_factor'])
                )
                def apply_adj(row):
                    af = adj_map.get(int(row['trade_date']), latest_adj)
                    ratio = af / latest_adj if latest_adj else 1.0
                    return ratio

                ratios = df.apply(apply_adj, axis=1)
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = (df[col] * ratios).round(4)

            # 设置日期索引
            df['date'] = pd.to_datetime(df['trade_date'].astype(str), format='%Y%m%d')
            df.set_index('date', inplace=True)
            
            # 保留因子列
            keep_cols = ['open', 'high', 'low', 'close', 'volume', 'turnover', 'peTTM', 'pbMRQ']
            # 只选取存在的列，以防有些列没有查询出来
            keep_cols = [c for c in keep_cols if c in df.columns]
            df = df[keep_cols].copy()
            
            # 由于停牌或没有基本面的日期可能为NaN，只删除OHLCV是NaN的行
            df.dropna(subset=['open', 'high', 'low', 'close', 'volume'], inplace=True)

            self._set_cache(cache_key, df)
            logger.info(f"LocalDB: 加载 {ts_code} {start}-{end} 共 {len(df)} 条")
            return df

        except Exception as e:
            logger.error(f"LocalDB.get_bars 失败 {ts_code}: {e}")
            raise

    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """本地数据库不支持实时行情，返回空 DataFrame"""
        logger.warning("LocalDBProvider 不支持实时行情")
        return pd.DataFrame()

    def get_trading_dates(self, start: str, end: str) -> List[datetime]:
        """从 trade_cal 表获取沪市交易日列表"""
        cache_key = f"_trade_cal_{start}_{end}"
        cached = self._use_cache(cache_key)
        if cached is not None:
            return cached  # type: ignore

        sql = """
            SELECT cal_date FROM trade_cal
            WHERE exchange = 'SSE'
              AND is_open = 1
              AND cal_date BETWEEN ? AND ?
            ORDER BY cal_date ASC
        """
        try:
            with self._connect() as conn:
                df = pd.read_sql_query(sql, conn, params=(int(start), int(end)))
            dates = [
                datetime.strptime(str(d), '%Y%m%d')
                for d in df['cal_date'].tolist()
            ]
            self._set_cache(cache_key, dates)  # type: ignore
            return dates
        except Exception as e:
            logger.warning(f"LocalDB.get_trading_dates 失败，降级为工作日: {e}")
            dates = pd.date_range(
                start=pd.to_datetime(start, format='%Y%m%d'),
                end=pd.to_datetime(end, format='%Y%m%d'),
                freq='B'
            )
            return dates.to_pydatetime().tolist()

    def validate_symbol(self, symbol: str) -> bool:
        """检查股票代码在 stock_basic 中是否存在"""
        ts_code = self._normalize_ts_code(symbol)
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM stock_basic WHERE ts_code = ? LIMIT 1", (ts_code,)
                )
                return cur.fetchone() is not None
        except Exception:
            return bool(symbol)

    # ------------------------------------------------------------------ #
    # Extra helpers (for stock selector)
    # ------------------------------------------------------------------ #

    def get_stock_name(self, symbol: str) -> str:
        """根据代码查询股票名称"""
        ts_code = self._normalize_ts_code(symbol)
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT name FROM stock_basic WHERE ts_code = ? LIMIT 1", (ts_code,)
                )
                row = cur.fetchone()
                return row['name'] if row else symbol
        except Exception:
            return symbol

    def get_stock_list_from_db(self, market: str = 'sh') -> List[str]:
        """从 stock_basic 获取指定市场的股票代码列表（纯数字格式）

        Args:
            market: 'sh' 上交所, 'sz' 深交所, 'all' 全部
        """
        exchange_map = {'sh': 'SSE', 'sz': 'SZSE', 'all': None}
        exchange = exchange_map.get(market.lower())

        if exchange:
            sql = "SELECT symbol FROM stock_basic WHERE ts_code LIKE ? ORDER BY ts_code"
            suffix = '.SH' if exchange == 'SSE' else '.SZ'
            params = (f'%{suffix}',)
        else:
            sql = "SELECT symbol FROM stock_basic ORDER BY ts_code"
            params = ()

        try:
            with self._connect() as conn:
                df = pd.read_sql_query(sql, conn, params=params)
            return df['symbol'].dropna().tolist()
        except Exception as e:
            logger.error(f"LocalDB.get_stock_list_from_db 失败: {e}")
            return []

    def get_stock_basics(self) -> pd.DataFrame:
        """从 stock_basic + daily_basic 获取股票基础信息（市值等）"""
        sql = """
            SELECT
                sb.symbol AS code,
                sb.name   AS name,
                db.pe_ttm,
                db.pb,
                db.circ_mv / 10000.0 AS market_cap,
                d.vol  AS volume
            FROM stock_basic sb
            LEFT JOIN (
                SELECT ts_code, pe_ttm, pb, circ_mv
                FROM daily_basic
                WHERE trade_date = (SELECT MAX(trade_date) FROM daily_basic)
            ) db ON db.ts_code = sb.ts_code
            LEFT JOIN (
                SELECT ts_code, vol
                FROM daily
                WHERE trade_date = (SELECT MAX(trade_date) FROM daily)
            ) d ON d.ts_code = sb.ts_code
        """
        try:
            with self._connect() as conn:
                df = pd.read_sql_query(sql, conn)
            return df
        except Exception as e:
            logger.error(f"LocalDB.get_stock_basics 失败: {e}")
            return pd.DataFrame()
