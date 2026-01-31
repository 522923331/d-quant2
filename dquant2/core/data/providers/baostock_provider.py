"""Baostock 数据提供者

使用 Baostock 获取真实市场数据，与选股模块数据源一致
"""

from datetime import datetime
from typing import List
import logging

import pandas as pd
import baostock as bs

from dquant2.core.data.interface import BaseDataProvider

logger = logging.getLogger(__name__)


class BaostockProvider(BaseDataProvider):
    """Baostock 数据提供者
    
    使用 Baostock 获取 A 股数据
    """
    
    def __init__(self):
        super().__init__(name="baostock")
        self._is_logged_in = False
        self._login()
    
    def _login(self):
        """登录 Baostock"""
        if not self._is_logged_in:
            try:
                lg = bs.login()
                if lg.error_code == '0':
                    self._is_logged_in = True
                    logger.info("Baostock 登录成功")
                else:
                    logger.error(f"Baostock 登录失败: {lg.error_msg}")
            except Exception as e:
                logger.error(f"Baostock 登录异常: {e}")
    
    def _logout(self):
        """登出 Baostock"""
        if self._is_logged_in:
            try:
                bs.logout()
                self._is_logged_in = False
                logger.info("Baostock 登出成功")
            except Exception as e:
                logger.error(f"Baostock 登出异常: {e}")
    
    def _get_baostock_code(self, symbol: str) -> str:
        """转换为 Baostock 格式的股票代码"""
        if symbol.startswith('6'):
            return f"sh.{symbol}"
        else:
            return f"sz.{symbol}"
    
    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """获取K线数据"""
        # 检查Parquet缓存
        from dquant2.core.data.cache import ParquetCache
        cache = ParquetCache()
        
        # 尝试从缓存加载
        cached_df = cache.load(symbol, start, end)
        if cached_df is not None:
            return cached_df
        
        # 内存缓存
        cache_key = self._get_cache_key(symbol, start, end, freq)
        cached = self._use_cache(cache_key)
        if cached is not None:
            return cached
        
        # 确保已登录
        if not self._is_logged_in:
            self._login()
        
        try:
            # 转换日期格式
            start_date = pd.to_datetime(start, format='%Y%m%d').strftime('%Y-%m-%d')
            end_date = pd.to_datetime(end, format='%Y%m%d').strftime('%Y-%m-%d')
            
            # 转换股票代码
            bs_code = self._get_baostock_code(symbol)
            
            # 频率映射
            freq_map = {
                'd': 'd',
                '60m': '60',
                '30m': '30',
                '15m': '15',
                '5m': '5'
            }
            bs_freq = freq_map.get(freq, 'd')
            
            # 调用 baostock
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,adjustflag",
                start_date=start_date,
                end_date=end_date,
                frequency=bs_freq,
                adjustflag="2"  # 前复权
            )
            
            if rs.error_code != '0':
                logger.error(f"Baostock 查询失败: {rs.error_msg}")
                raise Exception(f"Baostock 查询失败: {rs.error_msg}")
            
            # 获取数据
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f"Baostock 未获取到数据: {symbol}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换数据类型
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 只保留必需列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # 保存到 Parquet 缓存
            cache.save(symbol, df)
            
            # 缓存
            self._set_cache(cache_key, df)
            
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败 {symbol}: {str(e)}")
            raise
    
    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情（Baostock不支持实时行情）"""
        logger.warning("Baostock 不支持实时行情")
        return pd.DataFrame()
    
    def get_trading_dates(self, start: str, end: str) -> List[datetime]:
        """获取交易日历"""
        if not self._is_logged_in:
            self._login()
        
        try:
            start_date = pd.to_datetime(start, format='%Y%m%d').strftime('%Y-%m-%d')
            end_date = pd.to_datetime(end, format='%Y%m%d').strftime('%Y-%m-%d')
            
            rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
            
            dates = []
            while rs.next():
                row = rs.get_row_data()
                if row[1] == '1':  # is_trading_day
                    dates.append(pd.to_datetime(row[0]))
            
            return dates
            
        except Exception as e:
            logger.warning(f"获取交易日历失败: {str(e)}")
            # 降级方案：使用工作日
            dates = pd.date_range(
                start=pd.to_datetime(start, format='%Y%m%d'),
                end=pd.to_datetime(end, format='%Y%m%d'),
                freq='B'
            )
            return dates.tolist()
    
    def validate_symbol(self, symbol: str) -> bool:
        """验证股票代码"""
        if not isinstance(symbol, str):
            return False
        if len(symbol) != 6:
            return False
        if not symbol.isdigit():
            return False
        return True
    
    def __del__(self):
        """析构时登出"""
        self._logout()
