"""增强回测示例

演示如何使用新增的风控、组合管理、数据质量等功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from dquant2 import BacktestEngine, BacktestConfig
from dquant2.core.risk.metrics import RiskMetrics, StopLossTracker
from dquant2.core.portfolio.cost_calculator import FIFOCostCalculator
from dquant2.core.data.quality_checker import DataQualityChecker
from dquant2.core.data.storage import SQLiteAdapter


def example_1_enhanced_backtest():
    """示例1: 使用增强风控的回测"""
    print("=" * 60)
    print("示例1: 增强风控回测")
    print("=" * 60)
    
    # 创建回测配置
    config = BacktestConfig(
        symbol='000001',
        start_date='20230101',
        end_date='20231231',
        initial_cash=1000000,
        data_provider='mock',
        strategy_name='ma_cross',
        strategy_params={'fast_period': 5, 'slow_period': 20},
        
        # 风控配置
        enable_risk_control=True,
        max_position_ratio=0.3,  # 单只最大30%
        
        # 使用FIFO成本计算
        # cost_method='fifo'  # 这个参数需要添加到 BacktestConfig
    )
    
    # 运行回测
    engine = BacktestEngine(config)
    results = engine.run()
    
    # 使用风险指标分析结果
    risk_metrics = RiskMetrics()
    
    for record in results['equity_curve']:
        risk_metrics.update_equity(record['equity'])
    
    # 计算风险指标
    print("\n【风险指标分析】")
    summary = risk_metrics.get_risk_summary()
    
    print(f"VaR (95%):         {summary['var_95']:.2f}%")
    print(f"CVaR (95%):        {summary['cvar_95']:.2f}%")
    print(f"最大回撤:          {summary['max_drawdown']:.2f}%")
    print(f"夏普比率:          {summary['sharpe_ratio']:.2f}")
    print(f"索提诺比率:        {summary['sortino_ratio']:.2f}")
    print(f"卡玛比率:          {summary['calmar_ratio']:.2f}")
    print(f"欧米茄比率:        {summary['omega_ratio']:.2f}")
    
    # 风险等级评估
    risk_level = risk_metrics.assess_risk_level()
    print(f"\n风险等级: {risk_level}")
    
    # 风险预警
    alerts = risk_metrics.get_risk_alerts()
    if alerts:
        print(f"\n【风险预警】")
        for alert in alerts:
            print(f"  {alert['level']}: {alert['message']}")
    
    print("\n" + "=" * 60)


def example_2_cost_calculation():
    """示例2: FIFO 成本计算"""
    print("\n" + "=" * 60)
    print("示例2: FIFO 成本计算")
    print("=" * 60)
    
    # 创建 FIFO 计算器
    calc = FIFOCostCalculator()
    
    # 模拟分批买入
    print("\n【买入记录】")
    calc.add_buy('000001', 1000, 10.0, datetime.now())
    print(f"第1批: 买入 1000股 @ 10.00")
    
    calc.add_buy('000001', 500, 12.0, datetime.now())
    print(f"第2批: 买入 500股 @ 12.00")
    
    calc.add_buy('000001', 800, 11.0, datetime.now())
    print(f"第3批: 买入 800股 @ 11.00")
    
    # 当前持仓
    total_qty = calc.get_total_quantity('000001')
    avg_cost = calc.get_avg_cost('000001')
    print(f"\n当前持仓: {total_qty} 股, 平均成本: {avg_cost:.2f}")
    
    # FIFO 卖出
    print("\n【FIFO 卖出】")
    sell_qty = 1200
    avg_sell_cost, details = calc.calculate_sell_cost('000001', sell_qty)
    
    print(f"卖出 {sell_qty} 股, FIFO平均成本: {avg_sell_cost:.2f}")
    print("\n成本明细:")
    for i, detail in enumerate(details, 1):
        print(f"  第{i}批: {detail['quantity']}股 @ {detail['cost']:.2f}")
    
    # 剩余持仓
    remaining = calc.get_total_quantity('000001')
    print(f"\n剩余持仓: {remaining} 股")
    
    print("=" * 60)


def example_3_data_quality():
    """示例3: 数据质量检查"""
    print("\n" + "=" * 60)
    print("示例3: 数据质量检查")
    print("=" * 60)
    
    # 创建测试数据
    import pandas as pd
    import numpy as np
    
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'open': np.random.uniform(9.8, 10.2, 100),
        'high': np.random.uniform(10.0, 10.5, 100),
        'low': np.random.uniform(9.5, 10.0, 100),
        'close': np.random.uniform(9.8, 10.2, 100),
        'volume': np.random.uniform(1000000, 2000000, 100)
    })
    
    # 添加一些问题数据
    df.loc[10, 'open'] = None  # 缺失值
    df.loc[20, 'high'] = 9.0   # 逻辑错误（high < low）
    df.loc[30, 'volume'] = 0   # 零成交量
    
    # 执行质量检查
    checker = DataQualityChecker()
    results = checker.run_full_check(df, '000001')
    
    # 显示报告
    report = checker.generate_report(results)
    print("\n" + report)


def example_4_sqlite_storage():
    """示例4: SQLite 数据持久化"""
    print("\n" + "=" * 60)
    print("示例4: SQLite 数据持久化")
    print("=" * 60)
    
    import pandas as pd
    import numpy as np
    
    # 创建适配器
    adapter = SQLiteAdapter()
    
    # 创建测试数据
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'open': np.random.uniform(10, 11, 10),
        'high': np.random.uniform(11, 12, 10),
        'low': np.random.uniform(9, 10, 10),
        'close': np.random.uniform(10, 11, 10),
        'volume': np.random.uniform(1000000, 2000000, 10)
    })
    
    # 保存数据
    print("\n保存数据到数据库...")
    rows = adapter.save_kline_data('TEST001', df)
    print(f"保存成功: {rows} 行")
    
    # 加载数据
    print("\n从数据库加载数据...")
    df_loaded = adapter.load_kline_data('TEST001')
    print(f"加载成功: {len(df_loaded)} 行")
    
    # 数据库统计
    print("\n数据库统计:")
    stats = adapter.get_database_stats()
    print(f"总股票数: {stats['total_symbols']}")
    print(f"总记录数: {stats['total_kline_records']}")
    print(f"数据库大小: {stats['db_size_mb']:.2f} MB")
    print(f"数据库路径: {stats['db_path']}")
    
    # 清理测试数据
    adapter.delete_kline_data('TEST001')
    print("\n测试数据已清理")
    
    adapter.close()
    print("=" * 60)


def example_5_parameter_optimization():
    """示例5: 参数优化（框架展示）"""
    print("\n" + "=" * 60)
    print("示例5: 参数优化框架")
    print("=" * 60)
    
    from dquant2.backtest.optimizer import GridSearchOptimizer
    
    # 定义回测函数
    def run_backtest(params):
        config = BacktestConfig(
            symbol='000001',
            start_date='20230101',
            end_date='20231231',
            initial_cash=1000000,
            data_provider='mock',
            strategy_name='ma_cross',
            strategy_params=params
        )
        
        engine = BacktestEngine(config)
        return engine.run()
    
    # 定义参数空间
    param_space = {
        'fast_period': [3, 5, 7, 10],
        'slow_period': [15, 20, 25, 30]
    }
    
    print(f"\n参数空间: {param_space}")
    print(f"总组合数: {len(param_space['fast_period']) * len(param_space['slow_period'])}")
    
    # 创建优化器
    optimizer = GridSearchOptimizer(
        backtest_func=run_backtest,
        param_space=param_space,
        objective='sharpe_ratio'
    )
    
    # 运行优化（示例，实际运行会很慢）
    print("\n提示: 实际运行会测试所有参数组合")
    print("这里仅演示框架，不实际执行")
    
    # results = optimizer.optimize()
    # print(f"\n最优参数: {results['best_params']}")
    # print(f"最优夏普: {results['best_score']:.2f}")
    
    print("=" * 60)


if __name__ == '__main__':
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         d-quant2 增强功能使用示例                          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # 运行示例
    example_1_enhanced_backtest()
    example_2_cost_calculation()
    example_3_data_quality()
    example_4_sqlite_storage()
    example_5_parameter_optimization()
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                   所有示例运行完成                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")
