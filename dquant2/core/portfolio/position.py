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
    avg_price: float      # 平均成本
    current_price: float = 0.0  # 当前价格
    last_update: datetime = None
    
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
    
    def add_quantity(self, quantity: int, price: float):
        """增加持仓"""
        total_cost = self.cost_basis + quantity * price
        self.quantity += quantity
        if self.quantity > 0:
            self.avg_price = total_cost / self.quantity
    
    def reduce_quantity(self, quantity: int, sell_price: float = None) -> float:
        """减少持仓，返回实现盈亏
        
        Args:
            quantity: 减少数量
            sell_price: 卖出价格，如果不提供则使用当前价格
            
        Returns:
            实现盈亏
        """
        if quantity > self.quantity:
            raise ValueError(f"卖出数量 {quantity} 超过持仓 {self.quantity}")
        
        # 使用提供的卖出价格或当前价格
        price = sell_price if sell_price is not None else self.current_price
        realized_pnl = quantity * (price - self.avg_price)
        self.quantity -= quantity
        
        return realized_pnl
