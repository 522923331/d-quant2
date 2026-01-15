"""风控基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from dquant2.core.event_bus.events import OrderEvent

logger = logging.getLogger(__name__)


class BaseRiskControl(ABC):
    """风控基类
    
    所有风控规则都应该继承此类
    """
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self.violations = []  # 违规记录
    
    @abstractmethod
    def check(self, order: OrderEvent, portfolio: Any) -> tuple:
        """检查订单是否满足风控要求
        
        Args:
            order: 订单事件
            portfolio: 投资组合
            
        Returns:
            (is_valid, message)
        """
        pass
    
    def record_violation(self, message: str):
        """记录违规"""
        self.violations.append({
            'message': message,
            'timestamp': None
        })
        logger.warning(f"风控违规 [{self.name}]: {message}")
