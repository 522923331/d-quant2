"""持仓类"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """持仓信息
    
    记录单个股票的持仓详情
    """
    symbol: str           # 股票代码
    quantity: int         # 持仓数量
    available_quantity: int = 0  # 可用数量（T+1模式下当天买入不可用）
    avg_price: float = 0.0      # 平均成本
    current_price: float = 0.0  # 当前价格
    last_update: datetime = None
    is_t0_mode: bool = False  # 是否为T+0模式（ETF、期权等）
    
    @property
    def market_value(self) -> float:
        """市值"""
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        """成本"""
        return self.quantity * self.avg_price
    
    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏"""
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """未实现盈亏百分比"""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis
    
    def update_price(self, price: float, timestamp: datetime = None):
        """更新价格"""
        self.current_price = price
        if timestamp:
            self.last_update = timestamp
    
    def add_quantity(self, quantity: int, price:  float):
        """增加持仓
        
        T+0模式：当天买入立即可用
        T+1模式：当天买入次日可用
        """
        total_cost = self.cost_basis + quantity * price
        self.quantity += quantity
        
        # T+0模式下，当天买入立即可用
        if self.is_t0_mode:
            self.available_quantity += quantity
        # T+1模式下，当天买入不可用（需要在下一交易日解锁）
        # available_quantity 不变
        
        if self.quantity > 0:
            self.avg_price = total_cost / self.quantity
    
    def reduce_quantity(self, quantity: int, sell_price: float = None) -> float:
        """减少持仓，返回实现盈亏
        
        严格检查可用数量，防止T+1模式下当天买入当天卖出
        
        Args:
            quantity: 减少数量
            sell_price: 卖出价格，如果不提供则使用当前价格
            
        Returns:
            实现盈亏
        """
        # 检查持仓数量
        if quantity > self.quantity:
            raise ValueError(f"卖出数量 {quantity} 超过持仓 {self.quantity}")
        
        # 检查可用数量（T+1模式下极为重要）
        if quantity > self.available_quantity:
            raise ValueError(
                f"卖出数量 {quantity} 超过可用数量 {self.available_quantity} "
                f"(模式: {'T+0' if self.is_t0_mode else 'T+1'})"
            )
        
        # 使用提供的卖出价格或当前价格
        price = sell_price if sell_price is not None else self.current_price
        realized_pnl = quantity * (price - self.avg_price)
        
        # 同时减少总持仓和可用持仓
        self.quantity -= quantity
        self.available_quantity -= quantity
        
        return realized_pnl
    
    def unlock_available(self, quantity: int = None):
        """解锁可用数量（T+1模式下，下一交易日执行）
        
        Args:
            quantity: 解锁数量，不指定则全部解锁
        """
        if quantity is None:
            self.available_quantity = self.quantity
        else:
            self.available_quantity = min(
                self.available_quantity + quantity,
                self.quantity
            )
