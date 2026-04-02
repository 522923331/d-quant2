#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare数据下载器
功能：从Tushare API下载数据并批量插入SQLite数据库
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import tushare as ts

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def _default_db_path() -> str:
    """
    默认指向仓库根目录的 data/db/quant.db（供 d-quant2 作为数据源直接读取）。
    """
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "data" / "db" / "quant.db")


class TushareDownloader:
    """Tushare数据下载器"""

    def __init__(self, token: str, db_path: str = None):
        """
        初始化下载器

        Args:
            token: Tushare Pro token
            db_path: SQLite数据库路径
        """
        self.token = token
        self.db_path = db_path or os.getenv("QUANT_DB_PATH") or _default_db_path()

        # 初始化Tushare Pro API
        self.pro = ts.pro_api(token)

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        os.makedirs('cache', exist_ok=True)

        # 连接数据库
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")

        # API调用统计
        self.api_call_count = 0
        self.start_time = datetime.now()

        logger.info(f"Tushare下载器初始化完成，数据库: {self.db_path}")

    def safe_api_call(self, func, **kwargs):
        """
        安全的API调用，包含错误处理和重试机制

        Args:
            func: API函数
            **kwargs: API参数

        Returns:
            DataFrame 或 None
        """
        max_retries = 4
        retry_delay = 5  # 秒

        for attempt in range(max_retries):
            try:
                self.api_call_count += 1
                df = func(**kwargs)

                # 检查返回结果
                if df is None or df.empty:
                    func_name = getattr(func, '__name__', str(func))
                    logger.debug(f"API返回空数据: {func_name}, 参数: {kwargs}")
                    return None

                func_name = getattr(func, '__name__', str(func))
                logger.debug(f"API调用成功: {func_name}, 返回 {len(df)} 条记录")
                return df

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"API调用失败 ({attempt + 1}/{max_retries}): {e}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error(f"API调用失败，已达最大重试次数: {e}")
                    return None
    def save_to_sqlite(self, df: pd.DataFrame, table_name: str,
                       if_exists: str = 'append',
                       dtype: Optional[Dict] = None) -> bool:
        """保存DataFrame到SQLite，支持自动UPSERT策略防止主键冲突"""
        if df is None or df.empty:
            logger.warning(f"尝试保存空DataFrame到表 {table_name}")
            return False

        try:
            if if_exists == 'replace':
                df.to_sql(table_name, self.conn, if_exists=if_exists, index=False, dtype=dtype)
                logger.info(f"成功替换 {len(df)} 条数据到表 {table_name}")
                return True

            # 自动查询表的主键用于 UPSERT
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            if not columns_info:
                # 表不存在，直接按 append 让 pandas 建表
                df.to_sql(table_name, self.conn, if_exists='append', index=False, dtype=dtype)
                logger.info(f"成功建表并保存 {len(df)} 条数据到表 {table_name}")
                return True
                
            all_columns = [info[1] for info in columns_info]
            pk_columns = [info[1] for info in columns_info if info[5] > 0] # info[5] is pk flag
            
            valid_columns = [col for col in df.columns if col in all_columns]
            df = df[valid_columns]

            if not pk_columns:
                # 没有主键，退化为普通 append
                df.to_sql(table_name, self.conn, if_exists='append', index=False, dtype=dtype)
                logger.info(f"成功追加 {len(df)} 条数据到表 {table_name} (无主键)")
                return True

            # 构建 UPSERT SQL
            conflict_clause = ', '.join(pk_columns)
            update_columns = [col for col in valid_columns if col not in pk_columns]
            
            columns_str = ', '.join(valid_columns)
            placeholders = ', '.join(['?'] * len(valid_columns))
            
            if update_columns:
                update_set = ', '.join([f"{col}=excluded.{col}" for col in update_columns])
                sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT({conflict_clause}) DO UPDATE SET {update_set}"
            else:
                sql = f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})"

            data_tuples = [tuple(row) for row in df.itertuples(index=False, name=None)]
            cursor.executemany(sql, data_tuples)
            self.conn.commit()

            logger.info(f"成功 UPSERT {len(df)} 条数据到表 {table_name}")
            return True

        except Exception as e:
            logger.error(f"保存数据到表 {table_name} 失败: {e}")
            self.conn.rollback()
            return False

    # def _convert_date_columns(self, df: pd.DataFrame) -> pd.DataFrame:
    #     """
    #     转换日期列格式
    #
    #     Args:
    #         df: 原始DataFrame
    #
    #     Returns:
    #         转换后的DataFrame
    #     """
    #     df = df.copy()
    #
    #     # 常见的日期列名
    #     date_columns = ['trade_date', 'cal_date', 'list_date', 'delist_date','f_ann_date','suspend_date','resume_date',
    #                     'ann_date', 'end_date', 'base_date', 'exp_date']
    #
    #     for col in df.columns:
    #         # 检查是否是日期列（根据列名或数据类型）
    #         if col in date_columns or 'date' in col.lower():
    #             try:
    #                 # 转换日期格式
    #                 df[col] = pd.to_datetime(df[col], format='%Y%m%d', errors='coerce')
    #                 # 转换为字符串格式 YYYY-MM-DD
    #                 df[col] = df[col].dt.strftime('%Y-%m-%d')
    #             except:
    #                 # 如果转换失败，保持原样
    #                 pass
    #
    #     return df

    def download_stock_basic(self) -> bool:
        """下载股票基本信息"""
        logger.info("开始下载股票基本信息...")

        try:
            df = self.safe_api_call(self.pro.stock_basic,
                                    exchange='',
                                    list_status='L',
                                    fields='ts_code,symbol,name,area,industry,market,list_date,is_hs,act_name,act_ent_type')

            if df is not None:
                # 重命名列以匹配数据库表
                # df.rename(columns={'is_hs': 'is_hs'}, inplace=True)

                # 保存到数据库
                success = self.save_to_sqlite(df, 'stock_basic', if_exists='replace')

                # # 保存缓存文件
                # df.to_parquet('cache/stock_basic.parquet')

                return success
            return False

        except Exception as e:
            logger.error(f"下载股票基本信息失败: {e}")
            return False

    def download_index_basic(self) -> bool:
        """下载指数基本信息"""
        logger.info("开始下载指数基本信息...")

        try:
            # 只获取主要的宽基和行业指数，避开无行情数据的 OTH(比如CJ长江指数)
            markets = ['SSE', 'SZSE', 'CSI']
            dfs = []
            for market in markets:
                df = self.safe_api_call(self.pro.index_basic, market=market)
                if df is not None and not df.empty:
                    dfs.append(df)
            
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                # 保存到数据库
                success = self.save_to_sqlite(df, 'index_basic', if_exists='replace')

                # 保存缓存
                # df.to_parquet('cache/index_basic.parquet')

                return success
            return False

        except Exception as e:
            logger.error(f"下载指数基本信息失败: {e}")
            return False

    def _get_date_args(self, table_name: str, start_date: str, end_date: str) -> tuple[str, str]:
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        elif isinstance(end_date, int):
            end_date = str(end_date)
            
        if start_date is None or start_date == 'auto':
            try:
                date_col = 'ann_date' if table_name == 'income' else 'trade_date'
                latest_date = self.conn.execute(
                    f"SELECT MAX({date_col}) FROM {table_name} WHERE {date_col} IS NOT NULL"
                ).fetchone()[0]
                if latest_date:
                    start_date = str(latest_date).replace('-', '')
                else:
                    start_date = '20200101' # 默认初始日期
            except Exception:
                start_date = '20200101'
        elif isinstance(start_date, int):
            start_date = str(start_date)
            
        return start_date, end_date

    def _get_all_stock_codes(self) -> list:
        try:
            stock_list = self.conn.execute("SELECT ts_code FROM stock_basic").fetchall()
            return [code[0] for code in stock_list]
        except Exception as e:
            logger.error(f"获取股票代码列表失败: {e}")
            return []

    def _get_all_index_codes(self) -> list:
        try:
            index_list = self.conn.execute("SELECT ts_code FROM index_basic").fetchall()
            return [code[0] for code in index_list]
        except Exception as e:
            logger.error(f"获取指数代码列表失败: {e}")
            return []

    def _download_batch_data(self, api_func, table_name: str, stock_codes: list, start_date: str, end_date: str, batch_size: int = 100, **kwargs) -> bool:
        if not stock_codes:
            logger.warning(f"没有找到可用的代码列表，表: {table_name}")
            return False

        total_stocks = len(stock_codes)
        success_count = 0

        for i in range(0, total_stocks, batch_size):
            batch = stock_codes[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_stocks + batch_size - 1) // batch_size
            logger.info(f"下载 {table_name} 批次 {batch_num}/{total_batches}: {len(batch)} 个代码")

            batch_dfs = []
            for ts_code in batch:
                try:
                    df = self.safe_api_call(api_func, ts_code=ts_code, start_date=start_date, end_date=end_date, **kwargs)
                    if df is not None and not df.empty:
                        batch_dfs.append(df)
                        success_count += 1
                except Exception as e:
                    logger.error(f"下载 {table_name} - {ts_code} 数据失败: {e}")
                    
                # 遵循 Tushare 限流规则: 每分钟最多 500 次 -> 每次休眠 0.125s
                time.sleep(0.15)

            # 批量写入数据库，减少 UPSERT 次数，提高性能
            if batch_dfs:
                combined_df = pd.concat(batch_dfs, ignore_index=True)
                self.save_to_sqlite(combined_df, table_name)

            progress = min(i + batch_size, total_stocks)
            logger.info(f"进度 {table_name}: {progress}/{total_stocks} ({progress / total_stocks:.1%})")

        logger.info(f"{table_name} 下载完成: 成功 {success_count}/{total_stocks}")
        return success_count > 0
    def _get_trading_dates(self, start_date: str, end_date: str) -> list:
        try:
            sql = """
                SELECT cal_date FROM trade_cal 
                WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN ? AND ?
                ORDER BY cal_date ASC
            """
            dates = self.conn.execute(sql, (start_date, end_date)).fetchall()
            if not dates:
                df = self.safe_api_call(self.pro.trade_cal, exchange='SSE', is_open='1', start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    return df['cal_date'].tolist()
                return []
            return [str(d[0]) for d in dates]
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return []

    def _download_by_date(self, api_func, table_name: str, start_date: str, end_date: str, batch_size: int = 20, **kwargs) -> bool:
        trade_dates = self._get_trading_dates(start_date, end_date)
        if not trade_dates:
            logger.warning(f"没有找到有效的交易日期，表: {table_name}, 区间: {start_date} - {end_date}")
            return False

        total_dates = len(trade_dates)
        success_count = 0

        for i in range(0, total_dates, batch_size):
            batch = trade_dates[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_dates + batch_size - 1) // batch_size
            logger.info(f"下载 {table_name} 批次 {batch_num}/{total_batches}: {len(batch)} 个交易日")

            batch_dfs = []
            for t_date in batch:
                try:
                    df = self.safe_api_call(api_func, trade_date=t_date, **kwargs)
                    if df is not None and not df.empty:
                        batch_dfs.append(df)
                        success_count += 1
                except Exception as e:
                    logger.error(f"下载 {table_name} - {t_date} 数据失败: {e}")

                time.sleep(0.125)

            if batch_dfs:
                combined_df = pd.concat(batch_dfs, ignore_index=True)
                self.save_to_sqlite(combined_df, table_name)

            progress = min(i + batch_size, total_dates)
            logger.info(f"进度 {table_name}: {progress}/{total_dates} ({progress / total_dates:.1%})")

        logger.info(f"{table_name} 下载完成: 成功 {success_count}/{total_dates}")
        return success_count > 0

    def download_index_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('index_daily', start_date, end_date)
        logger.info(f"开始下载指数日线数据: {start_date} 到 {end_date}")
        codes = self._get_all_index_codes()
        return self._download_batch_data(self.pro.index_daily, 'index_daily', codes, start_date, end_date)

    def download_daily_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('daily', start_date, end_date)
        logger.info(f"开始下载股票日线数据: {start_date} 到 {end_date}")
        return self._download_by_date(self.pro.daily, 'daily', start_date, end_date, batch_size=20)

    def download_daily_basic(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('daily_basic', start_date, end_date)
        logger.info(f"开始下载日线基础数据: {start_date} 到 {end_date}")
        return self._download_by_date(self.pro.daily_basic, 'daily_basic', start_date, end_date, batch_size=20)

    def download_suspend_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('suspend', start_date, end_date)
        logger.info(f"开始下载停复牌数据: {start_date} 到 {end_date}")
        return self._download_by_date(self.pro.suspend_d, 'suspend', start_date, end_date, batch_size=20, suspend_type='')

    def download_stk_limit(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('stk_limit', start_date, end_date)
        logger.info(f"开始下载涨跌停数据: {start_date} 到 {end_date}")
        return self._download_by_date(self.pro.stk_limit, 'stk_limit', start_date, end_date, batch_size=20)

    def download_income_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        start_date, end_date = self._get_date_args('income', start_date, end_date)
        logger.info(f"开始下载利润表数据: {start_date} 到 {end_date}")
        codes = self._get_all_stock_codes()
        return self._download_batch_data(self.pro.income, 'income', codes, start_date, end_date)

    def download_dailies_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("开始下载所有股票日频数据")
        logger.info("=" * 50)
        results = {}
        results['daily_data'] = self.download_daily_data(start_date, end_date)
        results['daily_basic'] = self.download_daily_basic(start_date, end_date)
        results['suspend_data'] = self.download_suspend_data(start_date, end_date)
        results['limit_data'] = self.download_stk_limit(start_date, end_date)
        for task, success in results.items():
            status = "✓ 成功" if success else "✗ 失败"
            logger.info(f"{task}: {status}")
        return all(results.values())

    def download_indexes_data(self, start_date: str = 'auto', end_date: str = None) -> bool:
        logger.info("=" * 50)
        logger.info("开始下载指数日频数据")
        logger.info("=" * 50)
        results = {}
        # 为了防止只有日线没有基本信息，同时下载一下指数基本信息
        results['index_basic'] = self.download_index_basic()
        results['index_data'] = self.download_index_data(start_date, end_date)
        for task, success in results.items():
            status = "✓ 成功" if success else "✗ 失败"
            logger.info(f"{task}: {status}")
        return all(results.values())

    def download_once_data(self):
        """下载一次性的基础数据"""
        logger.info("=" * 50)
        logger.info("开始下载所有基础数据")
        logger.info("=" * 50)

        results = {}

        # 1. 下载交易日历
        # results['trade_cal'] = self.download_trade_cal()

        # 2. 下载股票基本信息
        results['stock_basic'] = self.download_stock_basic()

        # 显示统计信息
        logger.info("=" * 50)
        logger.info("数据下载完成，统计信息:")
        logger.info(f"总API调用次数: {self.api_call_count}")
        logger.info(f"总耗时: {datetime.now() - self.start_time}")

        for task, success in results.items():
            status = "✓ 成功" if success else "✗ 失败"
            logger.info(f"{task}: {status}")

        return all(results.values())

    def get_table_stats(self):
        """获取数据库表统计信息"""
        tables = ['stock_basic', 'index_basic', 'daily', 'daily_basic', 'income', 'trade_cal']

        stats = {}
        for table in tables:
            try:
                count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                # 获取最新数据日期（如果有trade_date列，income表特殊处理使用ann_date）
                try:
                    date_col = 'ann_date' if table == 'income' else 'trade_date'
                    latest_date = self.conn.execute(
                        f"SELECT MAX({date_col}) FROM {table} WHERE {date_col} IS NOT NULL"
                    ).fetchone()[0]
                except:
                    latest_date = None

                stats[table] = {
                    'count': count,
                    'latest_date': latest_date
                }
            except:
                stats[table] = {'count': 0, 'latest_date': None}

        return stats

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")

    def __del__(self):
        """析构函数"""
        self.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Tushare数据下载器')
    # parser.add_argument('--token', required=True, help='Tushare Pro token')
    parser.add_argument('--db', default=None, help='数据库路径（默认指向仓库根目录 data/db/quant.db；也可用环境变量 QUANT_DB_PATH 覆盖）')
    parser.add_argument('--task', choices=['all', 'once', 'stock', 'index', 'daily', 'income', 'suspend', 'limit'], default='all', help='下载任务')
    parser.add_argument('--start-date', help='开始日期 (YYYYMMDD)，设为auto则自动获取最后更新日期', default='auto')
    parser.add_argument('--end-date', help='结束日期 (YYYYMMDD)，默认为今天', default=None)

    args = parser.parse_args()

    # 创建下载器
    downloader = TushareDownloader('7c8157eef2bc27a38af3711c83ee5ed1a244b8d6732caeb6a08fecd7', args.db)

    try:
        # 执行下载任务
        if args.task == 'all':
            # 下载所有数据：先下载基础数据，再下载日线数据
            logger.info("执行完整数据下载流程")
            success = downloader.download_once_data()
            if success:
                success = downloader.download_dailies_data(args.start_date, args.end_date) and downloader.download_indexes_data(args.start_date, args.end_date)
        elif args.task == 'once':
            success = downloader.download_once_data()
        elif args.task == 'daily':
            success = downloader.download_dailies_data(args.start_date, args.end_date)
        elif args.task == 'index':
            success = downloader.download_indexes_data(args.start_date, args.end_date)
        elif args.task == 'income':
            success = downloader.download_income_data(args.start_date, args.end_date)
        elif args.task == 'suspend':
            success = downloader.download_suspend_data(args.start_date, args.end_date)
        elif args.task == 'limit':
            success = downloader.download_stk_limit(args.start_date, args.end_date)
        else:
            logger.warning(f"未识别的任务类型: {args.task}")
            success = False

        # 显示数据库统计
        if success:
            stats = downloader.get_table_stats()
            print("\n数据库统计信息:")
            print("-" * 40)
            for table, data in stats.items():
                print(f"{table:15} {data['count']:8} 条记录  最新日期: {data['latest_date']}")

    except KeyboardInterrupt:
        print("\n用户中断下载")
    finally:
        downloader.close()


if __name__ == "__main__":
    main()