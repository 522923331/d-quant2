"""网格交易策略

在指定价格区间内设置多个买卖点位，低买高卖，适合震荡市场
"""

from typing import List
import logging

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


@StrategyFactory.register('grid_trading')
class GridTradingStrategy(BaseStrategy):
    """网格交易策略
    
    原理:
    1. 在价格区间内设置多个网格线（买入线和卖出线）
    2. 价格下跌到买入线时买入
    3. 价格上涨到卖出线时卖出
    4. 通过频繁的低买高卖获取利润
    
    适用场景:
    - 震荡市场
    - 横盘整理
    - 波动率较高但无明显趋势的市场
    
    参数:
        base_price: 基准价格（网格中心价）
        grid_num: 网格数量（上下各grid_num个网格）
        grid_spacing: 网格间距（百分比，如0.02表示2%）
        min_price: 最低价格限制
        max_price: 最高价格限制
    """
    
    def __init__(self, name: str = 'grid_trading', params: dict = None):
        super().__init__(name, params or {})
        
        # 策略参数
        self.base_price = self.get_param('base_price', 100.0)  # 基准价格
        self.grid_num = self.get_param('grid_num', 5)  # 上下各5个网格
        self.grid_spacing = self.get_param('grid_spacing', 0.02)  # 2%网格间距
        self.min_price = self.get_param('min_price', None)  # 最低价格
        self.max_price = self.get_param('max_price', None)  # 最高价格
        
        # 网格线
        self.buy_grids = []  # 买入网格线
        self.sell_grids = []  # 卖出网格线
        
        # 持仓记录（每个网格独立）
        self.grid_positions = {}  # {grid_level: quantity}
        
        logger.info(
            f"网格交易策略初始化: 基准价={self.base_price}, "
            f"网格数={self.grid_num}, 间距={self.grid_spacing*100}%"
        )
    
    def on_start(self):
        """策略启动时初始化网格"""
        super().on_start()
        self._initialize_grids()
    
    def _initialize_grids(self):
        """初始化网格线"""
        # 计算买入网格线（基准价下方）
        for i in range(1, self.grid_num + 1):
            buy_price = self.base_price * (1 - i * self.grid_spacing)
            if self.min_price is None or buy_price >= self.min_price:
                self.buy_grids.append(buy_price)
        
        # 计算卖出网格线（基准价上方）
        for i in range(1, self.grid_num + 1):
            sell_price = self.base_price * (1 + i * self.grid_spacing)
            if self.max_price is None or sell_price <= self.max_price:
                self.sell_grids.append(sell_price)
        
        logger.info(f"买入网格线: {[f'{p:.2f}' for p in self.buy_grids]}")
        logger.info(f"卖出网格线: {[f'{p:.2f}' for p in self.sell_grids]}")
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据"""
        signals = []
        current_price = float(event.data['close'])
        
        # 检查是否触及买入网格线
        for i, buy_price in enumerate(self.buy_grids):
            if current_price <= buy_price:
                # 检查该网格是否已经买入
                grid_level = f"buy_{i}"
                if grid_level not in self.grid_positions:
                    # 生成买入信号
                    signal = SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type='BUY',
                        strength=1.0,
                        strategy_id=self.strategy_id,
                        metadata={'reason': f'触及买入网格线 {buy_price:.2f}'}
                    )
                    signals.append(signal)
                    # 记录网格持仓（实际数量在成交后更新）
                    self.grid_positions[grid_level] = 1
                    logger.info(f"买入信号: 价格{current_price:.2f} <= 网格{buy_price:.2f}")
        
        # 检查是否触及卖出网格线
        for i, sell_price in enumerate(self.sell_grids):
            if current_price >= sell_price:
                # 检查对应的买入网格是否有持仓
                # 简化逻辑：如果有任何持仓就卖出
                if self.grid_positions:
                    # 生成卖出信号
                    signal = SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type='SELL',
                        strength=1.0,
                        strategy_id=self.strategy_id,
                        metadata={'reason': f'触及卖出网格线 {sell_price:.2f}'}
                    )
                    signals.append(signal)
                    # 清除网格持仓（简化处理）
                    self.grid_positions.clear()
                    logger.info(f"卖出信号: 价格{current_price:.2f} >= 网格{sell_price:.2f}")
                    break  # 一次只卖一个网格
        
        return signals
    
    def on_stop(self):
        """策略停止"""
        logger.info(f"网格交易策略停止，网格持仓: {self.grid_positions}")
        super().on_stop()
