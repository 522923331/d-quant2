"""策略基类

所有策略都应该继承此基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import uuid
import logging

import pandas as pd

from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """策略基类
    
    所有自定义策略都应该继承此类并实现抽象方法。
    
    生命周期：
    1. __init__: 初始化策略参数
    2. on_start: 回测开始时调用
    3. on_data: 每个新数据到达时调用
    4. on_stop: 回测结束时调用
    """
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        """初始化策略
        
        Args:
            name: 策略名称
            params: 策略参数字典
        """
        self.name = name
        self.params = params or {}
        self.strategy_id = str(uuid.uuid4())
        
        # 策略状态
        self.is_initialized = False
        self.data_buffer: List[pd.Series] = []  # 数据缓冲区
        
        logger.info(f"策略 '{name}' 已创建, ID: {self.strategy_id}")
    
    @abstractmethod
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据事件
        
        这是策略的核心方法，每当新数据到达时都会被调用。
        策略应该分析数据并返回交易信号。
        
        Args:
            event: 市场数据事件
            
        Returns:
            信号事件列表（可能为空）
        """
        pass
    
    def on_start(self):
        """回测开始时调用
        
        可以在这里进行一些初始化工作，如加载模型等。
        """
        self.is_initialized = True
        logger.info(f"策略 '{self.name}' 已启动")
    
    def on_stop(self):
        """回测结束时调用
        
        可以在这里进行一些清理工作，如保存结果等。
        """
        logger.info(f"策略 '{self.name}' 已停止")
    
    def _add_to_buffer(self, data: pd.Series, max_size: int = 1000):
        """添加数据到缓冲区
        
        Args:
            data: 数据
            max_size: 最大缓冲区大小
        """
        self.data_buffer.append(data)
        if len(self.data_buffer) > max_size:
            self.data_buffer.pop(0)
    
    def get_buffer_df(self) -> pd.DataFrame:
        """获取缓冲区数据为DataFrame"""
        if not self.data_buffer:
            return pd.DataFrame()
        return pd.DataFrame(self.data_buffer)
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取策略参数
        
        Args:
            key: 参数键
            default: 默认值
            
        Returns:
            参数值
        """
        return self.params.get(key, default)
    
    def set_param(self, key: str, value: Any):
        """设置策略参数
        
        Args:
            key: 参数键
            value: 参数值
        """
        self.params[key] = value
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"{self.__class__.__name__}(name='{self.name}', id='{self.strategy_id[:8]}...')"
