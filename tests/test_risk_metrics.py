"""风险指标模块测试

测试风险指标计算的正确性
"""

import pytest
import numpy as np
from dquant2.core.risk.metrics import RiskMetrics, StopLossTracker, TrailingStopLoss


class TestRiskMetrics:
    """测试风险指标计算"""
    
    def test_calculate_returns(self):
        """测试收益率计算"""
        rm = RiskMetrics()
        
        # 模拟权益序列
        equity_values = [100000, 102000, 101000, 105000, 103000]
        for eq in equity_values:
            rm.update_equity(eq)
        
        returns = rm.calculate_returns()
        
        # 验证收益率数量
        assert len(returns) == len(equity_values) - 1
        
        # 验证第一个收益率
        expected_first = (102000 - 100000) / 100000
        assert abs(returns[0] - expected_first) < 1e-6
    
    def test_calculate_var(self):
        """测试 VaR 计算"""
        rm = RiskMetrics()
        
        # 模拟权益序列（包含一些负收益）
        equity_values = [100000, 102000, 98000, 101000, 97000, 103000, 99000, 105000]
        for eq in equity_values:
            rm.update_equity(eq)
        
        var_95 = rm.calculate_var(0.95)
        
        # VaR 应该是负数（表示损失）
        assert var_95 < 0
        
        print(f"VaR(95%): {var_95:.2f}%")
    
    def test_calculate_sharpe(self):
        """测试夏普比率计算"""
        rm = RiskMetrics()
        
        # 模拟稳定增长的权益序列
        equity_values = [100000 * (1.001 ** i) for i in range(100)]
        for eq in equity_values:
            rm.update_equity(eq)
        
        sharpe = rm.calculate_sharpe_ratio()
        
        # 稳定增长应该有正的夏普比率
        assert sharpe > 0
        
        print(f"Sharpe Ratio: {sharpe:.2f}")
    
    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        rm = RiskMetrics()
        
        # 模拟包含回撤的权益序列
        equity_values = [100000, 110000, 105000, 95000, 100000, 115000]
        for eq in equity_values:
            rm.update_equity(eq)
        
        max_dd, start_idx, end_idx = rm.calculate_max_drawdown()
        
        # 最大回撤应该是从 110000 到 95000
        expected_dd = (95000 - 110000) / 110000 * 100
        
        assert abs(max_dd - expected_dd) < 0.1
        assert start_idx == 1  # 110000 的位置
        assert end_idx == 3    # 95000 的位置
        
        print(f"Max Drawdown: {max_dd:.2f}%")
    
    def test_risk_level_assessment(self):
        """测试风险等级评估"""
        rm = RiskMetrics()
        
        # 低风险场景
        equity_values = [100000 + i * 100 for i in range(100)]
        for eq in equity_values:
            rm.update_equity(eq)
        
        risk_level = rm.assess_risk_level()
        assert risk_level in ['低', '中', '高', '极高']
        
        print(f"Risk Level: {risk_level}")


class TestStopLossTracker:
    """测试止损追踪器"""
    
    def test_stop_loss_trigger(self):
        """测试止损触发"""
        tracker = StopLossTracker(stop_loss_pct=0.05, take_profit_pct=0.15)
        
        # 模拟持仓
        class MockPosition:
            def __init__(self, symbol, unrealized_pnl_pct):
                self.symbol = symbol
                self.quantity = 1000
                self.avg_price = 10.0
                self.unrealized_pnl_pct = unrealized_pnl_pct
        
        # 亏损6%，应该触发止损
        position = MockPosition('000001', -0.06)
        result = tracker.check_position(position, 9.4)
        
        assert result['stop_loss'] == True
        assert result['action'] == 'SELL'
        assert '止损触发' in result['reason']
    
    def test_take_profit_trigger(self):
        """测试止盈触发"""
        tracker = StopLossTracker(stop_loss_pct=0.05, take_profit_pct=0.15)
        
        class MockPosition:
            def __init__(self, symbol, unrealized_pnl_pct):
                self.symbol = symbol
                self.quantity = 1000
                self.avg_price = 10.0
                self.unrealized_pnl_pct = unrealized_pnl_pct
        
        # 盈利16%，应该触发止盈
        position = MockPosition('000001', 0.16)
        result = tracker.check_position(position, 11.6)
        
        assert result['take_profit'] == True
        assert result['action'] == 'SELL'
        assert '止盈触发' in result['reason']


class TestTrailingStopLoss:
    """测试移动止损"""
    
    def test_trailing_stop(self):
        """测试移动止损触发"""
        trailing = TrailingStopLoss(trailing_pct=0.05)
        
        symbol = '000001'
        
        # 价格上涨
        trailing.update_peak(symbol, 10.0)
        trailing.update_peak(symbol, 11.0)
        trailing.update_peak(symbol, 12.0)
        
        # 从12回落到11.2，回落6.7%，应该触发
        should_stop = trailing.should_stop(symbol, 11.2)
        assert should_stop == True
    
    def test_no_trigger_within_threshold(self):
        """测试未超过阈值不触发"""
        trailing = TrailingStopLoss(trailing_pct=0.05)
        
        symbol = '000001'
        trailing.update_peak(symbol, 10.0)
        trailing.update_peak(symbol, 11.0)
        
        # 从11回落到10.5，回落4.5%，不应该触发
        should_stop = trailing.should_stop(symbol, 10.5)
        assert should_stop == False


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])
