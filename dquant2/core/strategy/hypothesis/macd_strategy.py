"""MACD策略

基于MACD指标的策略：
- MACD线上穿信号线（金叉）：买入信号
- MACD线下穿信号线（死叉）：卖出信号
- 可选：只在零轴上方做多，零轴下方做空
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register("macd")
class MACDStrategy(BaseStrategy):
    """MACD策略
    
    参数：
        fast_period: 快线EMA周期，默认12
        slow_period: 慢线EMA周期，默认26
        signal_period: 信号线周期，默认9
        use_histogram: 是否使用柱状图判断，默认False
    """
    
    def __init__(self, name: str = "MACD", params: dict = None):
        super().__init__(name, params)
        
        # 策略参数
        self.fast_period = self.get_param('fast_period', 12)
        self.slow_period = self.get_param('slow_period', 26)
        self.signal_period = self.get_param('signal_period', 9)
        self.use_histogram = self.get_param('use_histogram', False)
        
        # 内部状态
        self.last_signal = None
        self.in_position = False
        
        logger.info(
            f"MACD策略初始化: fast={self.fast_period}, slow={self.slow_period}, "
            f"signal={self.signal_period}"
        )
    
    def _calculate_macd(self, prices: pd.Series) -> tuple:
        """计算MACD指标
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        # 计算EMA
        ema_fast = prices.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=self.slow_period, adjust=False).mean()
        
        # MACD线 = 快线 - 慢线
        macd_line = ema_fast - ema_slow
        
        # 信号线 = MACD的EMA
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        
        # 柱状图 = MACD - 信号线
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理数据并生成信号"""
        # 添加数据到缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的数据才能计算MACD
        min_periods = self.slow_period + self.signal_period
        if len(self.data_buffer) < min_periods:
            return []
        
        # 获取历史数据
        df = self.get_buffer_df()
        
        # 计算MACD
        macd_line, signal_line, histogram = self._calculate_macd(df['close'])
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        prev_macd = macd_line.iloc[-2] if len(macd_line) >= 2 else None
        prev_signal = signal_line.iloc[-2] if len(signal_line) >= 2 else None
        
        if prev_macd is None or prev_signal is None:
            return []
        
        signals = []
        
        # 金叉：MACD线上穿信号线
        if prev_macd <= prev_signal and current_macd > current_signal:
            if not self.in_position:
                # 计算信号强度（基于柱状图增长速度）
                strength = min(abs(histogram.iloc[-1] - histogram.iloc[-2]) * 100, 1.0)
                
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=strength,
                    strategy_id=self.strategy_id,
                    metadata={
                        'macd': current_macd,
                        'signal': current_signal,
                        'histogram': histogram.iloc[-1],
                        'reason': 'MACD金叉'
                    }
                )
                signals.append(signal)
                self.in_position = True
                self.last_signal = 'BUY'
                logger.info(f"MACD金叉信号: {event.symbol} @ {event.timestamp}")
        
        # 死叉：MACD线下穿信号线
        elif prev_macd >= prev_signal and current_macd < current_signal:
            if self.in_position:
                strength = min(abs(histogram.iloc[-1] - histogram.iloc[-2]) * 100, 1.0)
                
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=strength,
                    strategy_id=self.strategy_id,
                    metadata={
                        'macd': current_macd,
                        'signal': current_signal,
                        'histogram': histogram.iloc[-1],
                        'reason': 'MACD死叉'
                    }
                )
                signals.append(signal)
                self.in_position = False
                self.last_signal = 'SELL'
                logger.info(f"MACD死叉信号: {event.symbol} @ {event.timestamp}")
        
        return signals
