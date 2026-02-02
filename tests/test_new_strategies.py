"""新策略测试

测试新增的3个策略：网格交易、动量策略、均值回归
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dquant2 import BacktestEngine, BacktestConfig


class TestGridTradingStrategy:
    """网格交易策略测试"""
    
    def test_grid_trading_basic(self):
        """测试网格交易策略基本功能"""
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='grid_trading',
            strategy_params={
                'base_price': 10.0,
                'grid_num': 5,
                'grid_spacing': 0.02
            }
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 验证结果
        assert results is not None
        assert 'portfolio' in results
        assert 'performance' in results
        assert results['portfolio']['total_value'] > 0
    
    def test_grid_trading_parameters(self):
        """测试不同的网格参数"""
        params_list = [
            {'base_price': 10.0, 'grid_num': 3, 'grid_spacing': 0.01},
            {'base_price': 10.0, 'grid_num': 5, 'grid_spacing': 0.02},
            {'base_price': 10.0, 'grid_num': 10, 'grid_spacing': 0.03},
        ]
        
        for params in params_list:
            config = BacktestConfig(
                symbol='000001',
                start_date='20230101',
                end_date='20230630',
                initial_cash=1000000,
                data_provider='mock',
                strategy_name='grid_trading',
                strategy_params=params
            )
            
            engine = BacktestEngine(config)
            results = engine.run()
            
            assert results['portfolio']['total_value'] > 0


class TestMomentumStrategy:
    """动量策略测试"""
    
    def test_momentum_basic(self):
        """测试动量策略基本功能"""
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='momentum',
            strategy_params={
                'momentum_period': 20,
                'buy_threshold': 5.0,
                'sell_threshold': -3.0,
                'volume_confirm': True
            }
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 验证结果
        assert results is not None
        assert results['portfolio']['total_value'] > 0
    
    def test_momentum_with_volume_confirm(self):
        """测试带成交量确认的动量策略"""
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='momentum',
            strategy_params={
                'momentum_period': 20,
                'buy_threshold': 5.0,
                'sell_threshold': -3.0,
                'volume_confirm': True,
                'volume_ratio': 1.5
            }
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        assert results is not None
    
    def test_momentum_without_volume_confirm(self):
        """测试不需要成交量确认的动量策略"""
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='momentum',
            strategy_params={
                'momentum_period': 20,
                'buy_threshold': 5.0,
                'sell_threshold': -3.0,
                'volume_confirm': False
            }
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        assert results is not None


class TestMeanReversionStrategy:
    """均值回归策略测试"""
    
    def test_mean_reversion_basic(self):
        """测试均值回归策略基本功能"""
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='mean_reversion',
            strategy_params={
                'ma_period': 20,
                'std_period': 20,
                'entry_std': 2.0,
                'exit_std': 0.5
            }
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 验证结果
        assert results is not None
        assert results['portfolio']['total_value'] > 0
    
    def test_mean_reversion_parameters(self):
        """测试不同的均值回归参数"""
        params_list = [
            {'ma_period': 10, 'std_period': 10, 'entry_std': 1.5, 'exit_std': 0.3},
            {'ma_period': 20, 'std_period': 20, 'entry_std': 2.0, 'exit_std': 0.5},
            {'ma_period': 30, 'std_period': 30, 'entry_std': 2.5, 'exit_std': 0.8},
        ]
        
        for params in params_list:
            config = BacktestConfig(
                symbol='000001',
                start_date='20230101',
                end_date='20230630',
                initial_cash=1000000,
                data_provider='mock',
                strategy_name='mean_reversion',
                strategy_params=params
            )
            
            engine = BacktestEngine(config)
            results = engine.run()
            
            assert results['portfolio']['total_value'] > 0


class TestStrategyComparison:
    """策略对比测试"""
    
    def test_compare_all_strategies(self):
        """对比所有策略的表现"""
        strategies = {
            'ma_cross': {'fast_period': 5, 'slow_period': 20},
            'rsi': {'period': 14, 'oversold': 30, 'overbought': 70},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
            'bollinger': {'period': 20, 'std_dev': 2.0},
            'grid_trading': {'base_price': 10.0, 'grid_num': 5, 'grid_spacing': 0.02},
            'momentum': {'momentum_period': 20, 'buy_threshold': 5.0, 'sell_threshold': -3.0},
            'mean_reversion': {'ma_period': 20, 'std_period': 20, 'entry_std': 2.0, 'exit_std': 0.5}
        }
        
        results_list = []
        
        for strategy_name, params in strategies.items():
            config = BacktestConfig(
                symbol='000001',
                start_date='20230101',
                end_date='20230630',
                initial_cash=1000000,
                data_provider='mock',
                strategy_name=strategy_name,
                strategy_params=params
            )
            
            engine = BacktestEngine(config)
            results = engine.run()
            
            results_list.append({
                'strategy': strategy_name,
                'return': results['portfolio']['total_return_pct'],
                'sharpe': results['performance']['sharpe_ratio'],
                'trades': results['portfolio']['num_trades']
            })
        
        # 验证所有策略都能运行
        assert len(results_list) == len(strategies)
        
        # 打印对比结果
        print("\n策略对比结果:")
        print("-" * 60)
        for result in sorted(results_list, key=lambda x: x['return'], reverse=True):
            print(f"{result['strategy']:20s} | "
                  f"收益: {result['return']:6.2f}% | "
                  f"夏普: {result['sharpe']:5.2f} | "
                  f"交易: {result['trades']:3d}次")


if __name__ == '__main__':
    # 直接运行测试
    pytest.main([__file__, '-v', '-s'])
