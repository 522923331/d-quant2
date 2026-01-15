"""事件类型定义

所有事件类型都继承自 BaseEvent，确保统一的事件接口。

注意：为了避免dataclass继承的字段顺序问题，所有子类都重新声明timestamp字段
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class BaseEvent:
    """事件基类
    
    所有事件都应该包含时间戳和唯一ID，便于审计和追踪。
    """
    timestamp: datetime
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于序列化"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, pd.Series):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


@dataclass
class MarketDataEvent:
    """市场数据事件
    
    当新的市场数据到达时触发此事件。
    数据包含 OHLCV 信息。
    """
    timestamp: datetime
    symbol: str
    data: pd.Series  # 包含 open, high, low, close, volume 等字段
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """验证数据完整性"""
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        for field_name in required_fields:
            if field_name not in self.data.index:
                raise ValueError(f"MarketDataEvent 缺少必需字段: {field_name}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'data': self.data.to_dict(),
            'event_id': self.event_id
        }


@dataclass
class SignalEvent:
    """交易信号事件
    
    策略生成交易信号后触发此事件。
    """
    timestamp: datetime
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    strength: float   # 信号强度 0-1
    strategy_id: str  # 生成信号的策略ID
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外信息
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """验证信号参数"""
        if self.signal_type not in ['BUY', 'SELL', 'HOLD']:
            raise ValueError(f"无效的信号类型: {self.signal_type}")
        if not 0 <= self.strength <= 1:
            raise ValueError(f"信号强度必须在 0-1 之间: {self.strength}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'strength': self.strength,
            'strategy_id': self.strategy_id,
            'metadata': self.metadata,
            'event_id': self.event_id
        }


@dataclass
class OrderEvent:
    """订单事件
    
    当需要下单时触发此事件。
    """
    timestamp: datetime
    symbol: str
    order_type: str   # MARKET, LIMIT
    direction: str    # BUY, SELL
    quantity: int     # 数量（股数）
    price: Optional[float] = None  # 限价单需要价格
    strategy_id: str = ""  # 来源策略
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """验证订单参数"""
        if self.order_type not in ['MARKET', 'LIMIT']:
            raise ValueError(f"无效的订单类型: {self.order_type}")
        if self.direction not in ['BUY', 'SELL']:
            raise ValueError(f"无效的交易方向: {self.direction}")
        if self.quantity <= 0:
            raise ValueError(f"订单数量必须大于0: {self.quantity}")
        if self.order_type == 'LIMIT' and self.price is None:
            raise ValueError("限价单必须指定价格")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'order_type': self.order_type,
            'direction': self.direction,
            'quantity': self.quantity,
            'price': self.price,
            'strategy_id': self.strategy_id,
            'order_id': self.order_id,
            'event_id': self.event_id
        }


@dataclass
class FillEvent:
    """成交事件
    
    订单成交后触发此事件。
    """
    timestamp: datetime
    symbol: str
    quantity: int       # 成交数量
    price: float        # 成交价格
    commission: float   # 手续费
    direction: str      # BUY, SELL
    order_id: str       # 关联的订单ID
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """验证成交参数"""
        if self.direction not in ['BUY', 'SELL']:
            raise ValueError(f"无效的交易方向: {self.direction}")
        if self.quantity <= 0:
            raise ValueError(f"成交数量必须大于0: {self.quantity}")
        if self.price <= 0:
            raise ValueError(f"成交价格必须大于0: {self.price}")
        if self.commission < 0:
            raise ValueError(f"手续费不能为负: {self.commission}")
    
    @property
    def total_cost(self) -> float:
        """总成本（包含手续费）"""
        cost = self.quantity * self.price
        if self.direction == 'BUY':
            return cost + self.commission
        else:  # SELL
            return cost - self.commission
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'commission': self.commission,
            'direction': self.direction,
            'order_id': self.order_id,
            'fill_id': self.fill_id,
            'event_id': self.event_id
        }


@dataclass
class RiskEvent:
    """风控事件
    
    当触发风控规则时发出此事件。
    """
    timestamp: datetime
    risk_type: str  # POSITION_LIMIT, DRAWDOWN_LIMIT, VOLATILITY_ALERT, etc.
    severity: str   # INFO, WARNING, CRITICAL
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """验证风控事件参数"""
        if self.severity not in ['INFO', 'WARNING', 'CRITICAL']:
            raise ValueError(f"无效的严重级别: {self.severity}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'risk_type': self.risk_type,
            'severity': self.severity,
            'message': self.message,
            'metadata': self.metadata,
            'event_id': self.event_id
        }


@dataclass
class PerformanceEvent:
    """绩效事件
    
    定期发出的绩效统计事件。
    """
    timestamp: datetime
    portfolio_value: float
    cash: float
    positions_value: float
    pnl: float  # 盈亏
    metrics: Dict[str, Any] = field(default_factory=dict)  # 其他指标
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'positions_value': self.positions_value,
            'pnl': self.pnl,
            'metrics': self.metrics,
            'event_id': self.event_id
        }
