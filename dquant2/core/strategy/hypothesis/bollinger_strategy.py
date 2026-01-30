"""布林带策略

基于布林带的策略：
- 价格触及下轨：买入信号
- 价格触及上轨：卖出信号
- 可选：布林带收窄后突破
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register("bollinger")
class BollingerBandStrategy(BaseStrategy):
    """布林带策略
    
    参数：
        period: 均线周期，默认20
        std_dev: 标准差倍数，默认2.0
        use_squeeze: 是否使用布林带收窄策略，默认False
    """
    
    def __init__(self, name: str = "Bollinger", params: dict = None):
        super().__init__(name, params)
        
        # 策略参数
        self.period = self.get_param('period', 20)
        self.std_dev = self.get_param('std_dev', 2.0)
        self.use_squeeze = self.get_param('use_squeeze', False)
        
        # 内部状态
        self.last_signal = None
        self.in_position = False
        
        logger.info(
            f"布林带策略初始化: period={self.period}, std_dev={self.std_dev}"
        )
    
    def _calculate_bollinger(self, prices: pd.Series) -> tuple:
        """计算布林带指标
        
        Returns:
            (middle_band, upper_band, lower_band, bandwidth)
        """
        # 中轨 = 移动平均线
        middle_band = prices.rolling(window=self.period).mean()
        
        # 标准差
        std = prices.rolling(window=self.period).std()
        
        # 上轨 = 中轨 + N倍标准差
        upper_band = middle_band + (std * self.std_dev)
        
        # 下轨 = 中轨 - N倍标准差
        lower_band = middle_band - (std * self.std_dev)
        
        # 带宽 = (上轨 - 下轨) / 中轨
        bandwidth = (upper_band - lower_band) / middle_band
        
        return middle_band, upper_band, lower_band, bandwidth
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理数据并生成信号"""
        # 添加数据到缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的数据才能计算布林带
        if len(self.data_buffer) < self.period + 2:
            return []
        
        # 获取历史数据
        df = self.get_buffer_df()
        
        # 计算布林带
        middle, upper, lower, bandwidth = self._calculate_bollinger(df['close'])
        
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_middle = middle.iloc[-1]
        prev_upper = upper.iloc[-2]
        prev_lower = lower.iloc[-2]
        
        if pd.isna(current_upper) or pd.isna(current_lower):
            return []
        
        signals = []
        
        # 价格从下轨反弹：买入信号
        if prev_price <= prev_lower and current_price > current_lower:
            if not self.in_position:
                # 计算与下轨的距离作为信号强度
                distance_pct = (current_middle - current_price) / (current_middle - current_lower)
                strength = min(max(distance_pct, 0.5), 1.0)
                
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=strength,
                    strategy_id=self.strategy_id,
                    metadata={
                        'price': current_price,
                        'lower_band': current_lower,
                        'middle_band': current_middle,
                        'upper_band': current_upper,
                        'bandwidth': bandwidth.iloc[-1],
                        'reason': '价格触及布林带下轨反弹'
                    }
                )
                signals.append(signal)
                self.in_position = True
                self.last_signal = 'BUY'
                logger.info(f"布林带买入信号: {event.symbol} @ {event.timestamp}, 价格={current_price:.2f}")
        
        # 价格触及上轨回落：卖出信号
        elif prev_price >= prev_upper and current_price < current_upper:
            if self.in_position:
                distance_pct = (current_price - current_middle) / (current_upper - current_middle)
                strength = min(max(distance_pct, 0.5), 1.0)
                
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=strength,
                    strategy_id=self.strategy_id,
                    metadata={
                        'price': current_price,
                        'lower_band': current_lower,
                        'middle_band': current_middle,
                        'upper_band': current_upper,
                        'bandwidth': bandwidth.iloc[-1],
                        'reason': '价格触及布林带上轨回落'
                    }
                )
                signals.append(signal)
                self.in_position = False
                self.last_signal = 'SELL'
                logger.info(f"布林带卖出信号: {event.symbol} @ {event.timestamp}, 价格={current_price:.2f}")
        
        # 价格跌破中轨：止损卖出
        elif self.in_position and prev_price >= prev_lower and current_price < current_middle:
            # 如果持仓且价格跌破中轨，考虑止损
            if current_price < current_middle * 0.98:  # 跌破中轨2%
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=0.8,
                    strategy_id=self.strategy_id,
                    metadata={
                        'price': current_price,
                        'middle_band': current_middle,
                        'reason': '价格跌破中轨止损'
                    }
                )
                signals.append(signal)
                self.in_position = False
                self.last_signal = 'SELL'
                logger.info(f"布林带止损信号: {event.symbol} @ {event.timestamp}")
        
        return signals
