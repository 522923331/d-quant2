"""RSI策略

基于相对强弱指标的策略：
- RSI低于超卖线（默认30）：买入信号
- RSI高于超买线（默认70）：卖出信号
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register("rsi")
class RSIStrategy(BaseStrategy):
    """RSI策略
    
    参数：
        period: RSI周期，默认14
        oversold: 超卖线，默认30
        overbought: 超买线，默认70
    """
    
    def __init__(self, name: str = "RSI", params: dict = None):
        super().__init__(name, params)
        
        # 策略参数
        self.period = self.get_param('period', 14)
        self.oversold = self.get_param('oversold', 30)
        self.overbought = self.get_param('overbought', 70)
        
        # 内部状态
        self.last_signal = None
        self.in_position = False
        
        logger.info(
            f"RSI策略初始化: period={self.period}, "
            f"oversold={self.oversold}, overbought={self.overbought}"
        )
    
    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理数据并生成信号"""
        # 添加数据到缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的数据才能计算RSI
        if len(self.data_buffer) < self.period + 2:
            return []
        
        # 获取历史数据
        df = self.get_buffer_df()
        
        # 计算RSI
        rsi = self._calculate_rsi(df['close'])
        
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2] if len(rsi) >= 2 else None
        
        if pd.isna(current_rsi) or prev_rsi is None or pd.isna(prev_rsi):
            return []
        
        signals = []
        
        # RSI从超卖区域回升：买入信号
        if prev_rsi < self.oversold and current_rsi >= self.oversold:
            if not self.in_position:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=1.0 - (current_rsi / 100),  # RSI越低信号越强
                    strategy_id=self.strategy_id,
                    metadata={
                        'rsi': current_rsi,
                        'prev_rsi': prev_rsi,
                        'reason': f'RSI从超卖区回升({prev_rsi:.1f}->{current_rsi:.1f})'
                    }
                )
                signals.append(signal)
                self.in_position = True
                self.last_signal = 'BUY'
                logger.info(f"RSI买入信号: {event.symbol} @ {event.timestamp}, RSI={current_rsi:.1f}")
        
        # RSI从超买区域回落：卖出信号
        elif prev_rsi > self.overbought and current_rsi <= self.overbought:
            if self.in_position:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=current_rsi / 100,  # RSI越高信号越强
                    strategy_id=self.strategy_id,
                    metadata={
                        'rsi': current_rsi,
                        'prev_rsi': prev_rsi,
                        'reason': f'RSI从超买区回落({prev_rsi:.1f}->{current_rsi:.1f})'
                    }
                )
                signals.append(signal)
                self.in_position = False
                self.last_signal = 'SELL'
                logger.info(f"RSI卖出信号: {event.symbol} @ {event.timestamp}, RSI={current_rsi:.1f}")
        
        return signals
