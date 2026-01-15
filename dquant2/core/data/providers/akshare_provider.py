"""AkShare 数据提供者

使用 AkShare 获取真实市场数据
"""

from datetime import datetime
from typing import List
import logging

import pandas as pd

from dquant2.core.data.interface import BaseDataProvider

logger = logging.getLogger(__name__)


class AkShareProvider(BaseDataProvider):
    """AkShare 数据提供者
    
    使用 AkShare 获取 A 股数据
    """
    
    def __init__(self):
        super().__init__(name="akshare")
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("请安装 akshare: pip install akshare")
            raise
    
    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """获取K线数据"""
        # 检查缓存
        cache_key = self._get_cache_key(symbol, start, end, freq)
        cached = self._use_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            # 转换日期格式
            start_date = pd.to_datetime(start, format='%Y%m%d').strftime('%Y%m%d')
            end_date = pd.to_datetime(end, format='%Y%m%d').strftime('%Y%m%d')
            
            # 调用 akshare
            if freq == 'd':
                # 日线数据
                df = self.ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"  # 前复权
                )
            else:
                # 其他频率暂不支持，使用日线
                logger.warning(f"AkShare 暂不支持 {freq} 频率，使用日线代替")
                df = self.ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
            })
            
            # 设置索引
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 只保留必需列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # 缓存
            self._set_cache(cache_key, df)
            
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败 {symbol}: {str(e)}")
            raise
    
    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情"""
        try:
            # 获取实时行情
            df = self.ak.stock_zh_a_spot_em()
            
            # 筛选指定股票
            df = df[df['代码'].isin(symbols)]
            
            # 标准化列名
            df = df.rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '成交量': 'volume',
                '成交额': 'amount',
            })
            
            return df[['symbol', 'name', 'price', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"获取实时行情失败: {str(e)}")
            raise
    
    def get_trading_dates(self, start: str, end: str) -> List[datetime]:
        """获取交易日历"""
        try:
            # 获取交易日历
            df = self.ak.tool_trade_date_hist_sina()
            
            # 筛选日期范围
            start_date = pd.to_datetime(start, format='%Y%m%d')
            end_date = pd.to_datetime(end, format='%Y%m%d')
            
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
            
            return df['trade_date'].tolist()
            
        except Exception as e:
            logger.warning(f"获取交易日历失败，使用工作日代替: {str(e)}")
            # 降级方案：使用工作日
            dates = pd.date_range(
                start=pd.to_datetime(start, format='%Y%m%d'),
                end=pd.to_datetime(end, format='%Y%m%d'),
                freq='B'
            )
            return dates.tolist()
    
    def validate_symbol(self, symbol: str) -> bool:
        """验证股票代码"""
        # A股代码格式：6位数字
        if not isinstance(symbol, str):
            return False
        if len(symbol) != 6:
            return False
        if not symbol.isdigit():
            return False
        return True
