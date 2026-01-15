"""固定比例资金管理策略"""

import logging

from dquant2.core.capital.base import BaseCapitalStrategy
from dquant2.core.event_bus.events import SignalEvent

logger = logging.getLogger(__name__)


class FixedRatioStrategy(BaseCapitalStrategy):
    """固定比例策略
    
    每次使用固定比例的资金进行交易
    
    参数：
        ratio: 使用比例，默认0.1（10%）
    """
    
    def __init__(self, ratio: float = 0.1):
        super().__init__("FixedRatio", {"ratio": ratio})
        self.ratio = ratio
    
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio_value: float,
        cash: float,
        current_price: float
    ) -> int:
        """计算仓位"""
        if signal.signal_type == 'SELL':
            # 卖出信号：返回0，由执行引擎处理全部卖出
            return 0
        
        # 买入信号：使用固定比例资金
        invest_amount = cash * self.ratio * signal.strength
        
        if current_price <= 0:
            return 0
        
        # 计算股数（向下取整到100的倍数）
        quantity = int(invest_amount / current_price / 100) * 100
        
        logger.debug(
            f"固定比例策略: 投资金额={invest_amount:.2f}, "
            f"价格={current_price:.2f}, 数量={quantity}"
        )
        
        return quantity
