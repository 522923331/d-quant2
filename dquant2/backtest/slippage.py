"""滑点模拟模块

提供多种滑点模拟方法：固定滑点、比例滑点、动态滑点
"""

from enum import Enum
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class SlippageType(Enum):
    """滑点类型枚举"""
    FIXED = "FIXED"        # 固定滑点（固定金额）
    RATIO = "RATIO"        # 比例滑点（价格百分比）
    TICK = "TICK"          # Tick滑点（按最小变动单位）
    DYNAMIC = "DYNAMIC"    # 动态滑点（基于成交量）


class SlippageModel:
    """滑点模型基类"""
    
    def calculate_slippage(self, 
                          price: float, 
                          quantity: float,
                          side: str,
                          market_data: Dict = None) -> float:
        """计算滑点
        
        Args:
            price: 订单价格
            quantity: 订单数量
            side: 买卖方向 ('BUY' or 'SELL')
            market_data: 市场数据（用于动态滑点）
            
        Returns:
            考虑滑点后的实际成交价格
        """
        raise NotImplementedError


class FixedSlippage(SlippageModel):
    """固定滑点模型
    
    无论价格和数量，滑点固定为指定金额
    """
    
    def __init__(self, slippage_value: float = 0.01):
        """初始化固定滑点
        
        Args:
            slippage_value: 滑点金额，默认 0.01 元
        """
        self.slippage_value = slippage_value
    
    def calculate_slippage(self, 
                          price: float, 
                          quantity: float,
                          side: str,
                          market_data: Dict = None) -> float:
        """计算固定滑点
        
        买入：实际价格 = 订单价格 + 滑点
        卖出：实际价格 = 订单价格 - 滑点
        """
        if side == 'BUY':
            actual_price = price + self.slippage_value
        else:  # SELL
            actual_price = price - self.slippage_value
        
        # 确保价格为正
        actual_price = max(0.01, actual_price)
        
        logger.debug(
            f"固定滑点: {side} {price:.2f} -> {actual_price:.2f} "
            f"(滑点 {self.slippage_value:.2f})"
        )
        
        return actual_price


class RatioSlippage(SlippageModel):
    """比例滑点模型
    
    滑点为价格的固定百分比
    """
    
    def __init__(self, slippage_ratio: float = 0.001):
        """初始化比例滑点
        
        Args:
            slippage_ratio: 滑点比例，默认 0.1%
        """
        self.slippage_ratio = slippage_ratio
    
    def calculate_slippage(self, 
                          price: float, 
                          quantity: float,
                          side: str,
                          market_data: Dict = None) -> float:
        """计算比例滑点
        
        买入：实际价格 = 订单价格 * (1 + 滑点比例)
        卖出：实际价格 = 订单价格 * (1 - 滑点比例)
        """
        if side == 'BUY':
            actual_price = price * (1 + self.slippage_ratio)
        else:  # SELL
            actual_price = price * (1 - self.slippage_ratio)
        
        logger.debug(
            f"比例滑点: {side} {price:.2f} -> {actual_price:.2f} "
            f"({self.slippage_ratio*100:.2f}%)"
        )
        
        return actual_price


class TickSlippage(SlippageModel):
    """Tick 滑点模型
    
    滑点为若干个最小变动单位（tick）
    """
    
    def __init__(self, tick_size: float = 0.01, tick_count: int = 1):
        """初始化 Tick 滑点
        
        Args:
            tick_size: 最小变动单位，默认 0.01 元
            tick_count: Tick 数量，默认 1 个 tick
        """
        self.tick_size = tick_size
        self.tick_count = tick_count
    
    def calculate_slippage(self, 
                          price: float, 
                          quantity: float,
                          side: str,
                          market_data: Dict = None) -> float:
        """计算 Tick 滑点
        
        买入：实际价格 = 订单价格 + tick_size * tick_count
        卖出：实际价格 = 订单价格 - tick_size * tick_count
        """
        slippage = self.tick_size * self.tick_count
        
        if side == 'BUY':
            actual_price = price + slippage
        else:  # SELL
            actual_price = price - slippage
        
        # 确保价格为正
        actual_price = max(0.01, actual_price)
        
        logger.debug(
            f"Tick滑点: {side} {price:.2f} -> {actual_price:.2f} "
            f"({self.tick_count} ticks)"
        )
        
        return actual_price


class DynamicSlippage(SlippageModel):
    """动态滑点模型
    
    根据订单量占成交量的比例动态计算滑点
    """
    
    def __init__(self, impact_factor: float = 0.1):
        """初始化动态滑点
        
        Args:
            impact_factor: 冲击系数，默认 0.1
        """
        self.impact_factor = impact_factor
    
    def calculate_slippage(self, 
                          price: float, 
                          quantity: float,
                          side: str,
                          market_data: Dict = None) -> float:
        """计算动态滑点
        
        滑点 = 价格 * (订单量/市场成交量) * 冲击系数
        
        Args:
            price: 订单价格
            quantity: 订单数量
            side: 买卖方向
            market_data: 市场数据，需要包含 'volume'
        """
        if market_data is None or 'volume' not in market_data:
            logger.warning("动态滑点需要市场成交量数据，使用默认比例 0.1%")
            # 降级为比例滑点
            return RatioSlippage(0.001).calculate_slippage(price, quantity, side)
        
        market_volume = market_data['volume']
        
        # 避免除零
        if market_volume == 0:
            return RatioSlippage(0.001).calculate_slippage(price, quantity, side)
        
        # 计算订单占比
        volume_ratio = quantity / market_volume
        
        # 计算滑点比例
        slippage_ratio = volume_ratio * self.impact_factor
        
        # 限制最大滑点为 2%
        slippage_ratio = min(slippage_ratio, 0.02)
        
        if side == 'BUY':
            actual_price = price * (1 + slippage_ratio)
        else:  # SELL
            actual_price = price * (1 - slippage_ratio)
        
        logger.debug(
            f"动态滑点: {side} {price:.2f} -> {actual_price:.2f} "
            f"(订单占比 {volume_ratio*100:.2f}%, 滑点 {slippage_ratio*100:.2f}%)"
        )
        
        return actual_price


class SlippageFactory:
    """滑点模型工厂"""
    
    @staticmethod
    def create(slippage_type: str, **params) -> SlippageModel:
        """创建滑点模型
        
        Args:
            slippage_type: 滑点类型 ('fixed', 'ratio', 'tick', 'dynamic')
            **params: 滑点参数
            
        Returns:
            滑点模型实例
        """
        slippage_type = slippage_type.lower()
        
        if slippage_type == 'fixed':
            return FixedSlippage(
                slippage_value=params.get('slippage_value', 0.01)
            )
        
        elif slippage_type == 'ratio':
            return RatioSlippage(
                slippage_ratio=params.get('slippage_ratio', 0.001)
            )
        
        elif slippage_type == 'tick':
            return TickSlippage(
                tick_size=params.get('tick_size', 0.01),
                tick_count=params.get('tick_count', 1)
            )
        
        elif slippage_type == 'dynamic':
            return DynamicSlippage(
                impact_factor=params.get('impact_factor', 0.1)
            )
        
        else:
            logger.warning(f"未知滑点类型: {slippage_type}，使用比例滑点")
            return RatioSlippage()
