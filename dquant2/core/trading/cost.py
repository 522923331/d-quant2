"""交易成本计算模块

参考 OSkhQuant/khTrade.py 的实现，提供完整的交易成本计算：
- 佣金（最低佣金 + 比例佣金）
- 印花税（卖出时收取）
- 过户费（沪市股票）
- 流量费（每笔固定）
- 滑点（支持 tick 模式和比例模式）
"""

from typing import Tuple, Literal
from dataclasses import dataclass


@dataclass
class TradingCost:
    """交易成本详情"""
    actual_price: float      # 考虑滑点后的实际成交价格
    commission: float        # 佣金
    stamp_tax: float        # 印花税
    transfer_fee: float     # 过户费
    flow_fee: float         # 流量费
    total_cost: float       # 总成本
    
    def __repr__(self) -> str:
        return (
            f"TradingCost(actual_price={self.actual_price:.3f}, "
            f"commission={self.commission:.2f}, "
            f"stamp_tax={self.stamp_tax:.2f}, "
            f"transfer_fee={self.transfer_fee:.2f}, "
            f"flow_fee={self.flow_fee:.2f}, "
            f"total={self.total_cost:.2f})"
        )


class TradingCostCalculator:
    """交易成本计算器
    
    提供完整的A股交易成本计算，包括：
    1. 佣金（最低佣金 + 比例佣金）
    2. 印花税（仅卖出时收取，目前为0.1%）
    3. 过户费（仅沪市股票，成交金额的0.001%）
    4. 流量费（每笔交易固定费用）
    5. 滑点（支持tick模式和比例模式）
    
    参考: OSkhQuant/khTrade.py
    """
    
    def __init__(
        self,
        min_commission: float = 5.0,           # 最低佣金（元）
        commission_rate: float = 0.0003,       # 佣金比例
        stamp_tax_rate: float = 0.001,         # 印花税率（卖出时）
        transfer_fee_rate: float = 0.00001,    # 过户费率（沪市）
        flow_fee: float = 0.1,                 # 流量费（元/笔）
        slippage_type: Literal['tick', 'ratio'] = 'ratio',
        slippage_tick_size: float = 0.01,      # tick 最小变动价
        slippage_tick_count: int = 2,          # tick 跳数
        slippage_ratio: float = 0.001,         # 滑点比例
        price_decimals: int = 2                # 价格精度（股票2位，ETF 3位）
    ):
        """初始化交易成本计算器
        
        Args:
            min_commission: 最低佣金（元），单笔交易至少收取的佣金
            commission_rate: 佣金比例，按成交金额计算
            stamp_tax_rate: 印花税率，仅卖出时收取，当前A股为0.1%
            transfer_fee_rate: 过户费率，仅沪市股票收取，成交金额的0.001%
            flow_fee: 流量费（元/笔），部分券商收取
            slippage_type: 滑点类型，'tick' 或 'ratio'
            slippage_tick_size: tick模式下的最小变动价（A股通常为0.01）
            slippage_tick_count: tick模式下的跳数（买入向上跳，卖出向下跳）
            slippage_ratio: ratio模式下的滑点比例
            price_decimals: 价格精度，股票为2位小数，ETF为3位小数
        """
        self.min_commission = min_commission
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.flow_fee = flow_fee
        
        # 滑点配置
        self.slippage_type = slippage_type
        self.slippage_tick_size = slippage_tick_size
        self.slippage_tick_count = slippage_tick_count
        self.slippage_ratio = slippage_ratio
        
        # 价格精度
        self.price_decimals = price_decimals
    
    def set_price_decimals(self, decimals: int):
        """设置价格精度
        
        Args:
            decimals: 小数位数，股票为2，ETF为3
        """
        self.price_decimals = decimals
    
    def calculate_slippage_price(
        self,
        price: float,
        direction: Literal['BUY', 'SELL']
    ) -> float:
        """计算考虑滑点后的价格
        
        滑点处理原则：
        - 买入时价格上滑（对交易者不利）
        - 卖出时价格下滑（对交易者不利）
        
        Args:
            price: 原始价格
            direction: 交易方向，'BUY' 或 'SELL'
            
        Returns:
            考虑滑点后的价格
        """
        if self.slippage_type == 'tick':
            # tick 模式：按最小变动价跳数计算
            slippage = self.slippage_tick_size * self.slippage_tick_count
            if direction == 'BUY':
                actual_price = price + slippage
            else:  # SELL
                actual_price = price - slippage
        else:  # ratio 模式
            # 比例模式：按百分比计算
            if direction == 'BUY':
                actual_price = price * (1 + self.slippage_ratio)
            else:  # SELL
                actual_price = price * (1 - self.slippage_ratio)
        
        return round(actual_price, self.price_decimals)
    
    def calculate_commission(self, price: float, volume: int) -> float:
        """计算佣金
        
        佣金 = max(最低佣金, 成交金额 × 佣金比例)
        
        Args:
            price: 成交价格
            volume: 成交数量
            
        Returns:
            佣金金额
        """
        if volume <= 0:
            return 0.0
        
        commission = price * volume * self.commission_rate
        return max(self.min_commission, commission)
    
    def calculate_stamp_tax(
        self,
        price: float,
        volume: int,
        direction: Literal['BUY', 'SELL']
    ) -> float:
        """计算印花税
        
        印花税仅在卖出时收取，当前A股税率为0.1%
        
        Args:
            price: 成交价格
            volume: 成交数量
            direction: 交易方向
            
        Returns:
            印花税金额
        """
        if volume <= 0:
            return 0.0
        
        if direction == 'SELL':
            return price * volume * self.stamp_tax_rate
        return 0.0
    
    def calculate_transfer_fee(
        self,
        stock_code: str,
        price: float,
        volume: int
    ) -> float:
        """计算过户费
        
        仅沪市股票收取过户费，成交金额的0.001%
        沪市股票代码以 'sh.' 或 '6' 开头
        
        Args:
            stock_code: 股票代码（如 '600519.SH' 或 '000001.SZ'）
            price: 成交价格
            volume: 成交数量
            
        Returns:
            过户费金额
        """
        if volume <= 0:
            return 0.0
        
        # 判断是否为沪市股票
        is_sh_stock = (
            stock_code.lower().startswith('sh.') or
            stock_code.startswith('6') or
            stock_code.lower().endswith('.sh')
        )
        
        if is_sh_stock:
            return price * volume * self.transfer_fee_rate
        return 0.0
    
    def calculate_flow_fee(self) -> float:
        """计算流量费
        
        每笔交易固定收取的流量费
        
        Returns:
            流量费金额
        """
        return self.flow_fee
    
    def calculate(
        self,
        stock_code: str,
        price: float,
        volume: int,
        direction: Literal['BUY', 'SELL']
    ) -> TradingCost:
        """计算完整的交易成本
        
        Args:
            stock_code: 股票代码
            price: 委托价格
            volume: 交易数量
            direction: 交易方向，'BUY' 或 'SELL'
            
        Returns:
            TradingCost 对象，包含所有成本明细
        """
        # 1. 计算滑点后的实际成交价格
        actual_price = self.calculate_slippage_price(price, direction)
        
        # 2. 计算佣金
        commission = self.calculate_commission(actual_price, volume)
        
        # 3. 计算印花税（仅卖出）
        stamp_tax = self.calculate_stamp_tax(actual_price, volume, direction)
        
        # 4. 计算过户费（沪市股票）
        transfer_fee = self.calculate_transfer_fee(stock_code, actual_price, volume)
        
        # 5. 计算流量费
        flow_fee = self.calculate_flow_fee()
        
        # 6. 总成本
        total_cost = commission + stamp_tax + transfer_fee + flow_fee
        
        return TradingCost(
            actual_price=actual_price,
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            flow_fee=flow_fee,
            total_cost=total_cost
        )
    
    def get_summary(self) -> dict:
        """获取成本计算器配置摘要
        
        Returns:
            配置字典
        """
        return {
            'min_commission': self.min_commission,
            'commission_rate': self.commission_rate,
            'stamp_tax_rate': self.stamp_tax_rate,
            'transfer_fee_rate': self.transfer_fee_rate,
            'flow_fee': self.flow_fee,
            'slippage_type': self.slippage_type,
            'slippage_tick_size': self.slippage_tick_size,
            'slippage_tick_count': self.slippage_tick_count,
            'slippage_ratio': self.slippage_ratio,
            'price_decimals': self.price_decimals
        }
    
    def print_summary(self):
        """打印成本计算器配置"""
        print("=" * 60)
        print("交易成本计算器配置")
        print("=" * 60)
        print(f"最低佣金: {self.min_commission}元")
        print(f"佣金比例: {self.commission_rate * 100}%")
        print(f"印花税率: {self.stamp_tax_rate * 100}%（仅卖出）")
        print(f"过户费率: {self.transfer_fee_rate * 100}%（沪市股票）")
        print(f"流量费: {self.flow_fee}元/笔")
        print(f"\n滑点类型: {self.slippage_type}")
        if self.slippage_type == 'tick':
            print(f"  最小变动价: {self.slippage_tick_size}元")
            print(f"  跳数: {self.slippage_tick_count}")
            print(f"  实际滑点: {self.slippage_tick_size * self.slippage_tick_count}元")
        else:
            print(f"  滑点比例: {self.slippage_ratio * 100}%")
        print(f"\n价格精度: {self.price_decimals}位小数")
        print("=" * 60)


# 示例用法
if __name__ == '__main__':
    # 创建成本计算器
    calculator = TradingCostCalculator()
    
    # 打印配置
    calculator.print_summary()
    
    # 测试1: 买入贵州茅台（沪市股票）
    print("\n测试1: 买入贵州茅台 600519.SH")
    cost = calculator.calculate(
        stock_code='600519.SH',
        price=1800.00,
        volume=100,
        direction='BUY'
    )
    print(cost)
    print(f"成交金额: {cost.actual_price * 100:.2f}")
    print(f"总成本: {cost.total_cost:.2f}")
    print(f"实际支出: {cost.actual_price * 100 + cost.total_cost:.2f}")
    
    # 测试2: 卖出平安银行（深市股票）
    print("\n测试2: 卖出平安银行 000001.SZ")
    cost = calculator.calculate(
        stock_code='000001.SZ',
        price=12.50,
        volume=1000,
        direction='SELL'
    )
    print(cost)
    print(f"成交金额: {cost.actual_price * 1000:.2f}")
    print(f"总成本: {cost.total_cost:.2f}")
    print(f"实际收入: {cost.actual_price * 1000 - cost.total_cost:.2f}")
