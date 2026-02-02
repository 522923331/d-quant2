"""投资组合增强功能测试"""

import pytest
from datetime import datetime
from dquant2.core.portfolio.cost_calculator import (
    FIFOCostCalculator, LIFOCostCalculator, WeightedAverageCostCalculator
)
from dquant2.core.portfolio.rebalance import RebalanceCalculator, PeriodicRebalancer


class TestFIFOCostCalculator:
    """测试 FIFO 成本计算"""
    
    def test_fifo_buy_and_sell(self):
        """测试 FIFO 买卖成本"""
        calc = FIFOCostCalculator()
        
        # 第一次买入
        calc.add_buy('000001', 1000, 10.0, datetime.now())
        assert calc.get_total_quantity('000001') == 1000
        assert calc.get_avg_cost('000001') == 10.0
        
        # 第二次买入（更高价格）
        calc.add_buy('000001', 500, 12.0, datetime.now())
        assert calc.get_total_quantity('000001') == 1500
        
        # FIFO 卖出 600 股（应该先卖第一批的600股）
        avg_cost, details = calc.calculate_sell_cost('000001', 600)
        assert avg_cost == 10.0  # 全部来自第一批
        assert len(details) == 1
        assert details[0]['quantity'] == 600
        assert details[0]['cost'] == 10.0
        
        # 剩余 900 股
        assert calc.get_total_quantity('000001') == 900
    
    def test_fifo_mixed_batches(self):
        """测试 FIFO 跨批次卖出"""
        calc = FIFOCostCalculator()
        
        # 三次买入
        calc.add_buy('000001', 300, 10.0, datetime.now())
        calc.add_buy('000001', 400, 11.0, datetime.now())
        calc.add_buy('000001', 300, 12.0, datetime.now())
        
        # 卖出 500 股（300@10 + 200@11）
        avg_cost, details = calc.calculate_sell_cost('000001', 500)
        expected_cost = (300 * 10.0 + 200 * 11.0) / 500
        assert abs(avg_cost - expected_cost) < 0.01
        assert len(details) == 2


class TestWeightedAverageCostCalculator:
    """测试加权平均成本计算"""
    
    def test_weighted_avg(self):
        """测试加权平均"""
        calc = WeightedAverageCostCalculator()
        
        # 第一次买入
        calc.add_buy('000001', 1000, 10.0, datetime.now())
        assert calc.get_avg_cost('000001') == 10.0
        
        # 第二次买入
        calc.add_buy('000001', 500, 12.0, datetime.now())
        expected_avg = (1000 * 10.0 + 500 * 12.0) / 1500
        assert abs(calc.get_avg_cost('000001') - expected_avg) < 0.01
        
        # 卖出
        avg_cost, _ = calc.calculate_sell_cost('000001', 500)
        assert abs(avg_cost - expected_avg) < 0.01


class TestRebalanceCalculator:
    """测试再平衡计算器"""
    
    def test_rebalance_calculation(self):
        """测试再平衡计算"""
        calc = RebalanceCalculator(commission_rate=0.0003)
        
        # 当前持仓
        current_positions = {
            '000001': {'quantity': 1000, 'value': 10000},
            '000002': {'quantity': 500, 'value': 5000}
        }
        
        # 目标权重（60% : 40%）
        target_weights = {
            '000001': 0.6,
            '000002': 0.4
        }
        
        # 当前价格
        current_prices = {
            '000001': 10.0,
            '000002': 10.0
        }
        
        portfolio_value = 15000
        
        # 计算再平衡方案
        plan = calc.calculate_rebalance(
            current_positions,
            target_weights,
            portfolio_value,
            current_prices
        )
        
        assert 'trades' in plan
        assert 'total_commission' in plan
        
        # 打印方案
        print(f"\n再平衡方案:")
        print(f"总交易数: {plan['total_trades']}")
        print(f"预计手续费: {plan['total_commission']:.2f}")
        for trade in plan['trades']:
            print(f"  {trade['direction']} {trade['symbol']} {trade['quantity']}股")


class TestPeriodicRebalancer:
    """测试定期再平衡器"""
    
    def test_monthly_rebalance_trigger(self):
        """测试月度再平衡触发"""
        target_weights = {'000001': 0.6, '000002': 0.4}
        rebalancer = PeriodicRebalancer(
            target_weights,
            rebalance_frequency='monthly',
            threshold_pct=0.05
        )
        
        # 第一次检查应该触发（last_rebalance_date 为 None）
        current_weights = {'000001': 0.7, '000002': 0.3}
        should_rebalance = rebalancer.should_rebalance(
            datetime.now(),
            current_weights
        )
        
        assert should_rebalance == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
