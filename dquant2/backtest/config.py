"""回测配置"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class BacktestConfig:
    """回测配置
    
    包含回测所需的所有参数
    """
    
    # 基本配置
    symbol: str                        # 股票代码
    start_date: str                    # 开始日期 YYYYMMDD
    end_date: str                      # 结束日期 YYYYMMDD
    initial_cash: float = 1000000.0   # 初始资金
    
    # 数据配置
    data_freq: str = 'd'              # 数据频率 'd'=日, '60m'=60分钟
    data_provider: str = 'akshare'        # 数据提供者 'mock', 'akshare', etc.
    
    # 策略配置
    strategy_name: str = 'ma_cross'    # 策略名称
    strategy_params: Dict[str, Any] = field(default_factory=dict)  # 策略参数
    
    # 资金管理配置
    capital_strategy: str = 'fixed_ratio'  # 资金管理策略
    capital_params: Dict[str, Any] = field(default_factory=lambda: {'ratio': 0.1})
    
    # 交易成本
    commission_rate: float = 0.0003    # 佣金费率
    slippage: float = 0.0              # 滑点
    
    # 风控配置
    max_position_ratio: float = 0.3    # 最大单只持仓比例
    enable_risk_control: bool = True   # 是否启用风控
    
    # 其他配置
    enable_logging: bool = True        # 是否启用日志
    enable_audit: bool = True          # 是否启用审计
    
    def validate(self):
        """验证配置"""
        assert self.initial_cash > 0, "初始资金必须大于0"
        assert 0 <= self.commission_rate < 1, "佣金费率必须在0-1之间"
        assert 0 <= self.max_position_ratio <= 1, "最大持仓比例必须在0-1之间"
        
        # 验证日期格式
        assert len(self.start_date) == 8, "日期格式应为YYYYMMDD"
        assert len(self.end_date) == 8, "日期格式应为YYYYMMDD"
        assert self.start_date < self.end_date, "开始日期必须早于结束日期"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_cash': self.initial_cash,
            'data_freq': self.data_freq,
            'data_provider': self.data_provider,
            'strategy_name': self.strategy_name,
            'strategy_params': self.strategy_params,
            'capital_strategy': self.capital_strategy,
            'capital_params': self.capital_params,
            'commission_rate': self.commission_rate,
            'slippage': self.slippage,
            'max_position_ratio': self.max_position_ratio,
            'enable_risk_control': self.enable_risk_control,
            'enable_logging': self.enable_logging,
            'enable_audit': self.enable_audit,
        }
