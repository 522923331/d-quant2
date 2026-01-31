"""选股配置类"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StockSelectorConfig:
    """选股配置
    
    定义选股的各项条件和参数
    """
    
    # 数据源选择
    data_provider: str = 'baostock'  # 'baostock' 或 'akshare'
    
    # 市场选择
    market: str = 'sh'  # 'sh' 上证, 'sz' 深证
    
    # 数量限制
    max_stocks: int = 10
    
    # 技术指标条件
    use_macd: bool = True  # MACD金叉
    use_kdj: bool = True  # KDJ可买入
    use_rsi: bool = True  # RSI超卖
    use_cci: bool = True  # CCI超卖
    use_wma: bool = True  # 价格>加权均线
    use_ema: bool = True  # 价格>指数均线
    use_sma: bool = True  # 价格>简单均线
    use_volume: bool = True  # 成交量放大
    use_boll: bool = True  # 布林带下轨
    
    # 价格和换手率条件
    use_price_range: bool = True  # 价格区间
    min_price: float = 5.0
    max_price: float = 40.0
    
    use_turnover: bool = True  # 换手率
    min_turnover: float = 3.0
    max_turnover: float = 12.0
    
    # 基本面指标
    use_pe_ratio: bool = False  # 市盈率
    max_pe_ratio: float = 20.0
    
    use_pb_ratio: bool = False  # 市净率
    max_pb_ratio: float = 2.0
    
    use_roe: bool = False  # 净资产收益率
    min_roe: float = 15.0
    
    use_net_profit_margin: bool = False  # 净利率
    min_net_profit_margin: float = 10.0
    
    # 财务指标
    use_gross_profit_rate: bool = False  # 毛利率
    min_gross_profit_rate: float = 30.0
    
    use_operating_profit_rate: bool = False  # 营业利润率
    min_operating_profit_rate: float = 15.0
    
    use_current_ratio: bool = False  # 流动比率
    min_current_ratio: float = 1.5
    
    use_quick_ratio: bool = False  # 速动比率
    min_quick_ratio: float = 1.0

    # 市值和成交量筛选 (New)
    use_market_cap: bool = False
    min_market_cap: float = 0.0  # 最小市值（亿元）
    max_market_cap: float = 1000.0  # 最大市值（亿元）

    use_volume_absolute: bool = False
    min_volume: float = 10000.0  # 最小成交量（手）
    max_volume: float = 10000000.0  # 最大成交量（手）
    
    # 数据源设置
    data_source: str = 'baostock'  # 数据源
    lookback_days: int = 300  # 回看天数
    
    # 指标参数
    bollinger_period: int = 15
    bollinger_std_dev: float = 1.5
    rsi_period: int = 14
    kdj_period: int = 9
    kdj_k_smooth: int = 3
    kdj_d_smooth: int = 3
    macd_short: int = 12
    macd_long: int = 26
    macd_signal: int = 9
    cci_period: int = 14
    ma_period: int = 5
    volume_ratio_threshold: float = 1.5
    
    def get_enabled_conditions(self) -> List[str]:
        """获取已启用的筛选条件列表"""
        conditions = []
        if self.use_macd:
            conditions.append("MACD金叉")
        if self.use_kdj:
            conditions.append("KDJ可买入")
        if self.use_rsi:
            conditions.append(f"RSI < 30")
        if self.use_cci:
            conditions.append(f"CCI < -100")
        if self.use_wma:
            conditions.append("价格 > WMA")
        if self.use_ema:
            conditions.append("价格 > EMA")
        if self.use_sma:
            conditions.append("价格 > SMA")
        if self.use_volume:
            conditions.append(f"成交量 > {self.volume_ratio_threshold}倍均量")
        if self.use_price_range:
            conditions.append(f"价格 {self.min_price}-{self.max_price}")
        if self.use_boll:
            conditions.append("价格 <= 布林下轨")
        if self.use_turnover:
            conditions.append(f"换手率 {self.min_turnover}-{self.max_turnover}")
        if self.use_pe_ratio:
            conditions.append(f"市盈率 < {self.max_pe_ratio}")
        if self.use_pb_ratio:
            conditions.append(f"市净率 < {self.max_pb_ratio}")
        if self.use_roe:
            conditions.append(f"ROE > {self.min_roe}%")
        if self.use_net_profit_margin:
            conditions.append(f"净利率 > {self.min_net_profit_margin}%")
        if self.use_gross_profit_rate:
            conditions.append(f"毛利率 > {self.min_gross_profit_rate}%")
        if self.use_operating_profit_rate:
            conditions.append(f"营业利润率 > {self.min_operating_profit_rate}%")
        if self.use_current_ratio:
            conditions.append(f"流动比率 > {self.min_current_ratio}")
        if self.use_quick_ratio:
            conditions.append(f"速动比率 > {self.min_quick_ratio}")
        if self.use_market_cap:
            conditions.append(f"市值 {self.min_market_cap}-{self.max_market_cap}亿")
        if self.use_volume_absolute:
            conditions.append(f"成交量 {self.min_volume/10000:.1f}万-{self.max_volume/10000:.1f}万手")
        return conditions
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'market': self.market,
            'max_stocks': self.max_stocks,
            'enabled_conditions': self.get_enabled_conditions(),
            'data_source': self.data_source
        }
