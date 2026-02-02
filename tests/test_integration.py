"""集成测试

端到端测试主要业务流程
"""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dquant2 import BacktestEngine, BacktestConfig
from dquant2.stock import StockSelector, StockSelectorConfig
from dquant2.core.data.cache import ParquetCache
from dquant2.backtest.history_manager import BacktestHistoryManager
from dquant2.backtest.report_exporter import ReportExporter
from dquant2.backtest.parallel_backtest import ParallelBacktest


class TestCompleteBacktestWorkflow:
    """完整回测流程测试"""
    
    def test_single_backtest_workflow(self):
        """测试单个回测的完整流程"""
        # 1. 创建配置
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',  # 使用模拟数据
            strategy_name='ma_cross',
            strategy_params={'fast_period': 5, 'slow_period': 20}
        )
        
        # 2. 运行回测
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 3. 验证结果
        assert results is not None
        assert 'portfolio' in results
        assert 'performance' in results
        assert 'equity_curve' in results
        assert 'trades' in results
        
        # 验证关键指标
        portfolio = results['portfolio']
        assert portfolio['initial_cash'] == 1000000
        assert portfolio['total_value'] > 0
        assert 'total_return_pct' in portfolio
        
        # 验证性能指标
        performance = results['performance']
        assert 'sharpe_ratio' in performance
        assert 'max_drawdown' in performance
        
        # 4. 保存到历史记录
        manager = BacktestHistoryManager()
        record_id = manager.save_backtest(
            results,
            notes="集成测试",
            tags=['test', 'ma_cross']
        )
        assert record_id > 0
        
        # 5. 从历史记录读取
        record = manager.get_backtest(record_id)
        assert record is not None
        assert record['symbol'] == '000001'
        assert record['strategy_name'] == 'ma_cross'
        
        # 6. 导出报告
        exporter = ReportExporter(results)
        html_path = exporter.export_html()
        assert Path(html_path).exists()
        
        # 清理
        Path(html_path).unlink()
        manager.delete_backtest(record_id)
    
    def test_multiple_strategies_workflow(self):
        """测试多个策略的对比流程"""
        strategies = ['ma_cross', 'rsi', 'macd']
        results_list = []
        
        for strategy in strategies:
            # 配置
            if strategy == 'ma_cross':
                params = {'fast_period': 5, 'slow_period': 20}
            elif strategy == 'rsi':
                params = {'period': 14, 'oversold': 30, 'overbought': 70}
            else:  # macd
                params = {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}
            
            config = BacktestConfig(
                symbol='000001',
                start_date='20230101',
                end_date='20230630',
                initial_cash=1000000,
                data_provider='mock',
                strategy_name=strategy,
                strategy_params=params
            )
            
            # 运行回测
            engine = BacktestEngine(config)
            results = engine.run()
            results_list.append(results)
        
        # 验证所有策略都运行成功
        assert len(results_list) == 3
        for results in results_list:
            assert results['portfolio']['total_value'] > 0
    
    def test_new_strategies(self):
        """测试新增的策略"""
        # 测试网格交易策略
        config_grid = BacktestConfig(
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
        
        engine = BacktestEngine(config_grid)
        results_grid = engine.run()
        assert results_grid is not None
        assert results_grid['portfolio']['total_value'] > 0
        
        # 测试动量策略
        config_momentum = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='momentum',
            strategy_params={
                'momentum_period': 20,
                'buy_threshold': 5.0,
                'sell_threshold': -3.0
            }
        )
        
        engine = BacktestEngine(config_momentum)
        results_momentum = engine.run()
        assert results_momentum is not None
        
        # 测试均值回归策略
        config_mean_rev = BacktestConfig(
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
        
        engine = BacktestEngine(config_mean_rev)
        results_mean_rev = engine.run()
        assert results_mean_rev is not None


class TestDataWorkflow:
    """数据流程测试"""
    
    def test_cache_workflow(self):
        """测试数据缓存流程"""
        cache = ParquetCache()
        
        # 清空缓存
        cache.clear()
        
        # 验证缓存为空
        stats = cache.get_cache_stats()
        assert stats['total_files'] == 0
        
        # 注意：实际的数据下载需要网络，这里跳过
        # 在真实环境中，会测试：
        # 1. 下载数据
        # 2. 保存到缓存
        # 3. 从缓存读取
        # 4. 验证数据一致性


class TestHistoryWorkflow:
    """历史记录流程测试"""
    
    def test_history_save_and_query(self):
        """测试历史记录保存和查询"""
        manager = BacktestHistoryManager()
        
        # 1. 运行一个回测
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='ma_cross',
            strategy_params={'fast_period': 5, 'slow_period': 20}
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 2. 保存到历史
        record_id = manager.save_backtest(
            results,
            notes="集成测试 - 历史记录",
            tags=['test', 'integration']
        )
        assert record_id > 0
        
        # 3. 查询记录
        record = manager.get_backtest(record_id)
        assert record is not None
        assert record['symbol'] == '000001'
        assert record['strategy_name'] == 'ma_cross'
        assert 'test' in record['tags']
        
        # 4. 列出记录
        records = manager.list_backtests(symbol='000001', limit=10)
        assert len(records) > 0
        assert any(r['id'] == record_id for r in records)
        
        # 5. 搜索记录
        search_results = manager.search_backtests(
            tags=['test'],
            limit=10
        )
        assert len(search_results) > 0
        
        # 6. 更新备注
        updated = manager.update_notes(record_id, "更新后的备注")
        assert updated
        
        # 7. 添加标签
        added = manager.add_tags(record_id, ['new_tag'])
        assert added
        
        # 8. 获取统计
        stats = manager.get_statistics()
        assert stats['total_count'] > 0
        
        # 清理
        manager.delete_backtest(record_id)


class TestParallelBacktest:
    """并行回测测试"""
    
    def test_parallel_backtest_symbols(self):
        """测试并行回测多个股票"""
        symbols = ['000001', '000002', '600000']
        
        base_config = {
            'start_date': '20230101',
            'end_date': '20230630',
            'initial_cash': 1000000,
            'data_provider': 'mock',
            'strategy_name': 'ma_cross',
            'strategy_params': {'fast_period': 5, 'slow_period': 20}
        }
        
        # 进度回调
        progress_messages = []
        def progress_callback(message, current, total):
            progress_messages.append(message)
        
        # 并行回测
        parallel = ParallelBacktest(max_workers=2)
        results = parallel.run_batch_for_symbols(
            symbols,
            base_config,
            progress_callback
        )
        
        # 验证结果
        assert len(results) == 3
        
        # 验证每个结果
        for result in results:
            if result['success']:
                assert 'portfolio' in result
                assert 'performance' in result
        
        # 验证进度回调被调用
        assert len(progress_messages) > 0
    
    def test_parameter_optimization(self):
        """测试参数优化"""
        base_config = {
            'symbol': '000001',
            'start_date': '20230101',
            'end_date': '20230630',
            'initial_cash': 1000000,
            'data_provider': 'mock',
            'strategy_name': 'ma_cross',
            'strategy_params': {}
        }
        
        param_grid = {
            'fast_period': [3, 5, 10],
            'slow_period': [20, 30]
        }
        
        # 参数优化
        parallel = ParallelBacktest(max_workers=2)
        results = parallel.run_parameter_optimization(
            base_config,
            param_grid
        )
        
        # 验证结果
        assert len(results) > 0  # 至少有成功的结果
        
        # 验证结果已按收益率排序
        if len(results) >= 2:
            first_return = results[0]['portfolio']['total_return_pct']
            second_return = results[1]['portfolio']['total_return_pct']
            assert first_return >= second_return


class TestCompleteWorkflow:
    """完整业务流程测试"""
    
    def test_select_and_backtest_workflow(self):
        """测试选股到回测的完整流程
        
        注意：此测试需要实际数据源，在CI环境中可能需要跳过
        """
        # 由于选股需要实际数据源，这里用mock数据演示流程
        
        # 1. 假设选股结果
        selected_stocks = [
            {'code': '000001', 'name': '平安银行', 'price': 10.5},
            {'code': '600000', 'name': '浦发银行', 'price': 8.5}
        ]
        
        # 2. 为选中的股票批量回测
        base_config = {
            'start_date': '20230101',
            'end_date': '20230630',
            'initial_cash': 100000,
            'data_provider': 'mock',
            'strategy_name': 'ma_cross',
            'strategy_params': {'fast_period': 5, 'slow_period': 20}
        }
        
        symbols = [stock['code'] for stock in selected_stocks]
        
        parallel = ParallelBacktest(max_workers=2)
        results = parallel.run_batch_for_symbols(symbols, base_config)
        
        # 3. 验证所有回测结果
        assert len(results) == len(symbols)
        
        # 4. 保存所有结果到历史
        manager = BacktestHistoryManager()
        saved_ids = []
        
        for i, result in enumerate(results):
            if result['success']:
                record_id = manager.save_backtest(
                    result,
                    notes=f"选股回测 - {selected_stocks[i]['name']}",
                    tags=['select_backtest', 'integration_test']
                )
                saved_ids.append(record_id)
        
        # 5. 验证保存成功
        assert len(saved_ids) > 0
        
        # 6. 对比回测结果
        if len(saved_ids) >= 2:
            comparison_df = manager.compare_backtests(saved_ids)
            assert len(comparison_df) == len(saved_ids)
        
        # 7. 导出最佳结果的报告
        if saved_ids:
            # 找到收益最高的
            records = [manager.get_backtest(rid) for rid in saved_ids]
            best_record = max(records, key=lambda x: x.get('total_return_pct', -float('inf')))
            
            # 重建results用于导出
            best_results = best_record['results']
            exporter = ReportExporter(best_results)
            html_path = exporter.export_html()
            assert Path(html_path).exists()
            
            # 清理
            Path(html_path).unlink()
        
        # 清理历史记录
        for record_id in saved_ids:
            manager.delete_backtest(record_id)
    
    def test_data_download_and_backtest(self):
        """测试数据下载到回测的流程
        
        注意：需要网络连接，可能较慢
        """
        # 此测试需要实际数据源，可以设置为skipif
        pytest.skip("需要实际数据源，跳过")
        
        # 实际流程（参考）：
        # 1. 下载数据
        # from dquant2.core.data.downloader import DataDownloader
        # downloader.download_single('000001', ...)
        
        # 2. 验证数据质量
        # from dquant2.core.data.quality_checker import DataQualityChecker
        # checker.run_full_check(df, '000001')
        
        # 3. 运行回测
        # engine = BacktestEngine(config)
        # results = engine.run()
        
        # 4. 分析结果
        # assert results['portfolio']['total_value'] > 0


class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_config(self):
        """测试无效配置的错误处理"""
        from dquant2.exceptions import BacktestConfigError
        
        # 测试无效日期
        with pytest.raises((ValueError, BacktestConfigError, AssertionError)):
            config = BacktestConfig(
                symbol='000001',
                start_date='invalid_date',  # 无效日期
                end_date='20231231',
                initial_cash=1000000
            )
            config.validate()
    
    def test_insufficient_data(self):
        """测试数据不足的错误处理"""
        # 测试时间范围太短
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230102',  # 只有1天
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='ma_cross',
            strategy_params={'fast_period': 5, 'slow_period': 20}
        )
        
        # 应该能运行但可能没有交易
        engine = BacktestEngine(config)
        results = engine.run()
        assert results is not None
        # 数据不足可能导致没有交易
        # assert len(results['trades']) == 0


