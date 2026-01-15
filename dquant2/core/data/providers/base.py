"""基础数据提供者

包含 Mock 数据提供者用于测试
"""

from datetime import datetime, timedelta
from typing import List

import numpy as np
import pandas as pd

from dquant2.core.data.interface import BaseDataProvider


class MockDataProvider(BaseDataProvider):
    """Mock 数据提供者
    
    用于测试和演示，生成随机数据
    """
    
    def __init__(self):
        super().__init__(name="mock")
    
    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """生成模拟K线数据
        
        使用几何布朗运动生成价格序列
        """
        # 解析日期
        start_date = pd.to_datetime(start, format='%Y%m%d')
        end_date = pd.to_datetime(end, format='%Y%m%d')
        
        # 生成日期序列
        if freq == 'd':
            dates = pd.date_range(start=start_date, end=end_date, freq='B')
        elif freq.endswith('m'):
            # 分钟级别
            minutes = int(freq[:-1])
            dates = pd.date_range(
                start=start_date,
                end=end_date,
                freq=f'{minutes}min'
            )
        else:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        n = len(dates)
        
        # 生成价格（几何布朗运动）
        initial_price = 100.0
        mu = 0.0001  # 漂移
        sigma = 0.02  # 波动率
        
        returns = np.random.normal(mu, sigma, n)
        prices = initial_price * np.exp(np.cumsum(returns))
        
        # 生成 OHLC
        data = {
            'date': dates,
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, n)),
            'high': prices * (1 + np.abs(np.random.uniform(0, 0.02, n))),
            'low': prices * (1 - np.abs(np.random.uniform(0, 0.02, n))),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, n),
        }
        
        df = pd.DataFrame(data)
        df.set_index('date', inplace=True)
        
        # 确保 high >= max(open, close) 和 low <= min(open, close)
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        return df
    
    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取模拟实时行情"""
        data = []
        for symbol in symbols:
            data.append({
                'symbol': symbol,
                'price': np.random.uniform(10, 200),
                'volume': np.random.randint(100000, 1000000),
                'timestamp': datetime.now()
            })
        return pd.DataFrame(data)
    
    def get_trading_dates(self, start: str, end: str) -> List[datetime]:
        """获取交易日（去除周末）"""
        start_date = pd.to_datetime(start, format='%Y%m%d')
        end_date = pd.to_datetime(end, format='%Y%m%d')
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        return dates.to_pydatetime().tolist()
