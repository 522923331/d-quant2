"""凯利公式资金管理策略"""

import logging

from dquant2.core.capital.base import BaseCapitalStrategy
from dquant2.core.event_bus.events import SignalEvent

logger = logging.getLogger(__name__)


class KellyStrategy(BaseCapitalStrategy):
    """凯利公式策略
    
    根据胜率和盈亏比计算最优仓位
    
    Kelly% = (bp - q) / b
    其中：
    b = 盈亏比
    p = 胜率
    q = 1 - p
    
    参数：
        win_rate: 胜率
        profit_loss_ratio: 盈亏比
        kelly_fraction: 凯利比例调整系数（通常使用0.5，即半凯利）
    """
    
    def __init__(
        self,
        win_rate: float = 0.55,
        profit_loss_ratio: float = 1.5,
        kelly_fraction: float = 0.5
    ):
        super().__init__("Kelly", {
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "kelly_fraction": kelly_fraction
        })
        self.win_rate = win_rate
        self.profit_loss_ratio = profit_loss_ratio
        self.kelly_fraction = kelly_fraction
    
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio_value: float,
        cash: float,
        current_price: float
    ) -> int:
        """计算仓位"""
        if signal.signal_type == 'SELL':
            return 0
        
        # 计算凯利比例
        b = self.profit_loss_ratio
        p = self.win_rate
        q = 1 - p
        
        kelly_pct = (b * p - q) / b
        
        # 应用调整系数
        kelly_pct = kelly_pct * self.kelly_fraction
        
        # 限制在合理范围内
        kelly_pct = max(0, min(kelly_pct, 1.0))
        
        # 计算投资金额
        invest_amount = cash * kelly_pct * signal.strength
        
        if current_price <= 0:
            return 0
        
        # 计算股数
        quantity = int(invest_amount / current_price / 100) * 100
        
        logger.debug(
            f"凯利公式: kelly%={kelly_pct:.2%}, "
            f"投资金额={invest_amount:.2f}, 数量={quantity}"
        )
        
        return quantity
