"""MyTT 技术指标库使用示例

演示如何在策略中使用 MyTT 技术指标库
"""

import sys
sys.path.insert(0, '/Users/k02/PycharmProjects/lianghua2/d-quant2')

import numpy as np
import pandas as pd
from dquant2.indicators import MA, EMA, MACD, KDJ, RSI, BOLL, CROSS

print("="*70)
print("MyTT 技术指标库测试")
print("="*70)

# 模拟价格数据
np.random.seed(42)
closes = np.array([
    100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
    110, 112, 111, 113, 115, 114, 116, 118, 117, 119,
    120, 122, 121, 123, 125, 124, 126, 128, 127, 129
])
highs = closes + 1
lows = closes - 1
opens = (highs + lows) / 2

print(f"\n数据长度: {len(closes)} 条")
print(f"价格范围: {closes.min():.2f} - {closes.max():.2f}")

# 测试1: 移动平均线
print("\n" + "="*70)
print("测试1: 移动平均线 (MA)")
print("="*70)
ma5 = MA(closes, 5)
ma10 = MA(closes, 10)
ma20 = MA(closes, 20)

print(f"MA5 最新值: {ma5[-1]:.2f}")
print(f"MA10 最新值: {ma10[-1]:.2f}")
print(f"MA20 最新值: {ma20[-1]:.2f}")
print(f"MA5 > MA10: {ma5[-1] > ma10[-1]}")

# 测试2: 指数移动平均
print("\n" + "="*70)
print("测试2: 指数移动平均 (EMA)")
print("="*70)
ema12 = EMA(closes, 12)
ema26 = EMA(closes, 26)

print(f"EMA12 最新值: {ema12[-1]:.2f}")
print(f"EMA26 最新值: {ema26[-1]:.2f}")

# 测试3: MACD 指标
print("\n" + "="*70)
print("测试3: MACD 指标")
print("="*70)
dif, dea, macd = MACD(closes, 12, 26, 9)

print(f"DIF 最新值: {dif[-1]:.3f}")
print(f"DEA 最新值: {dea[-1]:.3f}")
print(f"MACD 最新值: {macd[-1]:.3f}")
print(f"MACD > 0: {macd[-1] > 0} (多头)")

# 测试4: KDJ 指标
print("\n" + "="*70)
print("测试4: KDJ 指标")
print("="*70)
k, d, j = KDJ(closes, highs, lows, 9, 3, 3)

print(f"K 最新值: {k[-1]:.2f}")
print(f"D 最新值: {d[-1]:.2f}")
print(f"J 最新值: {j[-1]:.2f}")

if j[-1] < 20:
    print("J值进入超卖区 (< 20)")
elif j[-1] > 80:
    print("J值进入超买区 (> 80)")
else:
    print("J值在正常区间")

# 测试5: RSI 指标
print("\n" + "="*70)
print("测试5: RSI 指标")
print("="*70)
rsi6 = RSI(closes, 6)
rsi12 = RSI(closes, 12)
rsi24 = RSI(closes, 24)

print(f"RSI6 最新值: {rsi6[-1]:.2f}")
print(f"RSI12 最新值: {rsi12[-1]:.2f}")
print(f"RSI24 最新值: {rsi24[-1]:.2f}")

if rsi6[-1] < 30:
    print("RSI6进入超卖区 (< 30)")
elif rsi6[-1] > 70:
    print("RSI6进入超买区 (> 70)")
else:
    print("RSI6在正常区间")

# 测试6: 布林带
print("\n" + "="*70)
print("测试6: 布林带 (BOLL)")
print("="*70)
upper, mid, lower = BOLL(closes, 20, 2)

print(f"上轨: {upper[-1]:.2f}")
print(f"中轨: {mid[-1]:.2f}")
print(f"下轨: {lower[-1]:.2f}")
print(f"当前价格: {closes[-1]:.2f}")

if closes[-1] > upper[-1]:
    print("价格突破上轨")
elif closes[-1] < lower[-1]:
    print("价格跌破下轨")
else:
    print("价格在通道内")

# 测试7: 金叉死叉判断
print("\n" + "="*70)
print("测试7: 金叉死叉 (CROSS)")
print("="*70)

# 创建金叉场景
fast_line = np.array([10, 11, 12, 13, 14])
slow_line = np.array([12, 12, 12, 12, 12])

is_golden_cross = CROSS(fast_line, slow_line)
print(f"快线: {fast_line}")
print(f"慢线: {slow_line}")
print(f"是否金叉: {is_golden_cross[-1] == 1}")

# 测试8: 策略示例 - 双均线+RSI
print("\n" + "="*70)
print("测试8: 策略示例 - 双均线 + RSI 过滤")
print("="*70)

ma5_latest = ma5[-1]
ma20_latest = ma20[-1]
rsi_latest = rsi12[-1]

print(f"\n当前状态:")
print(f"  MA5: {ma5_latest:.2f}")
print(f"  MA20: {ma20_latest:.2f}")
print(f"  RSI12: {rsi_latest:.2f}")

# 交易信号
if CROSS(ma5, ma20)[-1] == 1 and rsi_latest > 30:
    signal = "买入信号 (MA5金叉MA20 且 RSI > 30)"
elif CROSS(ma20, ma5)[-1] == 1:
    signal = "卖出信号 (MA5死叉MA20)"
else:
    signal = "无信号"

print(f"\n交易信号: {signal}")

print("\n" + "="*70)
print("✅ 所有MyTT指标测试完成！")
print("="*70)

print("\n支持的指标列表:")
print("  • 移动平均: MA, EMA, SMA, WMA")
print("  • 趋势指标: MACD, DMI, TRIX, DPO")
print("  • 振荡指标: RSI, KDJ, WR, CCI, PSY")
print("  • 通道指标: BOLL, SAR")
print("  • 成交量: OBV, VR, MFI, EMV")
print("  • 其他: BBI, BIAS, ATR, ROC, MTM")
print("  • 工具函数: CROSS, REF, HHV, LLV, STD")