class TestPerformanceOptimization:
    """性能优化测试"""
    
    def test_parallel_vs_sequential(self):
        """测试并行vs串行回测的性能对比"""
        import time
        
        symbols = ['000001', '000002', '600000']
        base_config = {
            'start_date': '20230101',
            'end_date': '20230630',
            'initial_cash': 1000000,
            'data_provider': 'mock',
            'strategy_name': 'ma_cross',
            'strategy_params': {'fast_period': 5, 'slow_period': 20}
        }
        
        # 1. 串行回测
        start_time = time.time()
        sequential_results = []
        for symbol in symbols:
            config = BacktestConfig(**{**base_config, 'symbol': symbol})
            engine = BacktestEngine(config)
            results = engine.run()
            sequential_results.append(results)
        sequential_time = time.time() - start_time
        
        # 2. 并行回测
        start_time = time.time()
        parallel = ParallelBacktest(max_workers=2)
        parallel_results = parallel.run_batch_for_symbols(symbols, base_config)
        parallel_time = time.time() - start_time
        
        # 3. 验证结果一致
        assert len(sequential_results) == len(symbols)
        assert len(parallel_results) == len(symbols)
        
        # 4. 性能对比
        print(f"\n串行耗时: {sequential_time:.2f}秒")
        print(f"并行耗时: {parallel_time:.2f}秒")
        print(f"加速比: {sequential_time/parallel_time:.2f}x")
        
        # 并行应该更快（在有多个CPU核心的情况下）
        # 注意：由于启动开销，小数据集可能看不到明显加速
        # assert parallel_time < sequential_time


if __name__ == '__main__':
    # 直接运行测试
    pytest.main([__file__, '-v', '-s'])
