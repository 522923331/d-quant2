"""资金管理基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from dquant2.core.event_bus.events import SignalEvent


class BaseCapitalStrategy(ABC):
    """资金管理策略基类
    
    负责根据信号强度和账户状况计算仓位大小
    """
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
    
    @abstractmethod
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio_value: float,
        cash: float,
        current_price: float
    ) -> int:
        """计算仓位大小
        
        Args:
            signal: 信号事件
            portfolio_value: 组合总价值
            cash: 可用现金
            current_price: 当前价格
            
        Returns:
            股票数量
        """
        pass
