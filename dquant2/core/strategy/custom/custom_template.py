"""自定义策略模板

这是一个自定义策略模板，您可以基于此模板创建自己的交易策略。

使用方法：
1. 复制此文件并重命名（如: my_strategy.py）
2. 修改类名和策略名称
3. 实现 on_data 方法中的交易逻辑
4. 策略会自动注册到策略工厂，可在前端选择使用

策略开发提示：
- self.data_buffer: 历史数据缓冲区
- self.get_buffer_df(): 获取缓冲区数据为DataFrame
- self.get_param(key, default): 获取策略参数
- SignalEvent: 信号事件，用于发出买卖信号
"""

from typing import List
import logging

import pandas as pd
import numpy as np

from dquant2.core.strategy.base import BaseStrategy
from dquant2.core.strategy.factory import StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

logger = logging.getLogger(__name__)


# ============================================================
# 在这里修改策略注册名称（用于前端选择）
# ============================================================
STRATEGY_NAME = "custom_template"  # 修改这个名称

@StrategyFactory.register(STRATEGY_NAME)
class CustomStrategy(BaseStrategy):
    """自定义策略模板
    
    修改这个类实现您自己的交易策略
    
    可配置参数（在前端设置）：
        param1: 参数1说明
        param2: 参数2说明
    """
    
    # ============================================================
    # 策略参数定义（用于前端显示和配置）
    # ============================================================
    STRATEGY_PARAMS = {
        'param1': {
            'name': '参数1',           # 显示名称
            'type': 'int',             # 类型: int, float, bool
            'default': 10,             # 默认值
            'min': 1,                  # 最小值
            'max': 100,                # 最大值
            'step': 1,                 # 步长
            'help': '这是参数1的说明'   # 帮助文本
        },
        'param2': {
            'name': '参数2',
            'type': 'float',
            'default': 0.5,
            'min': 0.1,
            'max': 1.0,
            'step': 0.1,
            'help': '这是参数2的说明'
        }
    }
    
    def __init__(self, name: str = "CustomStrategy", params: dict = None):
        super().__init__(name, params)
        
        # ============================================================
        # 初始化策略参数
        # ============================================================
        self.param1 = self.get_param('param1', 10)
        self.param2 = self.get_param('param2', 0.5)
        
        # 内部状态变量
        self.last_signal = None
        self.in_position = False
        
        logger.info(f"自定义策略初始化: param1={self.param1}, param2={self.param2}")
    
    def on_data(self, event: MarketDataEvent) -> List[SignalEvent]:
        """处理市场数据并生成交易信号
        
        这是策略的核心方法，每当新数据到达时都会被调用。
        
        Args:
            event: 市场数据事件，包含:
                - event.timestamp: 时间戳
                - event.symbol: 股票代码
                - event.data: 当前K线数据 (pd.Series)
                    - 'open': 开盘价
                    - 'high': 最高价
                    - 'low': 最低价
                    - 'close': 收盘价
                    - 'volume': 成交量
        
        Returns:
            信号事件列表（可以为空列表，表示不发出信号）
        """
        # ============================================================
        # 1. 添加数据到缓冲区
        # ============================================================
        self._add_to_buffer(event.data)
        
        # ============================================================
        # 2. 检查是否有足够的数据
        # ============================================================
        min_periods = self.param1  # 根据您的策略调整
        if len(self.data_buffer) < min_periods:
            return []
        
        # ============================================================
        # 3. 获取历史数据并计算指标
        # ============================================================
        df = self.get_buffer_df()
        
        # 示例：计算简单移动平均
        ma = df['close'].rolling(window=self.param1).mean()
        current_price = df['close'].iloc[-1]
        current_ma = ma.iloc[-1]
        
        if pd.isna(current_ma):
            return []
        
        # ============================================================
        # 4. 生成交易信号
        # ============================================================
        signals = []
        
        # 示例买入条件：价格上穿均线
        if current_price > current_ma and not self.in_position:
            signal = SignalEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                signal_type='BUY',
                strength=1.0,  # 信号强度 0-1
                strategy_id=self.strategy_id,
                metadata={
                    'price': current_price,
                    'ma': current_ma,
                    'reason': '价格上穿均线'  # 信号原因
                }
            )
            signals.append(signal)
            self.in_position = True
            self.last_signal = 'BUY'
            logger.info(f"买入信号: {event.symbol} @ {event.timestamp}")
        
        # 示例卖出条件：价格下穿均线
        elif current_price < current_ma and self.in_position:
            signal = SignalEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                signal_type='SELL',
                strength=1.0,
                strategy_id=self.strategy_id,
                metadata={
                    'price': current_price,
                    'ma': current_ma,
                    'reason': '价格下穿均线'
                }
            )
            signals.append(signal)
            self.in_position = False
            self.last_signal = 'SELL'
            logger.info(f"卖出信号: {event.symbol} @ {event.timestamp}")
        
        return signals
    
    # ============================================================
    # 可选：添加自定义辅助方法
    # ============================================================
    def _calculate_indicator(self, data: pd.DataFrame) -> pd.Series:
        """计算自定义指标
        
        这是一个示例辅助方法，您可以添加更多辅助方法
        
        Args:
            data: 历史数据DataFrame
            
        Returns:
            计算结果
        """
        # 实现您的指标计算逻辑
        pass


# ============================================================
# 策略元数据（用于前端显示）
# ============================================================
STRATEGY_METADATA = {
    'name': STRATEGY_NAME,
    'display_name': '自定义策略模板',  # 前端显示名称
    'description': '这是一个自定义策略模板，您可以基于此创建自己的交易策略',
    'author': 'Your Name',
    'version': '1.0.0',
    'params': CustomStrategy.STRATEGY_PARAMS
}
