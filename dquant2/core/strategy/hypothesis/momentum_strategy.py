"""动量策略

追随强势趋势，买入涨势强劲的股票，卖出跌势明显的股票
"""

from typing import List
import logging
import pandas as pd

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register('momentum')
class MomentumStrategy(BaseStrategy):
    """动量策略
    
    原理:
    1. 计算价格动量（ROC - Rate of Change）
    2. 当动量超过阈值时买入（看涨动量）
    3. 当动量低于阈值时卖出（看跌动量）
    4. 可结合成交量放大确认信号
    
    适用场景:
    - 趋势明显的市场
    - 牛市或熊市
    - 突破后的连续走势
    
    参数:
        momentum_period: 动量计算周期（天）
        buy_threshold: 买入阈值（百分比，如5表示5%）
        sell_threshold: 卖出阈值（百分比，如-3表示-3%）
        volume_confirm: 是否需要成交量确认
        volume_ratio: 成交量放大倍数（如1.5表示成交量需大于均值1.5倍）
    """
    
    def __init__(self, name: str = 'momentum', params: dict = None):
        super().__init__(name, params or {})
        
        # 策略参数
        self.momentum_period = self.get_param('momentum_period', 20)  # 20日动量
        self.buy_threshold = self.get_param('buy_threshold', 5.0)  # 买入阈值5%
        self.sell_threshold = self.get_param('sell_threshold', -3.0)  # 卖出阈值-3%
        self.volume_confirm = self.get_param('volume_confirm', True)  # 成交量确认
        self.volume_ratio = self.get_param('volume_ratio', 1.5)  # 成交量放大1.5倍
        
        # 持仓状态
        self.position = False
        
        logger.info(
            f"动量策略初始化: 周期={self.momentum_period}天, "
            f"买入阈值={self.buy_threshold}%, 卖出阈值={self.sell_threshold}%"
        )
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据"""
        signals = []
        
        # 添加到数据缓冲区
        self._add_to_buffer(event.data)
        
        # 需要足够的历史数据
        if len(self.data_buffer) < self.momentum_period + 1:
            return signals
        
        # 获取数据DataFrame
        df = self.get_buffer_df()
        
        # 计算动量指标
        momentum = self._calculate_momentum(df)
        if momentum is None:
            return signals
        
        # 计算成交量指标（如果需要）
        volume_confirmed = True
        if self.volume_confirm:
            volume_confirmed = self._check_volume(df)
        
        current_price = float(event.data['close'])
        
        # 生成交易信号
        if not self.position:
            # 无持仓，检查买入条件
            if momentum >= self.buy_threshold and volume_confirmed:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='BUY',
                    strength=min(momentum / 10.0, 1.0),  # 动量越强，信号越强
                    strategy_id=self.strategy_id,
                    metadata={'reason': f'看涨动量 {momentum:.2f}% (阈值: {self.buy_threshold}%)'}
                )
                signals.append(signal)
                self.position = True
                logger.info(
                    f"买入信号: 动量={momentum:.2f}%, 价格={current_price:.2f}, "
                    f"成交量确认={volume_confirmed}"
                )
        else:
            # 有持仓，检查卖出条件
            if momentum <= self.sell_threshold:
                signal = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=event.symbol,
                    signal_type='SELL',
                    strength=1.0,
                    strategy_id=self.strategy_id,
                    metadata={'reason': f'看跌动量 {momentum:.2f}% (阈值: {self.sell_threshold}%)'}
                )
                signals.append(signal)
                self.position = False
                logger.info(f"卖出信号: 动量={momentum:.2f}%, 价格={current_price:.2f}")
        
        return signals
    
    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """计算价格动量（ROC）
        
        ROC = (当前价格 - N日前价格) / N日前价格 * 100
        
        Returns:
            动量百分比
        """
        if len(df) < self.momentum_period + 1:
            return None
        
        current_price = float(df['close'].iloc[-1])
        past_price = float(df['close'].iloc[-self.momentum_period - 1])
        
        if past_price == 0:
            return None
        
        momentum = (current_price - past_price) / past_price * 100
        return momentum
    
    def _check_volume(self, df: pd.DataFrame) -> bool:
        """检查成交量是否放大
        
        Returns:
            是否成交量放大
        """
        if 'volume' not in df.columns:
            return True  # 如果没有成交量数据，默认通过
        
        if len(df) < self.momentum_period:
            return True
        
        # 当前成交量
        current_volume = float(df['volume'].iloc[-1])
        
        # 过去N日平均成交量
        avg_volume = df['volume'].iloc[-self.momentum_period:-1].mean()
        
        if avg_volume == 0:
            return True
        
        # 判断是否放大
        volume_ratio = current_volume / avg_volume
        return volume_ratio >= self.volume_ratio
    
    def on_stop(self):
        """策略停止"""
        logger.info(f"动量策略停止，最终持仓: {'有' if self.position else '无'}")
        super().on_stop()
