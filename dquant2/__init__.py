"""
d-quant2: 现代化量化回测系统

核心原则: 解耦 + 可插拔 + 可回测 + 可审计 + 易维护
"""

__version__ = "0.1.0"
__author__ = "d-quant2 Team"

from dquant2.backtest.engine import BacktestEngine
from dquant2.backtest.config import BacktestConfig
from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.event_bus.bus import EventBus
from dquant2.core.event_bus.events import (
    BaseEvent,
    MarketDataEvent,
    SignalEvent,
    OrderEvent,
    FillEvent,
)

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BaseStrategy",
    "EventBus",
    "BaseEvent",
    "MarketDataEvent",
    "SignalEvent",
    "OrderEvent",
    "FillEvent",
]
