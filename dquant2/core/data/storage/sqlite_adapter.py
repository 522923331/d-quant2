"""SQLite 数据库适配器

提供股票数据的持久化存储
参考: QuantOL/src/core/data/sqlite_adapter.py
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SQLiteAdapter:
    """SQLite 数据库适配器
    
    用于存储和检索股票数据
    """
    
    def __init__(self, db_path: str = None):
        """初始化 SQLite 适配器
        
        Args:
            db_path: 数据库文件路径，默认为 data/stock_data.db
        """
        if db_path is None:
            db_path = Path.home() / '.dquant2' / 'data' / 'stock_data.db'
        else:
            db_path = Path(db_path)
        
        # 确保目录存在
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"SQLite 数据库初始化: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # K线数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover REAL,
                pct_chg REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_date 
            ON kline_data(symbol, date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol 
            ON kline_data(symbol)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date 
            ON kline_data(date)
        ''')
        
        # 股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_info (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                market TEXT,
                list_date DATE,
                delist_date DATE,
                is_active INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 基本面数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fundamental_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                report_date DATE NOT NULL,
                pe_ratio REAL,
                pb_ratio REAL,
                ps_ratio REAL,
                pcf_ratio REAL,
                roe REAL,
                roa REAL,
                gross_margin REAL,
                net_margin REAL,
                market_cap REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, report_date)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fundamental_symbol 
            ON fundamental_data(symbol)
        ''')
        
        conn.commit()
        logger.info("数据库表结构初始化完成")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False  # 允许多线程访问
            )
            # 启用 WAL 模式提升并发性能
            self.conn.execute('PRAGMA journal_mode=WAL')
        
        return self.conn
    
    def save_kline_data(self, symbol: str, df: pd.DataFrame) -> int:
        """保存 K 线数据
        
        Args:
            symbol: 股票代码
            df: K线数据DataFrame，必须包含列: date, open, high, low, close, volume
            
        Returns:
            保存的行数
        """
        if df.empty:
            logger.warning(f"保存K线数据: {symbol} 数据为空")
            return 0
        
        conn = self._get_connection()
        
        # 准备数据
        df_save = df.copy()
        
        # 确保 date 是索引或列
        if 'date' not in df_save.columns:
            if df_save.index.name == 'date' or isinstance(df_save.index, pd.DatetimeIndex):
                df_save = df_save.reset_index()
        
        # 添加 symbol 列
        df_save['symbol'] = symbol
        
        # 选择需要的列
        columns = ['symbol', 'date', 'open', 'high', 'low', 'close', 
                   'volume', 'amount', 'turnover', 'pct_chg']
        
        # 只保留存在的列
        save_columns = [col for col in columns if col in df_save.columns]
        df_to_save = df_save[save_columns]
        
        # 使用 REPLACE INTO 避免重复
        try:
            rows_saved = 0
            for _, row in df_to_save.iterrows():
                cursor = conn.cursor()
                placeholders = ', '.join(['?' for _ in save_columns])
                columns_str = ', '.join(save_columns)
                
                # 转换数据类型（Timestamp -> string）
                values = []
                for col in save_columns:
                    val = row[col]
                    # 将 Timestamp 转换为字符串
                    if isinstance(val, pd.Timestamp):
                        val = val.strftime('%Y-%m-%d')
                    # 将 NaN 转换为 None
                    elif pd.isna(val):
                        val = None
                    values.append(val)
                
                cursor.execute(
                    f"REPLACE INTO kline_data ({columns_str}) VALUES ({placeholders})",
                    tuple(values)
                )
                rows_saved += 1
            
            conn.commit()
            logger.info(f"保存 K 线数据: {symbol}, {rows_saved} 行")
            return rows_saved
            
        except Exception as e:
            logger.error(f"保存 K 线数据失败: {symbol}, {e}")
            conn.rollback()
            return 0
    
    def load_kline_data(self, 
                       symbol: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """加载 K 线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            K线数据DataFrame
        """
        conn = self._get_connection()
        
        # 构建查询
        query = "SELECT * FROM kline_data WHERE symbol = ?"
        params = [symbol]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date ASC"
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            
            if df.empty:
                logger.debug(f"加载 K 线数据: {symbol} 无数据")
                return pd.DataFrame()
            
            # 设置日期索引
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # 删除不需要的列
            if 'id' in df.columns:
                df = df.drop(columns=['id', 'symbol', 'created_at'], errors='ignore')
            
            logger.debug(
                f"加载 K 线数据: {symbol}, {len(df)} 行 "
                f"({df.index[0]} - {df.index[-1]})"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"加载 K 线数据失败: {symbol}, {e}")
            return pd.DataFrame()
    
    def get_available_symbols(self) -> List[str]:
        """获取所有可用的股票代码
        
        Returns:
            股票代码列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT symbol FROM kline_data ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"数据库中共有 {len(symbols)} 只股票")
        
        return symbols
    
    def get_date_range(self, symbol: str) -> Optional[Dict]:
        """获取股票的数据日期范围
        
        Args:
            symbol: 股票代码
            
        Returns:
            {'start_date': xxx, 'end_date': yyy, 'days': zzz}
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT MIN(date), MAX(date), COUNT(*) FROM kline_data WHERE symbol = ?",
            (symbol,)
        )
        
        row = cursor.fetchone()
        if row and row[0]:
            return {
                'start_date': row[0],
                'end_date': row[1],
                'days': row[2]
            }
        
        return None
    
    def delete_kline_data(self, symbol: str) -> int:
        """删除股票的 K 线数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            删除的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM kline_data WHERE symbol = ?", (symbol,))
        rows_deleted = cursor.rowcount
        conn.commit()
        
        logger.info(f"删除 K 线数据: {symbol}, {rows_deleted} 行")
        
        return rows_deleted
    
    def save_stock_info(self, stocks: List[Dict]) -> int:
        """保存股票基本信息
        
        Args:
            stocks: 股票信息列表 [{'symbol': xxx, 'name': yyy, 'market': zzz}, ...]
            
        Returns:
            保存的行数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        rows_saved = 0
        for stock in stocks:
            try:
                cursor.execute('''
                    REPLACE INTO stock_info (symbol, name, market, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    stock.get('symbol'),
                    stock.get('name'),
                    stock.get('market'),
                    datetime.now()
                ))
                rows_saved += 1
            except Exception as e:
                logger.error(f"保存股票信息失败: {stock.get('symbol')}, {e}")
        
        conn.commit()
        logger.info(f"保存股票信息: {rows_saved} 行")
        
        return rows_saved
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT symbol, name, market, list_date FROM stock_info WHERE symbol = ?",
            (symbol,)
        )
        
        row = cursor.fetchone()
        if row:
            return {
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'list_date': row[3]
            }
        
        return None
    
    def save_fundamental_data(self, symbol: str, data: Dict) -> bool:
        """保存基本面数据
        
        Args:
            symbol: 股票代码
            data: 基本面数据字典
            
        Returns:
            是否保存成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                REPLACE INTO fundamental_data (
                    symbol, report_date, pe_ratio, pb_ratio, ps_ratio, pcf_ratio,
                    roe, roa, gross_margin, net_margin, market_cap, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                data.get('report_date'),
                data.get('pe_ratio'),
                data.get('pb_ratio'),
                data.get('ps_ratio'),
                data.get('pcf_ratio'),
                data.get('roe'),
                data.get('roa'),
                data.get('gross_margin'),
                data.get('net_margin'),
                data.get('market_cap'),
                datetime.now()
            ))
            
            conn.commit()
            logger.debug(f"保存基本面数据: {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"保存基本面数据失败: {symbol}, {e}")
            return False
    
    def load_fundamental_data(self, 
                             symbol: str,
                             report_date: Optional[str] = None) -> Optional[Dict]:
        """加载基本面数据
        
        Args:
            symbol: 股票代码
            report_date: 报告日期，为空则获取最新
            
        Returns:
            基本面数据字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if report_date:
            cursor.execute(
                "SELECT * FROM fundamental_data WHERE symbol = ? AND report_date = ?",
                (symbol, report_date)
            )
        else:
            cursor.execute(
                "SELECT * FROM fundamental_data WHERE symbol = ? ORDER BY report_date DESC LIMIT 1",
                (symbol,)
            )
        
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        
        return None
    
    def get_database_stats(self) -> Dict:
        """获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # K线数据统计
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM kline_data")
        total_symbols = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM kline_data")
        total_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(date), MAX(date) FROM kline_data")
        date_range = cursor.fetchone()
        
        # 股票信息统计
        cursor.execute("SELECT COUNT(*) FROM stock_info")
        total_stock_info = cursor.fetchone()[0]
        
        # 数据库文件大小
        db_size = Path(self.db_path).stat().st_size / (1024 * 1024)  # MB
        
        return {
            'total_symbols': total_symbols,
            'total_kline_records': total_records,
            'date_range': {
                'start': date_range[0],
                'end': date_range[1]
            } if date_range[0] else None,
            'total_stock_info': total_stock_info,
            'db_size_mb': db_size,
            'db_path': self.db_path
        }
    
    def vacuum(self):
        """清理数据库，回收空间"""
        conn = self._get_connection()
        conn.execute('VACUUM')
        logger.info("数据库已清理优化")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")
    
    def __enter__(self):
        """上下文管理器进入"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
    
    def backup(self, backup_path: str) -> bool:
        """备份数据库
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            是否备份成功
        """
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"数据库备份成功: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        """执行自定义 SQL 查询
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            查询结果DataFrame
        """
        conn = self._get_connection()
        
        try:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return pd.DataFrame()
