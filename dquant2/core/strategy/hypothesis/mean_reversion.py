"""均值回归策略

基于价格会回归均值的理论，当价格偏离均值过大时进行反向操作
"""

from typing import List
import logging
import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register('mean_reversion')
class MeanReversionStrategy(BaseStrategy):
    """均值回归策略
    
    原理:
    1. 计算价格的移动平均线作为均值
    2. 计算价格偏离均值的标准差
    3. 当价格低于均值-N倍标准差时买入（超卖）
    4. 当价格高于均值+N倍标准差时卖出（超买）
    5. 当价格回归到均值附近时平仓
    
    适用场景:
    - 震荡市场
    - 横盘整理
    - 波动率较高的市场
    - 缺乏明确趋势的市场
    
    参数:
        ma_period: 均线周期（天）
        std_period: 标准差计算周期（天）
        entry_std: 入场标准差倍数（如2表示偏离2个标准差）
        exit_std: 出场标准差倍数（如0.5表示回到0.5个标准差内）
        use_bollinger: 是否使用布林带（布林带是均值回归的一种）
    """
    
    def __init__(self, name: str = 'mean_reversion', params: dict = None):
        super().__init__(name, params or {})
        
        # 策略参数
        self.ma_period = self.get_param('ma_period', 20)  # 20日均线
        self.std_period = self.get_param('std_period', 20)  # 20日标准差
        self.entry_std = self.get_param('entry_std', 2.0)  # 2倍标准差入场
        self.exit_std = self.get_param('exit_std', 0.5)  # 0.5倍标准差出场
        self.use_bollinger = self.get_param('use_bollinger', False)  # 布林带模式
        
        # 持仓状态
        self.position = None  # None: 无持仓, 'LONG': 多头, 'SHORT': 空头
        self.entry_price = None  # 入场价格
        
        logger.info(
            f"均值回归策略初始化: 均线={self.ma_period}天, "
            f"入场={self.entry_std}σ, 出场={self.exit_std}σ"
        )
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据"""
        signals = []
        
        # 添加到数据缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的历史数据
        min_period = max(self.ma_period, self.std_period)
        if len(self.data_buffer) < min_period + 1:
            return signals
        
        # 获取数据DataFrame
        df = self.get_buffer_df()
        
        # 计算均值和标准差
        mean_value, std_value = self._calculate_mean_std(df)
        if mean_value is None or std_value is None:
            return signals
        
        current_price = float(event.data['close'])
        
        # 计算Z-score（价格偏离均值的标准差倍数）
        z_score = (current_price - mean_value) / std_value if std_value > 0 else 0
        
        # 生成交易信号
        if self.position is None:
            # 无持仓，检查入场条件
            
            # 价格大幅低于均值 -> 买入（预期价格会回归上涨）
            if z_score <= -self.entry_std:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=min(abs(z_score) / 3.0, 1.0),  # Z-score越大，信号越强
                    strategy_id=self.strategy_id,
                    metadata={'reason': f'价格低于均值{abs(z_score):.2f}σ (超卖)'}
                )
                signals.append(signal)
                self.position = 'LONG'
                self.entry_price = current_price
                logger.info(
                    f"买入信号: 价格={current_price:.2f}, 均值={mean_value:.2f}, "
                    f"Z-score={z_score:.2f}"
                )
            
            # 价格大幅高于均值 -> 做空（仅在支持做空的市场）
            # 在A股市场不支持做空，这里仅作为逻辑示例
            elif z_score >= self.entry_std and not self.use_bollinger:
                # 注意：A股不支持做空，这里的卖出信号实际不会生效
                logger.debug(
                    f"价格超买: 价格={current_price:.2f}, 均值={mean_value:.2f}, "
                    f"Z-score={z_score:.2f} (A股不支持做空，忽略)"
                )
        
        elif self.position == 'LONG':
            # 有多头持仓，检查出场条件
            
            # 条件1: 价格回归到均值附近
            if abs(z_score) <= self.exit_std:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=1.0,
                    strategy_id=self.strategy_id,
                    metadata={'reason': f'价格回归均值 (Z-score={z_score:.2f})'}
                )
                signals.append(signal)
                profit_pct = (current_price - self.entry_price) / self.entry_price * 100
                self.position = None
                self.entry_price = None
                logger.info(
                    f"卖出信号(回归): 价格={current_price:.2f}, 均值={mean_value:.2f}, "
                    f"Z-score={z_score:.2f}, 盈亏={profit_pct:.2f}%"
                )
            
            # 条件2: 价格继续下跌到新的低点（止损）
            elif z_score <= -(self.entry_std + 1.0):
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=1.0,
                    strategy_id=self.strategy_id,
                    metadata={'reason': f'价格继续偏离，止损 (Z-score={z_score:.2f})'}
                )
                signals.append(signal)
                profit_pct = (current_price - self.entry_price) / self.entry_price * 100
                self.position = None
                self.entry_price = None
                logger.warning(
                    f"卖出信号(止损): 价格={current_price:.2f}, 均值={mean_value:.2f}, "
                    f"Z-score={z_score:.2f}, 盈亏={profit_pct:.2f}%"
                )
        
        return signals
    
    def _calculate_mean_std(self, df: pd.DataFrame):
        """计算均值和标准差
        
        Returns:
            (均值, 标准差)
        """
        if len(df) < max(self.ma_period, self.std_period):
            return None, None
        
        # 计算移动平均
        ma = df['close'].rolling(window=self.ma_period).mean().iloc[-1]
        
        # 计算标准差
        std = df['close'].rolling(window=self.std_period).std().iloc[-1]
        
        return float(ma), float(std)
    
    def on_stop(self):
        """策略停止"""
        position_str = {
            None: '无持仓',
            'LONG': '多头',
            'SHORT': '空头'
        }.get(self.position, '未知')
        
        logger.info(f"均值回归策略停止，最终持仓: {position_str}")
        if self.entry_price:
            logger.info(f"入场价格: {self.entry_price:.2f}")
        
        super().on_stop()
