"""风控管理器

集成多个风控规则
"""

from typing import List
import logging

from dquant2.core.risk.base import BaseRiskControl
from dquant2.core.event_bus.events import OrderEvent

logger = logging.getLogger(__name__)


class RiskManager:
    """风控管理器
    
    负责管理多个风控规则，所有订单必须通过所有风控检查
    """
    
    def __init__(self, portfolio):
        """初始化风控管理器
        
        Args:
            portfolio: 投资组合对象
        """
        self.portfolio = portfolio
        self.risk_controls: List[BaseRiskControl] = []
        
    def add_control(self, control: BaseRiskControl):
        """添加风控规则"""
        self.risk_controls.append(control)
        logger.info(f"已添加风控规则: {control.name}")
    
    def validate_order(self, order: OrderEvent) -> tuple:
        """验证订单
        
        Args:
            order: 订单事件
            
        Returns:
            (is_valid, messages)
        """
        messages = []
        
        for control in self.risk_controls:
            is_valid, message = control.check(order, self.portfolio)
            if not is_valid:
                messages.append(f"[{control.name}] {message}")
        
        if messages:
            logger.warning(f"订单未通过风控: {order.order_id}")
            return False, messages
        
        return True, []
    
    def get_violations(self) -> list:
        """获取所有违规记录"""
        violations = []
        for control in self.risk_controls:
            violations.extend(control.violations)
        return violations


class MaxPositionControl(BaseRiskControl):
    """最大仓位控制"""
    
    def __init__(self, max_position_ratio: float = 0.3):
        super().__init__("MaxPosition")
        self.max_position_ratio = max_position_ratio
    
    def check(self, order: OrderEvent, portfolio) -> tuple:
        if order.direction != 'BUY':
            return True, ""
        
        # 计算订单价值
        order_value = order.quantity * (order.price or 0)
        portfolio_value = portfolio.get_total_value()
        
        if portfolio_value == 0:
            return True, ""
        
        position_ratio = order_value / portfolio_value
        
        if position_ratio > self.max_position_ratio:
            msg = f"仓位比例 {position_ratio:.2%} 超过限制 {self.max_position_ratio:.2%}"
            self.record_violation(msg)
            return False, msg
        
        return True, ""


class CashControl(BaseRiskControl):
    """现金充足性控制"""
    
    def __init__(self):
        super().__init__("Cash")
    
    def check(self, order: OrderEvent, portfolio) -> tuple:
        if order.direction != 'BUY':
            return True, ""
        
        required_cash = order.quantity * (order.price or 0) * 1.001  # 包含手续费
        available_cash = portfolio.cash
        
        if required_cash > available_cash:
            msg = f"现金不足: 需要 {required_cash:.2f}, 可用 {available_cash:.2f}"
            self.record_violation(msg)
            return False, msg
        
        return True, ""
