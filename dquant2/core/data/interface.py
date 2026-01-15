"""数据提供者接口

定义统一的数据接口，支持多数据源切换
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

import pandas as pd


class IDataProvider(ABC):
    """数据提供者接口
    
    所有数据源都应该实现这个接口，确保可以无缝切换。
    """
    
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """获取K线数据
        
        Args:
            symbol: 股票代码
            start: 开始日期 YYYYMMDD
            end: 结束日期 YYYYMMDD
            freq: 频率 'd'=日, '60m'=60分钟, '5m'=5分钟等
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            DataFrame with realtime quotes
        """
        pass
    
    @abstractmethod
    def get_trading_dates(
        self,
        start: str,
        end: str
    ) -> List[datetime]:
        """获取交易日历
        
        Args:
            start: 开始日期
            end: 结束日期
            
        Returns:
            交易日列表
        """
        pass
    
    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """验证股票代码是否有效
        
        Args:
            symbol: 股票代码
            
        Returns:
            是否有效
        """
        pass


class BaseDataProvider(IDataProvider):
    """数据提供者基类
    
    提供一些通用功能的默认实现
    """
    
    def __init__(self, name: str = "base"):
        self.name = name
        self._cache = {}  # 简单的缓存机制
    
    def _get_cache_key(self, symbol: str, start: str, end: str, freq: str) -> str:
        """生成缓存键"""
        return f"{symbol}_{start}_{end}_{freq}"
    
    def _use_cache(self, key: str) -> Optional[pd.DataFrame]:
        """使用缓存"""
        return self._cache.get(key)
    
    def _set_cache(self, key: str, data: pd.DataFrame):
        """设置缓存"""
        self._cache[key] = data.copy()
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def validate_symbol(self, symbol: str) -> bool:
        """默认的符号验证实现"""
        # 简单验证：不为空
        return bool(symbol and isinstance(symbol, str))
