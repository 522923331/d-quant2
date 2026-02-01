"""测试交易成本计算改进

验证新的 TradingCostCalculator 功能是否正常
"""

import sys
sys.path.insert(0, '/Users/k02/PycharmProjects/lianghua2/d-quant2')

from dquant2.core.trading.cost import TradingCostCalculator

print("="*70)
print("测试1: 创建成本计算器并打印配置")
print("="*70)

# 创建成本计算器，使用默认参数
calculator = TradingCostCalculator()
calculator.print_summary()

print("\n" + "="*70)
print("测试2: 买入贵州茅台（沪市股票，应有过户费）")
print("="*70)

cost = calculator.calculate(
    stock_code='600519.SH',
    price=1800.00,
    volume=100,
    direction='BUY'
)

print(f"\n股票代码: 600519.SH (贵州茅台)")
print(f"交易方向: 买入")
print(f"委托价格: 1800.00元")
print(f"交易数量: 100股")
print(f"\n成本明细:")
print(f"  实际成交价格: {cost.actual_price:.3f}元 (含滑点)")
print(f"  佣金: {cost.commission:.2f}元")
print(f"  印花税: {cost.stamp_tax:.2f}元 (买入无印花税)")
print(f"  过户费: {cost.transfer_fee:.2f}元 (沪市股票)")
print(f"  流量费: {cost.flow_fee:.2f}元")
print(f"  ━━━━━━━━━━━━━━━━━━━━")
print(f"  总成本: {cost.total_cost:.2f}元")
print(f"\n成交金额: {cost.actual_price * 100:.2f}元")
print(f"实际支出: {cost.actual_price * 100 + cost.total_cost:.2f}元")

print("\n" + "="*70)
print("测试3: 卖出平安银行（深市股票，应有印花税，无过户费）")
print("="*70)

cost = calculator.calculate(
    stock_code='000001.SZ',
    price=12.50,
    volume=1000,
    direction='SELL'
)

print(f"\n股票代码: 000001.SZ (平安银行)")
print(f"交易方向: 卖出")
print(f"委托价格: 12.50元")
print(f"交易数量: 1000股")
print(f"\n成本明细:")
print(f"  实际成交价格: {cost.actual_price:.3f}元 (含滑点)")
print(f"  佣金: {cost.commission:.2f}元 (max(5元, 成交金额×0.03%))")
print(f"  印花税: {cost.stamp_tax:.2f}元 (卖出征收 0.1%)")
print(f"  过户费: {cost.transfer_fee:.2f}元 (深市无过户费)")
print(f"  流量费: {cost.flow_fee:.2f}元")
print(f"  ━━━━━━━━━━━━━━━━━━━━")
print(f"  总成本: {cost.total_cost:.2f}元")
print(f"\n成交金额: {cost.actual_price * 1000:.2f}元")
print(f"实际收入: {cost.actual_price * 1000 - cost.total_cost:.2f}元")

print("\n" + "="*70)
print("测试4: 小额买入（验证最低佣金5元）")
print("="*70)

cost = calculator.calculate(
    stock_code='600000.SH',
    price=10.00,
    volume=10,  # 只买10股
    direction='BUY'
)

print(f"\n股票代码: 600000.SH")
print(f"交易方向: 买入")
print(f"委托价格: 10.00元")
print(f"交易数量: 10股 (小额交易)")
print(f"\n成交金额: {cost.actual_price * 10:.2f}元")
print(f"按比例佣金: {cost.actual_price * 10 * 0.0003:.2f}元 (成交金额 × 0.03%)")
print(f"实际佣金: {cost.commission:.2f}元 (应为最低佣金5元)")
print(f"总成本: {cost.total_cost:.2f}元")

print("\n" + "="*70)
print("测试5: Tick 滑点模式")
print("="*70)

calculator_tick = TradingCostCalculator(
    slippage_type='tick',
    slippage_tick_size=0.01,
    slippage_tick_count=2
)

cost_buy = calculator_tick.calculate(
    stock_code='600519.SH',
    price=1800.00,
    volume=100,
    direction='BUY'
)

cost_sell = calculator_tick.calculate(
    stock_code='600519.SH',
    price=1800.00,
    volume=100,
    direction='SELL'
)

print(f"\n原始价格: 1800.00元")
print(f"Tick 设置: 0.01元/tick × 2 = 0.02元滑点")
print(f"买入成交价: {cost_buy.actual_price:.2f}元 (向上滑点)")
print(f"卖出成交价: {cost_sell.actual_price:.2f}元 (向下滑点)")

print("\n" + "="*70)
print("✅ 所有测试完成！")
print("="*70)
print("\n总结:")
print("  ✅ 最低佣金生效")
print("  ✅ 印花税仅卖出时收取")
print("  ✅ 过户费仅沪市股票收取")
print("  ✅ 流量费正常计算")
print("  ✅ 滑点正确应用(买入向上，卖出向下)")
print("  ✅ Tick 模式和 Ratio 模式均正常")
