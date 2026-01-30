"""策略假设模块"""

# 导入策略以触发注册
from dquant2.core.strategy.hypothesis.ma_cross import MACrossStrategy
from dquant2.core.strategy.hypothesis.rsi_strategy import RSIStrategy
from dquant2.core.strategy.hypothesis.macd_strategy import MACDStrategy
from dquant2.core.strategy.hypothesis.bollinger_strategy import BollingerBandStrategy

__all__ = [
    "MACrossStrategy",
    "RSIStrategy", 
    "MACDStrategy",
    "BollingerBandStrategy"
]
