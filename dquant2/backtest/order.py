"""订单类型定义

提供多种订单类型：市价单、限价单、止损单、止盈单
参考: QuantOL 回测架构
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "MARKET"          # 市价单
    LIMIT = "LIMIT"            # 限价单
    STOP = "STOP"              # 止损单
    STOP_LIMIT = "STOP_LIMIT"  # 止损限价单


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "PENDING"        # 待执行
    PARTIAL = "PARTIAL"        # 部分成交
    FILLED = "FILLED"          # 已成交
    CANCELLED = "CANCELLED"    # 已取消
    REJECTED = "REJECTED"      # 已拒绝


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """订单类
    
    支持多种订单类型的统一订单对象
    """
    
    symbol: str                        # 股票代码
    quantity: float                    # 数量
    side: OrderSide                    # 方向（买/卖）
    order_type: OrderType = OrderType.MARKET  # 订单类型
    
    # 价格相关
    limit_price: Optional[float] = None     # 限价
    stop_price: Optional[float] = None      # 止损价
    
    # 状态相关
    status: OrderStatus = OrderStatus.PENDING  # 订单状态
    filled_quantity: float = 0.0        # 已成交数量
    avg_fill_price: float = 0.0        # 平均成交价格
    
    # 时间相关
    created_at: Optional[datetime] = None    # 创建时间
    updated_at: Optional[datetime] = None    # 更新时间
    filled_at: Optional[datetime] = None     # 成交时间
    
    # 标识
    order_id: str = None               # 订单ID
    strategy_id: Optional[str] = None  # 策略ID
    
    # 其他
    notes: str = ""                    # 备注
    
    def __post_init__(self):
        """初始化后处理"""
        if self.order_id is None:
            self.order_id = str(uuid.uuid4())
        
        if self.created_at is None:
            self.created_at = datetime.now()
        
        self.updated_at = self.created_at
    
    @property
    def remaining_quantity(self) -> float:
        """剩余未成交数量"""
        return self.quantity - self.filled_quantity
    
    @property
    def is_complete(self) -> bool:
        """是否完全成交"""
        return self.filled_quantity >= self.quantity
    
    @property
    def fill_ratio(self) -> float:
        """成交比例"""
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity
    
    def update_fill(self, fill_quantity: float, fill_price: float):
        """更新成交信息
        
        Args:
            fill_quantity: 成交数量
            fill_price: 成交价格
        """
        # 更新已成交数量
        old_filled = self.filled_quantity
        self.filled_quantity += fill_quantity
        
        # 更新平均成交价格
        if self.filled_quantity > 0:
            total_value = old_filled * self.avg_fill_price + fill_quantity * fill_price
            self.avg_fill_price = total_value / self.filled_quantity
        
        # 更新状态
        if self.is_complete:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.now()
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIAL
        
        self.updated_at = datetime.now()
    
    def cancel(self):
        """取消订单"""
        if self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now()
        return True
    
    def reject(self, reason: str = ""):
        """拒绝订单
        
        Args:
            reason: 拒绝原因
        """
        self.status = OrderStatus.REJECTED
        self.notes = reason
        self.updated_at = datetime.now()
    
    def can_execute_at_price(self, current_price: float) -> bool:
        """判断在当前价格是否可以执行
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否可以执行
        """
        if self.status != OrderStatus.PENDING:
            return False
        
        if self.order_type == OrderType.MARKET:
            return True
        
        elif self.order_type == OrderType.LIMIT:
            if self.limit_price is None:
                return False
            
            # 买入：当前价 <= 限价
            # 卖出：当前价 >= 限价
            if self.side == OrderSide.BUY:
                return current_price <= self.limit_price
            else:
                return current_price >= self.limit_price
        
        elif self.order_type == OrderType.STOP:
            if self.stop_price is None:
                return False
            
            # 买入：当前价 >= 止损价（突破买入）
            # 卖出：当前价 <= 止损价（跌破卖出）
            if self.side == OrderSide.BUY:
                return current_price >= self.stop_price
            else:
                return current_price <= self.stop_price
        
        elif self.order_type == OrderType.STOP_LIMIT:
            if self.stop_price is None or self.limit_price is None:
                return False
            
            # 先检查止损价触发
            if self.side == OrderSide.BUY:
                if current_price < self.stop_price:
                    return False
                return current_price <= self.limit_price
            else:
                if current_price > self.stop_price:
                    return False
                return current_price >= self.limit_price
        
        return False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'order_type': self.order_type.value if isinstance(self.order_type, OrderType) else self.order_type,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value if isinstance(self.status, OrderStatus) else self.status,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'strategy_id': self.strategy_id,
            'notes': self.notes
        }
    
    def __repr__(self):
        return (
            f"Order({self.order_type.value if isinstance(self.order_type, OrderType) else self.order_type} "
            f"{self.side.value if isinstance(self.side, OrderSide) else self.side} "
            f"{self.symbol} {self.quantity}@"
            f"{self.limit_price or self.stop_price or 'MKT'})"
        )
