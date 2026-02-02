"""策略假设模块"""

# 导入策略以触发注册
from dquant2.core.strategy.hypothesis.ma_cross import MACrossStrategy
from dquant2.core.strategy.hypothesis.rsi_strategy import RSIStrategy
from dquant2.core.strategy.hypothesis.macd_strategy import MACDStrategy
from dquant2.core.strategy.hypothesis.bollinger_strategy import BollingerBandStrategy
from dquant2.core.strategy.hypothesis.grid_trading import GridTradingStrategy
from dquant2.core.strategy.hypothesis.momentum_strategy import MomentumStrategy
from dquant2.core.strategy.hypothesis.mean_reversion import MeanReversionStrategy

__all__ = [
    "MACrossStrategy",
    "RSIStrategy", 
    "MACDStrategy",
    "BollingerBandStrategy",
    "GridTradingStrategy",
    "MomentumStrategy",
    "MeanReversionStrategy"
]
