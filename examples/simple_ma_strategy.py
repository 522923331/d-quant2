"""简单的双均线策略回测示例

演示如何使用 d-quant2 进行回测
"""

import logging

from dquant2 import BacktestEngine, BacktestConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """运行双均线策略回测"""
    
    # 创建回测配置
    config = BacktestConfig(
        symbol='000001',           # 股票代码（模拟数据）
        start_date='20200101',     # 开始日期
        end_date='20231231',       # 结束日期
        initial_cash=1000000,      # 初始资金100万
        
        # 数据配置
        data_provider='mock',      # 使用模拟数据
        data_freq='d',             # 日线数据
        
        # 策略配置
        strategy_name='ma_cross',  # 双均线策略
        strategy_params={
            'fast_period': 5,      # 快线周期
            'slow_period': 20,     # 慢线周期
        },
        
        # 资金管理
        capital_strategy='fixed_ratio',  # 固定比例
        capital_params={'ratio': 0.2},   # 每次使用20%资金
        
        # 交易成本
        commission_rate=0.0003,    # 万3佣金
        slippage=0.001,            # 0.1%滑点
        
        # 风控
        max_position_ratio=0.5,    # 单只最大50%仓位
        enable_risk_control=True,
    )
    
    # 创建回测引擎
    engine = BacktestEngine(config)
    
    # 运行回测
    results = engine.run()
    
    # 输出详细结果
    print("\n" + "=" * 80)
    print("详细回测结果")
    print("=" * 80)
    
    print("\n【配置信息】")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    
    print("\n【权益曲线】（最后10条）")
    equity_curve = results['equity_curve'][-10:]
    for record in equity_curve:
        print(f"  {record['timestamp']}: 权益={record['equity']:,.2f}, "
              f"现金={record['cash']:,.2f}, 持仓={record['positions_value']:,.2f}")
    
    print("\n【交易记录】")
    trades = results['trades']
    if trades:
        for trade in trades[:10]:  # 只显示前10条
            print(f"  {trade['timestamp']}: {trade['direction']} "
                  f"{trade['symbol']} {trade['quantity']}@{trade['price']:.2f}")
        if len(trades) > 10:
            print(f"  ... 还有 {len(trades) - 10} 条交易")
    else:
        print("  无交易")
    
    print("\n【事件统计】")
    for key, value in results['event_stats'].items():
        print(f"  {key}: {value}")
    
    return results


if __name__ == '__main__':
    results = main()
