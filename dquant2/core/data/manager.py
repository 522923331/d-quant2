"""数据管理器

负责数据的获取、缓存和分发
"""

from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple

import pandas as pd
import logging

from dquant2.core.data.interface import IDataProvider
from dquant2.core.data.providers import MockDataProvider

logger = logging.getLogger(__name__)


class DataManager:
    """数据管理器
    
    职责：
    1. 管理多个数据提供者
    2. 数据缓存
    3. 数据预处理
    4. 为回测提供数据迭代器
    """
    
    def __init__(self, provider: Optional[IDataProvider] = None):
        """初始化数据管理器
        
        Args:
            provider: 数据提供者，默认使用 MockDataProvider
        """
        self.provider = provider or MockDataProvider()
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._current_index = 0
        self._current_data: Optional[pd.DataFrame] = None
    
    def set_provider(self, provider: IDataProvider):
        """设置数据提供者"""
        self.provider = provider
        self._data_cache.clear()  # 清空缓存
        logger.info(f"数据提供者已切换为: {provider.name}")
    
    def load_data(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """加载数据
        
        Args:
            symbol: 股票代码
            start: 开始日期 YYYYMMDD
            end: 结束日期 YYYYMMDD
            freq: 频率
            
        Returns:
            K线数据
        """
        cache_key = f"{symbol}_{start}_{end}_{freq}"
        
        # 检查缓存
        if cache_key in self._data_cache:
            logger.debug(f"使用缓存数据: {cache_key}")
            return self._data_cache[cache_key]
        
        # 获取数据
        logger.info(f"加载数据: {symbol} {start} - {end}")
        data = self.provider.get_bars(symbol, start, end, freq)
        
        # 数据验证
        if data.empty:
            raise ValueError(f"未获取到数据: {symbol}")
        
        # 缓存
        self._data_cache[cache_key] = data
        
        return data
    
    def prepare_backtest_data(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """准备回测数据
        
        会进行一些预处理，如填充缺失值等
        """
        data = self.load_data(symbol, start, end, freq)
        
        # 数据预处理
        data = data.copy()
        
        # 填充缺失值
        data.fillna(method='ffill', inplace=True)
        data.fillna(method='bfill', inplace=True)
        
        # 确保数据按日期排序
        data.sort_index(inplace=True)
        
        # 存储当前数据供迭代使用
        self._current_data = data
        self._current_index = 0
        
        return data
    
    def iter_bars(self) -> Iterator[Tuple[datetime, pd.Series]]:
        """迭代K线数据
        
        用于回测时逐条迭代过去的数据
        
        Yields:
            (timestamp, bar_data)
        """
        if self._current_data is None:
            raise ValueError("请先调用 prepare_backtest_data 加载数据")
        
        for timestamp, bar in self._current_data.iterrows():
            yield timestamp, bar
    
    def get_bar_at(self, index: int) -> Tuple[datetime, pd.Series]:
        """获取指定索引的K线
        
        Args:
            index: 数据索引
            
        Returns:
            (timestamp, bar_data)
        """
        if self._current_data is None:
            raise ValueError("请先调用 prepare_backtest_data 加载数据")
        
        if index < 0 or index >= len(self._current_data):
            raise IndexError(f"索引超出范围: {index}")
        
        timestamp = self._current_data.index[index]
        bar = self._current_data.iloc[index]
        return timestamp, bar
    
    def get_history(
        self,
        index: int,
        window: int
    ) -> pd.DataFrame:
        """获取历史窗口数据
        
        Args:
            index: 当前索引
            window: 窗口大小
            
        Returns:
            历史数据
        """
        if self._current_data is None:
            raise ValueError("请先调用 prepare_backtest_data 加载数据")
        
        start_idx = max(0, index - window + 1)
        return self._current_data.iloc[start_idx:index + 1]
    
    def get_all_data(self) -> Optional[pd.DataFrame]:
        """获取所有当前数据"""
        return self._current_data
    
    def clear_cache(self):
        """清空缓存"""
        self._data_cache.clear()
        logger.info("数据缓存已清空")
