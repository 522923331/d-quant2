"""双均线交叉策略

经典的技术分析策略：
- 短期均线上穿长期均线：买入信号
- 短期均线下穿长期均线：卖出信号
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register("ma_cross")
class MACrossStrategy(BaseStrategy):
    """双均线交叉策略
    
    参数：
        fast_period: 快线周期，默认5
        slow_period: 慢线周期，默认20
    """
    
    def __init__(self, name: str = "MACross", params: dict = None):
        super().__init__(name, params)
        
        # 策略参数
        self.fast_period = self.get_param('fast_period', 5)
        self.slow_period = self.get_param('slow_period', 20)
        
        # 内部状态
        self.last_signal = None  # 上次信号类型
        
        logger.info(
            f"双均线策略初始化: fast={self.fast_period}, slow={self.slow_period}"
        )
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理数据并生成信号"""
        # 添加数据到缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的数据才能计算均线
        if len(self.data_buffer) < self.slow_period:
            return []
        
        # 获取历史数据
        df = self.get_buffer_df()
        
        # 计算均线
        fast_ma = df['close'].rolling(window=self.fast_period).mean()
        slow_ma = df['close'].rolling(window=self.slow_period).mean()
        
        # 获取最新的均线值
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2] if len(fast_ma) >= 2 else None
        prev_slow = slow_ma.iloc[-2] if len(slow_ma) >= 2 else None
        
        # 检测交叉
        signals = []
        
        if prev_fast is not None and prev_slow is not None:
            # 金叉：快线上穿慢线
            if prev_fast <= prev_slow and current_fast > current_slow:
                if self.last_signal != 'BUY':
                    signal = SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type='BUY',
                        strength=1.0,
                        strategy_id=self.strategy_id,
                        metadata={
                            'fast_ma': current_fast,
                            'slow_ma': current_slow,
                            'reason': '金叉'
                        }
                    )
                    signals.append(signal)
                    self.last_signal = 'BUY'
                    logger.info(f"金叉信号: {event.symbol} @ {event.timestamp}")
            
            # 死叉：快线下穿慢线
            elif prev_fast >= prev_slow and current_fast < current_slow:
                if self.last_signal != 'SELL':
                    signal = SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type='SELL',
                        strength=1.0,
                        strategy_id=self.strategy_id,
                        metadata={
                            'fast_ma': current_fast,
                            'slow_ma': current_slow,
                            'reason': '死叉'
                        }
                    )
                    signals.append(signal)
                    self.last_signal = 'SELL'
                    logger.info(f"死叉信号: {event.symbol} @ {event.timestamp}")
        
        return signals
