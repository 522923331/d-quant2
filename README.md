# d-quant2

现代化量化回测系统

## 特点

✨ **事件驱动架构** - 基于EventBus的松耦合设计
🔌 **可插拔组件** - 策略、数据源、风控规则均可灵活替换
📊 **完整回测** - 精确的事件驱动回测模拟
📝 **全程审计** - 所有事件可追溯、可重现
🛡️ **多层风控** - 策略级、账户级、交易级风控
💰 **资金管理** - 固定比例、凯利公式等多种策略
📈 **性能分析** - 夏普比率、最大回撤等完整指标

## 核心原则

**解耦 + 可插拔 + 可回测 + 可审计 + 易维护**

## 系统链路

```
数据 → 假设 → 信号 → 风控 → 执行 → 资金 → 风险 → 生存
```

## 快速开始

### Web界面（推荐）

使用Streamlit Web界面进行交互式回测：

```bash
cd d-quant2

# 方法一：使用启动脚本
./start_web.sh

# 方法二：直接运行
streamlit run app.py
```

访问 **http://localhost:8501** 即可看到可视化界面！

![d-quant2 Web界面](file:///Users/k02/.gemini/antigravity/brain/23e7eb8b-e8d1-4903-a279-e207178a51ab/dquant2_web_ui_1768449164910.png)

**Web界面特点：**
- 🎨 **交互式配置** - 滑块调整参数，实时预览
- 📊 **可视化图表** - 权益曲线、回撤分析、交易记录
- 📈 **专业指标** - 夏普比率、索提诺比率、胜率分析
- 💾 **结果导出** - 下载配置和交易记录
- 🔄 **实时回测** - 点击按钮即可运行

详细使用说明：[WEB_GUIDE.md](WEB_GUIDE.md)

### 命令行方式



```bash
cd d-quant2
pip install -r requirements.txt
```

### 简单示例

```python
from dquant2 import BacktestEngine, BacktestConfig

# 配置回测
config = BacktestConfig(
    symbol='000001',
    start_date='20200101',
    end_date='20231231',
    initial_cash=1000000,
    strategy_name='ma_cross',
    strategy_params={
        'fast_period': 5,
        'slow_period': 20,
    }
)

# 运行回测
engine = BacktestEngine(config)
results = engine.run()

# 查看结果
print(results['portfolio'])
print(results['performance'])
```

### 运行示例

```bash
python examples/simple_ma_strategy.py
```

## 架构设计

### 核心模块

- **`core/event_bus`** - 事件总线，实现模块解耦
- **`core/data`** - 数据层，统一数据接口
- **`core/strategy`** - 策略层，可插拔策略系统
- **`core/risk`** - 风控层，多层次风控体系
- **`core/capital`** - 资金管理，多种仓位策略
- **`core/portfolio`** - 组合管理，持仓和盈亏跟踪
- **`backtest`** - 回测引擎，事件驱动回测

### 事件流

```
MarketDataEvent → Strategy → SignalEvent → Capital 
→ OrderEvent → Risk → FillEvent → Portfolio
```

## 自定义策略

```python
from dquant2.core.strategy import BaseStrategy, StrategyFactory
from dquant2.core.event_bus.events import MarketDataEvent, SignalEvent

@StrategyFactory.register("my_strategy")
class MyStrategy(BaseStrategy):
    def on_data(self, event: MarketDataEvent):
        # 实现策略逻辑
        signals = []
        
        # 生成信号
        if 某个条件:
            signal = SignalEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                signal_type='BUY',
                strength=1.0,
                strategy_id=self.strategy_id
            )
            signals.append(signal)
        
        return signals
```

## 项目结构

```
d-quant2/
├── dquant2/                   # 核心包
│   ├── core/                  # 核心模块
│   │   ├── event_bus/         # 事件总线
│   │   ├── data/              # 数据层
│   │   ├── strategy/          # 策略层
│   │   ├── risk/              # 风控层
│   │   ├── capital/           # 资金管理
│   │   └── portfolio/         # 组合管理
│   └── backtest/              # 回测引擎
├── examples/                  # 示例代码
├── tests/                     # 测试
└── docs/                      # 文档
```

## 内置策略

- **MACrossStrategy** - 双均线交叉策略

## 资金管理策略

- **FixedRatioStrategy** - 固定比例
- **KellyStrategy** - 凯利公式

## 风控规则

- **MaxPositionControl** - 最大仓位控制
- **CashControl** - 现金充足性控制

## 性能指标

- 总收益率 / 年化收益率
- 最大回撤
- 夏普比率 / 索提诺比率
- 波动率
- 胜率 / 盈亏比

## 路线图

- [x] 事件驱动框架
- [x] 数据管理层
- [x] 策略系统
- [x] 风控系统
- [x] 资金管理
- [x] 回测引擎
- [x] 性能指标
- [ ] 更多策略实现
- [ ] 实时数据源
- [ ] Web界面
- [ ] 策略优化器
- [ ] 实盘交易接口

## 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest tests/

# 运行示例
python examples/simple_ma_strategy.py
```

## 贡献

欢迎贡献代码、策略、文档！

## 许可证

MIT License

## 致谢

本项目综合了以下项目的优秀设计理念：
- **qstock** - 简洁的向量化回测
- **QuantOL** - 现代化事件驱动架构
- **vnpy** - 专业的量化交易框架
