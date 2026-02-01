"""使用 MyTT 指标库的双均线RSI策略

演示如何使用 MyTT 技术指标库编写策略
相比原来的策略，代码更简洁、更符合通达信语法习惯
"""

from typing import List, Dict
import pandas as pd

from dquant2.core.strategy import Strategy
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent
from dquant2.indicators import MA, RSI, CROSS  # 使用 MyTT 指标


class MAandRSIStrategy(Strategy):
    """双均线 + RSI 过滤策略（使用MyTT）
    
    策略逻辑：
    1. 买入信号：MA5 金叉 MA20 且 RSI > 30 (避免超卖)
    2. 卖出信号：MA5死叉 MA20 或 RSI > 80 (超买)
    
    优势：
    - 使用 MyTT 库，代码更简洁
    - 完全兼容通达信语法
    - 指标计算高效（NumPy实现）
    """
    
    def __init__(self, fast_period: int = 5, slow_period: int = 20, 
                 rsi_period: int = 14, rsi_oversold: int = 30, 
                 rsi_overbought: int = 80):
        """初始化策略
        
        Args:
            fast_period: 快线周期（默认5）
            slow_period: 慢线周期（默认20）
            rsi_period: RSI周期（默认14）
            rsi_oversold: RSI超卖线（默认30）
            rsi_overbought: RSI超买线（默认80）
        """
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # 历史数据缓存（用于计算指标）
        self.price_history = []
        self.min_bars = max(slow_period, rsi_period) + 10  # 至少需要的bar数
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据，生成交易信号
        
        使用 MyTT 库计算指标，语法简洁
        """
        signals = []
        
        # 更新价格历史
        close_price = event.data['close']
        self.price_history.append(close_price)
        
        # 保持合适的历史长度
        if len(self.price_history) > self.min_bars * 2:
            self.price_history = self.price_history[-self.min_bars * 2:]
        
        # 至少需要足够的数据才开始计算
        if len(self.price_history) < self.min_bars:
            return signals
        
        # === 使用 MyTT 计算指标（简洁！） ===
        import numpy as np
        closes = np.array(self.price_history)
        
        # 计算移动平均线
        ma_fast = MA(closes, self.fast_period)
        ma_slow = MA(closes, self.slow_period)
        
        # 计算RSI
        rsi = RSI(closes, self.rsi_period)
        
        # 使用 CROSS 函数判断金叉死叉
        golden_cross = CROSS(ma_fast, ma_slow)[-1]  # 快线上穿慢线
        death_cross = CROSS(ma_slow, ma_fast)[-1]   # 慢线上穿快线
        
        # 获取最新值
        rsi_value = rsi[-1]
        
        # === 生成交易信号 ===
        
        # 买入条件：金叉 且 RSI不在超卖区
        if golden_cross == 1 and rsi_value > self.rsi_oversold:
            signal = SignalEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                signal_type='BUY',
                strategy_id=self.name,
                reason=f'MA{self.fast_period}金叉MA{self.slow_period}, RSI={rsi_value:.1f}'
            )
            signals.append(signal)
        
        # 卖出条件：死叉 或 RSI进入超买区
        elif death_cross == 1 or rsi_value > self.rsi_overbought:
            reason = f'MA{self.fast_period}死叉MA{self.slow_period}' if death_cross == 1 \
                else f'RSI超买({rsi_value:.1f}>{self.rsi_overbought})'
            
            signal = SignalEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                signal_type='SELL',
                strategy_id=self.name,
                reason=reason
            )
            signals.append(signal)
        
        return signals
    
    def on_start(self):
        """策略启动"""
        print(f"启动策略: {self.name}")
        print(f"参数: MA{self.fast_period}/{self.slow_period}, "
              f"RSI{self.rsi_period}({self.rsi_oversold},{self.rsi_overbought})")
    
    def on_stop(self):
        """策略停止"""
        print(f"停止策略: {self.name}")


# 注册策略到工厂
from dquant2.core.strategy import StrategyFactory
StrategyFactory.register('ma_rsi_mytt', MAandRSIStrategy)
