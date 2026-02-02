"""新功能演示示例

展示 v2.1 版本新增的所有功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dquant2 import BacktestEngine, BacktestConfig
from dquant2.utils.logging_config import setup_logging, set_log_level, get_logger
from dquant2.exceptions import ExceptionHandler, handle_exceptions
from dquant2.backtest.report_exporter import export_report
from dquant2.backtest.history_manager import BacktestHistoryManager, save_backtest_to_history
from dquant2.backtest.parallel_backtest import parallel_backtest_symbols, optimize_parameters


# 配置日志
setup_logging(log_level='INFO', enable_color=True, log_to_console=True, log_to_file=False)
logger = get_logger(__name__)


def demo_exception_handling():
    """演示异常处理"""
    print("\n" + "=" * 60)
    print("演示1: 异常处理")
    print("=" * 60)
    
    from dquant2.exceptions import DataNotFoundError, BacktestConfigError
    
    # 1. 抛出自定义异常
    try:
        raise DataNotFoundError(
            "股票数据未找到",
            details={'symbol': '000001', 'date': '20230101'}
        )
    except DataNotFoundError as e:
        error_info = ExceptionHandler.handle(e, context="加载数据", logger=logger)
        print(f"捕获异常: {error_info}")
    
    # 2. 使用装饰器
    @handle_exceptions(context="演示函数", default="默认值")
    def risky_function():
        raise ValueError("模拟错误")
    
    result = risky_function()
    print(f"使用装饰器的函数返回: {result}")


def demo_logging_config():
    """演示日志配置"""
    print("\n" + "=" * 60)
    print("演示2: 日志级别配置")
    print("=" * 60)
    
    # 切换到DEBUG级别
    print("切换到DEBUG级别...")
    set_log_level('DEBUG')
    
    logger.debug("这是DEBUG日志（现在可见）")
    logger.info("这是INFO日志")
    logger.warning("这是WARNING日志")
    
    # 切换回INFO级别
    print("\n切换回INFO级别...")
    set_log_level('INFO')
    
    logger.debug("这是DEBUG日志（现在不可见）")
    logger.info("这是INFO日志（可见）")


def demo_new_strategies():
    """演示新策略"""
    print("\n" + "=" * 60)
    print("演示3: 新增策略")
    print("=" * 60)
    
    strategies = [
        {
            'name': 'grid_trading',
            'display': '网格交易策略',
            'params': {
                'base_price': 10.0,
                'grid_num': 5,
                'grid_spacing': 0.02
            }
        },
        {
            'name': 'momentum',
            'display': '动量策略',
            'params': {
                'momentum_period': 20,
                'buy_threshold': 5.0,
                'sell_threshold': -3.0,
                'volume_confirm': True
            }
        },
        {
            'name': 'mean_reversion',
            'display': '均值回归策略',
            'params': {
                'ma_period': 20,
                'std_period': 20,
                'entry_std': 2.0,
                'exit_std': 0.5
            }
        }
    ]
    
    for strategy_info in strategies:
        print(f"\n测试 {strategy_info['display']}...")
        
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20230630',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name=strategy_info['name'],
            strategy_params=strategy_info['params']
        )
        
        engine = BacktestEngine(config)
        results = engine.run()
        
        print(f"  总收益率: {results['portfolio']['total_return_pct']:.2f}%")
        print(f"  夏普比率: {results['performance']['sharpe_ratio']:.2f}")
        print(f"  交易次数: {results['portfolio']['num_trades']}")


def demo_report_export():
    """演示报告导出"""
    print("\n" + "=" * 60)
    print("演示4: 报告导出")
    print("=" * 60)
    
    # 运行一个回测
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
    
    # 导出HTML报告
    html_path = export_report(results, format='html')
    print(f"✅ HTML报告已生成: {html_path}")
    
    # 导出PDF（需要安装依赖）
    # try:
    #     pdf_path = export_report(results, format='pdf')
    #     print(f"✅ PDF报告已生成: {pdf_path}")
    # except Exception as e:
    #     print(f"⚠️ PDF导出失败（需要安装 pdfkit 和 wkhtmltopdf）: {e}")


def demo_parallel_backtest():
    """演示并行回测"""
    print("\n" + "=" * 60)
    print("演示5: 并行回测")
    print("=" * 60)
    
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
    def progress_callback(message, current, total):
        print(f"  [{current}/{total}] {message}")
    
    # 并行回测
    print(f"并行回测 {len(symbols)} 只股票...")
    results = parallel_backtest_symbols(
        symbols,
        base_config,
        max_workers=2,
        progress_callback=progress_callback
    )
    
    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    print(f"\n✅ 完成 {success_count}/{len(results)} 个回测")
    
    # 显示结果
    for result in results:
        if result['success']:
            symbol = result['config']['symbol']
            ret = result['portfolio']['total_return_pct']
            print(f"  {symbol}: {ret:.2f}%")


def demo_history_management():
    """演示历史记录管理"""
    print("\n" + "=" * 60)
    print("演示6: 历史记录管理")
    print("=" * 60)
    
    manager = BacktestHistoryManager()
    
    # 1. 运行回测并保存
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
    
    # 保存到历史
    record_id = save_backtest_to_history(
        results,
        notes="新功能演示",
        tags=['demo', 'ma_cross', '2023']
    )
    print(f"✅ 回测记录已保存，ID: {record_id}")
    
    # 2. 查询记录
    record = manager.get_backtest(record_id)
    print(f"\n查询记录:")
    print(f"  股票: {record['symbol']}")
    print(f"  策略: {record['strategy_name']}")
    print(f"  收益率: {record['total_return_pct']:.2f}%")
    
    # 3. 列出所有记录
    all_records = manager.list_backtests(limit=10)
    print(f"\n历史记录数: {len(all_records)}")
    
    # 4. 高级搜索
    good_results = manager.search_backtests(
        min_return=0.0,    # 收益率>0%
        min_sharpe=0.5,    # 夏普>0.5
        tags=['ma_cross']
    )
    print(f"优秀回测数: {len(good_results)}")
    
    # 5. 获取统计
    stats = manager.get_statistics()
    print(f"\n统计信息:")
    print(f"  总记录数: {stats['total_count']}")
    print(f"  平均收益率: {stats['avg_performance']['avg_return']:.2f}%")
    
    # 清理（演示完删除）
    print(f"\n清理演示记录...")
    manager.delete_backtest(record_id)


def demo_parameter_optimization():
    """演示参数优化"""
    print("\n" + "=" * 60)
    print("演示7: 参数优化")
    print("=" * 60)
    
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
    
    print(f"参数网格: {param_grid}")
    print(f"总组合数: {len(param_grid['fast_period']) * len(param_grid['slow_period'])}")
    
    # 进度回调
    def progress_callback(message, current, total):
        print(f"  [{current}/{total}] {message}")
    
    # 执行优化
    results = optimize_parameters(
        base_config,
        param_grid,
        max_workers=2,
        progress_callback=progress_callback
    )
    
    # 显示前3个最佳结果
    print(f"\n✅ 优化完成，找到 {len(results)} 个有效结果")
    print("\n前3个最佳参数:")
    
    for i, result in enumerate(results[:3]):
        params = result['config']['strategy_params']
        ret = result['portfolio']['total_return_pct']
        sharpe = result['performance']['sharpe_ratio']
        print(f"  {i+1}. 参数: {params}")
        print(f"     收益率: {ret:.2f}%, 夏普: {sharpe:.2f}")


def main():
    """主函数"""
    print("=" * 60)
    print("d-quant2 新功能演示")
    print("=" * 60)
    
    # 运行所有演示
    demo_exception_handling()
    demo_logging_config()
    demo_new_strategies()
    demo_report_export()
    demo_parallel_backtest()
    demo_history_management()
    demo_parameter_optimization()
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n提示:")
    print("- 查看生成的HTML报告: reports/")
    print("- 查看历史记录数据库: data/db/backtest_history.db")
    print("- 查看日志文件: logs/")


if __name__ == '__main__':
    main()
