"""双均线+RSI组合策略

这是一个示例自定义策略，结合了双均线和RSI指标：
- 快线上穿慢线 + RSI < 70：买入信号
- 快线下穿慢线 + RSI > 30：卖出信号
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


STRATEGY_NAME = "ma_rsi_combo"

@StrategyFactory.register(STRATEGY_NAME)
class MARSIComboStrategy(BaseStrategy):
    """双均线+RSI组合策略
    
    结合均线交叉和RSI过滤，减少假信号
    """
    
    STRATEGY_PARAMS = {
        'fast_period': {
            'name': '快线周期',
            'type': 'int',
            'default': 5,
            'min': 3,
            'max': 20,
            'step': 1,
            'help': '短期移动平均线周期'
        },
        'slow_period': {
            'name': '慢线周期',
            'type': 'int',
            'default': 20,
            'min': 10,
            'max': 60,
            'step': 5,
            'help': '长期移动平均线周期'
        },
        'rsi_period': {
            'name': 'RSI周期',
            'type': 'int',
            'default': 14,
            'min': 7,
            'max': 21,
            'step': 1,
            'help': 'RSI指标计算周期'
        },
        'rsi_overbought': {
            'name': 'RSI超买线',
            'type': 'int',
            'default': 70,
            'min': 60,
            'max': 80,
            'step': 5,
            'help': 'RSI超买阈值，高于此值不买入'
        },
        'rsi_oversold': {
            'name': 'RSI超卖线',
            'type': 'int',
            'default': 30,
            'min': 20,
            'max': 40,
            'step': 5,
            'help': 'RSI超卖阈值，低于此值不卖出'
        }
    }
    
    def __init__(self, name: str = "MA_RSI_Combo", params: dict = None):
        super().__init__(name, params)
        
        self.fast_period = self.get_param('fast_period', 5)
        self.slow_period = self.get_param('slow_period', 20)
        self.rsi_period = self.get_param('rsi_period', 14)
        self.rsi_overbought = self.get_param('rsi_overbought', 70)
        self.rsi_oversold = self.get_param('rsi_oversold', 30)
        
        self.last_signal = None
        self.in_position = False
        
        logger.info(
            f"MA+RSI组合策略初始化: fast={self.fast_period}, slow={self.slow_period}, "
            f"rsi={self.rsi_period}"
        )
    
    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """计算RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据并生成交易信号"""
        self._add_to_buffer(event.data)
        
        min_periods = max(self.slow_period, self.rsi_period) + 2
        if len(self.data_buffer) < min_periods:
            return []
        
        df = self.get_buffer_df()
        
        # 计算均线
        fast_ma = df['close'].rolling(window=self.fast_period).mean()
        slow_ma = df['close'].rolling(window=self.slow_period).mean()
        
        # 计算RSI
        rsi = self._calculate_rsi(df['close'])
        
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        current_rsi = rsi.iloc[-1]
        
        if pd.isna(current_fast) or pd.isna(current_rsi):
            return []
        
        signals = []
        
        # 金叉 + RSI未超买：买入
        if prev_fast <= prev_slow and current_fast > current_slow:
            if current_rsi < self.rsi_overbought and not self.in_position:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=1.0 - (current_rsi / 100),
                    strategy_id=self.strategy_id,
                    metadata={
                        'fast_ma': current_fast,
                        'slow_ma': current_slow,
                        'rsi': current_rsi,
                        'reason': f'金叉+RSI={current_rsi:.1f}<{self.rsi_overbought}'
                    }
                )
                signals.append(signal)
                self.in_position = True
                self.last_signal = 'BUY'
                logger.info(f"买入信号: {event.symbol}, RSI={current_rsi:.1f}")
        
        # 死叉 + RSI未超卖：卖出
        elif prev_fast >= prev_slow and current_fast < current_slow:
            if current_rsi > self.rsi_oversold and self.in_position:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=current_rsi / 100,
                    strategy_id=self.strategy_id,
                    metadata={
                        'fast_ma': current_fast,
                        'slow_ma': current_slow,
                        'rsi': current_rsi,
                        'reason': f'死叉+RSI={current_rsi:.1f}>{self.rsi_oversold}'
                    }
                )
                signals.append(signal)
                self.in_position = False
                self.last_signal = 'SELL'
                logger.info(f"卖出信号: {event.symbol}, RSI={current_rsi:.1f}")
        
        return signals


STRATEGY_METADATA = {
    'name': STRATEGY_NAME,
    'display_name': '双均线+RSI组合',
    'description': '结合均线交叉和RSI过滤的组合策略，通过RSI过滤假信号',
    'author': 'd-quant2',
    'version': '1.0.0',
    'params': MARSIComboStrategy.STRATEGY_PARAMS
}
