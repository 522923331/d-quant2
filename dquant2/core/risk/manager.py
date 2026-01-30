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


class StopLossControl(BaseRiskControl):
    """止损控制
    
    当持仓亏损达到指定比例时触发止损
    """
    
    def __init__(self, stop_loss_pct: float = 0.05):
        """初始化止损控制
        
        Args:
            stop_loss_pct: 止损比例，默认5%
        """
        super().__init__("StopLoss")
        self.stop_loss_pct = stop_loss_pct
    
    def check(self, order: OrderEvent, portfolio) -> tuple:
        # 止损控制主要用于检查现有持仓是否需要平仓
        # 这里只是拦截买入订单以防止在亏损状态下加仓
        if order.direction != 'BUY':
            return True, ""
        
        # 检查该标的是否有持仓且正在亏损
        position = portfolio.get_position(order.symbol)
        if position and position.quantity > 0:
            loss_pct = position.unrealized_pnl_pct
            if loss_pct < -self.stop_loss_pct:
                msg = f"持仓亏损 {loss_pct:.2%} 超过止损线 {-self.stop_loss_pct:.2%}，禁止加仓"
                self.record_violation(msg)
                return False, msg
        
        return True, ""
    
    def should_close_position(self, position) -> bool:
        """判断是否应该平仓止损
        
        Args:
            position: Position对象
            
        Returns:
            是否应该止损平仓
        """
        if position and position.quantity > 0:
            return position.unrealized_pnl_pct < -self.stop_loss_pct
        return False


class TakeProfitControl(BaseRiskControl):
    """止盈控制
    
    当持仓盈利达到指定比例时提示止盈
    """
    
    def __init__(self, take_profit_pct: float = 0.15):
        """初始化止盈控制
        
        Args:
            take_profit_pct: 止盈比例，默认15%
        """
        super().__init__("TakeProfit")
        self.take_profit_pct = take_profit_pct
    
    def check(self, order: OrderEvent, portfolio) -> tuple:
        # 止盈控制不拦截订单，只记录提示
        return True, ""
    
    def should_close_position(self, position) -> bool:
        """判断是否应该止盈平仓
        
        Args:
            position: Position对象
            
        Returns:
            是否应该止盈平仓
        """
        if position and position.quantity > 0:
            return position.unrealized_pnl_pct > self.take_profit_pct
        return False


class MaxDrawdownControl(BaseRiskControl):
    """最大回撤控制
    
    当组合回撤超过指定比例时停止交易
    """
    
    def __init__(self, max_drawdown_pct: float = 0.20):
        """初始化最大回撤控制
        
        Args:
            max_drawdown_pct: 最大回撤比例，默认20%
        """
        super().__init__("MaxDrawdown")
        self.max_drawdown_pct = max_drawdown_pct
        self.peak_value = 0.0
    
    def check(self, order: OrderEvent, portfolio) -> tuple:
        current_value = portfolio.get_total_value()
        
        # 更新峰值
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        # 计算回撤
        if self.peak_value > 0:
            drawdown = (self.peak_value - current_value) / self.peak_value
            
            if drawdown > self.max_drawdown_pct:
                msg = f"当前回撤 {drawdown:.2%} 超过最大限制 {self.max_drawdown_pct:.2%}，禁止开新仓"
                self.record_violation(msg)
                if order.direction == 'BUY':
                    return False, msg
        
        return True, ""

