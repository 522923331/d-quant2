"""回测模块"""

from dquant2.backtest.engine import BacktestEngine
from dquant2.backtest.config import BacktestConfig
from dquant2.backtest.metrics import PerformanceMetrics
from dquant2.backtest.order import Order, OrderType, OrderStatus, OrderSide
from dquant2.backtest.slippage import (
    SlippageModel,
    FixedSlippage,
    RatioSlippage,
    TickSlippage,
    DynamicSlippage,
    SlippageFactory
)
from dquant2.backtest.optimizer import (
    ParameterOptimizer,
    GridSearchOptimizer,
    RandomSearchOptimizer,
    optimize_strategy_params
)

__all__ = [
    "BacktestEngine", 
    "BacktestConfig", 
    "PerformanceMetrics",
    "Order",
    "OrderType",
    "OrderStatus",
    "OrderSide",
    "SlippageModel",
    "FixedSlippage",
    "RatioSlippage",
    "TickSlippage",
    "DynamicSlippage",
    "SlippageFactory",
    "ParameterOptimizer",
    "GridSearchOptimizer",
    "RandomSearchOptimizer",
    "optimize_strategy_params"
]
