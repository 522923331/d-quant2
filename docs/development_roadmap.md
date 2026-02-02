# d-quant2 开发路线图和任务清单

> 基于四个量化项目（QuantOL, qstock, OSkhQuant, sphinx-quant）的架构对比分析

---

## 🎯 阶段一：核心风控和组合管理（优先级 P0）

### 📋 任务 1.1：完善风控模块
**参考项目**: QuantOL/src/core/risk/risk_manager.py

- [ ] **订单验证机制**
  - [ ] 实现 `validate_order(order_event)` 方法
  - [ ] 实现 `_check_funds(order_event)` - 资金充足性检查
  - [ ] 实现 `_check_position_limit(order_event)` - 仓位比例检查
  - [ ] 实现 `_check_daily_loss_limit()` - 单日亏损限制
  - [ ] 添加单元测试

- [ ] **风险指标监控**
  - [ ] 实现 `calculate_var()` - 计算 VaR（风险价值）
  - [ ] 实现 `calculate_cvar()` - 计算 CVaR（条件风险价值）
  - [ ] 实现 `calculate_beta()` - 计算 Beta（市场相关性）
  - [ ] 实现 `calculate_sharpe()` - 夏普比率实时计算
  - [ ] 实现 `calculate_max_drawdown()` - 最大回撤实时计算
  - [ ] 添加风险指标可视化

- [ ] **止损止盈机制**
  - [ ] 实现固定止损/止盈
    ```python
    def check_stop_loss(self, position, current_price):
        loss_pct = (current_price - position.avg_cost) / position.avg_cost
        if loss_pct < -self.stop_loss_ratio:
            return True  # 触发止损
        return False
    ```
  - [ ] 实现移动止损/止盈
  - [ ] 实现时间止损（持仓超过N天自动平仓）
  - [ ] 添加止损止盈记录和统计

- [ ] **风险预警系统**
  - [ ] 实现风险等级评估（低、中、高）
  - [ ] 实现风险预警事件发布
  - [ ] 集成到 Streamlit 界面显示

**预计完成时间**: 1周
**关键文件**: 
- `dquant2/core/risk/manager.py`
- `dquant2/core/risk/metrics.py`（新建）
- `dquant2/core/risk/stop_loss.py`（新建）

---

### 📋 任务 1.2：完善投资组合模块
**参考项目**: QuantOL/src/core/portfolio/portfolio.py

- [ ] **缓存优化机制**
  - [ ] 实现 LRU 缓存装饰器
    ```python
    from functools import lru_cache
    
    @lru_cache(maxsize=128)
    def _calculate_portfolio_value_cached(self, timestamp):
        # 计算组合价值
        pass
    ```
  - [ ] 实现缓存失效策略（TTL=1秒）
  - [ ] 添加缓存命中率统计

- [ ] **成本计算方法**
  - [ ] 实现 FIFO（先进先出）成本计算
    ```python
    def update_position_fifo(self, symbol, quantity, price):
        if symbol not in self.positions:
            self.positions[symbol] = []
        if quantity > 0:  # 买入
            self.positions[symbol].append({
                'quantity': quantity,
                'price': price,
                'timestamp': datetime.now()
            })
        else:  # 卖出
            # FIFO 逻辑
            pass
    ```
  - [ ] 实现 LIFO（后进先出）成本计算
  - [ ] 实现加权平均成本计算
  - [ ] 添加成本计算方法配置选项

- [ ] **组合再平衡**
  - [ ] 实现 `calculate_rebalance(target_weights)` 方法
  - [ ] 实现最小交易成本路径算法
  - [ ] 实现再平衡模拟和预览
  - [ ] 添加再平衡历史记录

- [ ] **净值跟踪增强**
  - [ ] 优化 `record_equity()` 方法
  - [ ] 添加分时净值记录（可选）
  - [ ] 实现净值曲线平滑处理
  - [ ] 添加净值变化事件发布

- [ ] **持仓分析增强**
  - [ ] 实现 `get_positions_summary()` 方法
  - [ ] 添加行业/板块分布分析
  - [ ] 添加持仓集中度分析
  - [ ] 添加持仓收益排行榜

**预计完成时间**: 1.5周
**关键文件**: 
- `dquant2/core/portfolio/manager.py`
- `dquant2/core/portfolio/position.py`
- `dquant2/core/portfolio/cost_calculator.py`（新建）
- `dquant2/core/portfolio/rebalance.py`（新建）

---

## 🎯 阶段二：数据和回测扩展（优先级 P0-P1）

### 📋 任务 2.1：完善数据模块
**参考项目**: QuantOL/src/core/data/, qstock/data/

- [ ] **数据库持久化**
  - [ ] 实现 SQLite 适配器
    ```python
    # 参考 QuantOL/src/core/data/sqlite_adapter.py
    class SQLiteAdapter:
        def save_kline_data(self, symbol, df):
            # 保存K线数据到 SQLite
            pass
        
        def load_kline_data(self, symbol, start_date, end_date):
            # 从 SQLite 加载K线数据
            pass
    ```
  - [ ] 实现数据库表结构设计
    - `kline_data` - K线数据表
    - `stock_info` - 股票基本信息表
    - `fundamental_data` - 基本面数据表
  - [ ] 实现数据库迁移脚本
  - [ ] 添加数据库索引优化

- [ ] **字段映射器**
  - [ ] 实现 `FieldMapper` 类
    ```python
    class FieldMapper:
        FIELD_MAP = {
            'akshare': {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                # ...
            },
            'baostock': {
                'date': 'date',
                'open': 'open',
                # ...
            }
        }
        
        def map_fields(self, df, source):
            # 统一字段名
            pass
    ```
  - [ ] 添加字段类型转换
  - [ ] 添加字段验证

- [ ] **数据质量检查**
  - [ ] 实现完整性检查（缺失值检测）
  - [ ] 实现一致性检查（数据逻辑验证）
  - [ ] 实现异常值检测（基于统计方法）
  - [ ] 实现数据质量报告生成

- [ ] **基本面数据接口**
  - [ ] 实现财务报表数据接口
    - 资产负债表
    - 利润表
    - 现金流量表
  - [ ] 实现估值指标数据接口
    - PE, PB, PS, PCF
    - ROE, ROA
    - 毛利率、净利率
  - [ ] 集成到选股模块

- [ ] **宏观数据接口（可选）**
  - [ ] 实现宏观经济指标接口
    - GDP, CPI, PMI
    - 利率、汇率
  - [ ] 实现行业数据接口

**预计完成时间**: 2周
**关键文件**: 
- `dquant2/core/data/storage/sqlite_adapter.py`（新建）
- `dquant2/core/data/field_mapper.py`（新建）
- `dquant2/core/data/quality_checker.py`（新建）
- `dquant2/core/data/fundamental.py`（新建）

---

### 📋 任务 2.2：扩展回测引擎
**参考项目**: QuantOL/src/core/strategy/backtesting.py

- [ ] **订单类型扩展**
  - [ ] 实现 `Order` 类重构
    ```python
    class Order:
        def __init__(self, symbol, quantity, order_type='MARKET',
                     limit_price=None, stop_price=None):
            self.symbol = symbol
            self.quantity = quantity
            self.order_type = order_type  # MARKET, LIMIT, STOP, STOP_LIMIT
            self.limit_price = limit_price
            self.stop_price = stop_price
            self.status = 'PENDING'  # PENDING, FILLED, CANCELLED
    ```
  - [ ] 实现市价单执行逻辑
  - [ ] 实现限价单执行逻辑
  - [ ] 实现止损单执行逻辑
  - [ ] 实现止盈单执行逻辑
  - [ ] 添加订单状态跟踪

- [ ] **滑点模拟扩展**
  - [ ] 实现固定滑点模型
  - [ ] 实现比例滑点模型
  - [ ] 实现动态滑点模型（基于成交量）
    ```python
    def calculate_slippage(self, order, market_data):
        if self.slippage_type == 'FIXED':
            return self.slippage_value
        elif self.slippage_type == 'RATIO':
            return order.price * self.slippage_ratio
        elif self.slippage_type == 'DYNAMIC':
            # 基于成交量计算滑点
            volume_ratio = order.quantity / market_data['volume']
            return order.price * volume_ratio * self.impact_factor
    ```
  - [ ] 添加滑点模拟配置

- [ ] **策略参数优化**
  - [ ] 实现网格搜索
    ```python
    def grid_search(self, param_grid):
        results = []
        for params in product(*param_grid.values()):
            config = BacktestConfig(**dict(zip(param_grid.keys(), params)))
            result = self.run_backtest(config)
            results.append((params, result))
        return sorted(results, key=lambda x: x[1]['sharpe'], reverse=True)
    ```
  - [ ] 实现随机搜索
  - [ ] 实现贝叶斯优化（可选）
  - [ ] 添加参数优化可视化

- [ ] **回测性能优化**
  - [ ] 实现向量化计算（使用 numpy/pandas）
  - [ ] 实现多进程回测（并行参数优化）
  - [ ] 添加回测进度条

- [ ] **回测结果增强**
  - [ ] 添加更多性能指标
    - 卡玛比率（Calmar Ratio）
    - 欧米茄比率（Omega Ratio）
    - 盈亏比（Profit Factor）
  - [ ] 实现交易明细导出
  - [ ] 实现回测报告生成（PDF/HTML）

**预计完成时间**: 2周
**关键文件**: 
- `dquant2/backtest/engine.py`
- `dquant2/backtest/order.py`（新建）
- `dquant2/backtest/slippage.py`（新建）
- `dquant2/backtest/optimizer.py`（新建）

---

## 🎯 阶段三：规则引擎和交易执行（优先级 P1）

### 📋 任务 3.1：实现规则引擎（DSL）
**参考项目**: QuantOL/src/core/strategy/rule_parser.py

- [ ] **表达式解析器**
  - [ ] 实现词法分析器（Lexer）
    ```python
    class Lexer:
        def tokenize(self, expr):
            # "MA(5) > MA(20)" -> ['MA', '(', '5', ')', '>', 'MA', '(', '20', ')']
            pass
    ```
  - [ ] 实现语法分析器（Parser）
    ```python
    class Parser:
        def parse(self, tokens):
            # 构建抽象语法树（AST）
            pass
    ```
  - [ ] 实现表达式计算器（Evaluator）
    ```python
    class Evaluator:
        def evaluate(self, ast, data):
            # 计算表达式结果
            pass
    ```

- [ ] **指标函数库**
  - [ ] 支持 MA(period)
  - [ ] 支持 EMA(period)
  - [ ] 支持 RSI(period)
  - [ ] 支持 MACD(fast, slow, signal)
  - [ ] 支持 BOLL(period, std)
  - [ ] 支持 KDJ(n, m1, m2)
  - [ ] 支持 ATR(period)
  - [ ] 支持 VOLUME()
  - [ ] 支持自定义函数注册

- [ ] **运算符支持**
  - [ ] 比较运算符: `>`, `<`, `>=`, `<=`, `==`, `!=`
  - [ ] 逻辑运算符: `and`, `or`, `not`
  - [ ] 算术运算符: `+`, `-`, `*`, `/`, `%`

- [ ] **规则验证器**
  - [ ] 实现语法检查
  - [ ] 实现指标参数验证
  - [ ] 实现运行时错误处理

- [ ] **规则策略集成**
  - [ ] 实现 `RuleBasedStrategy` 类
    ```python
    class RuleBasedStrategy(BaseStrategy):
        def __init__(self, buy_rule, sell_rule):
            self.buy_rule = buy_rule
            self.sell_rule = sell_rule
            self.parser = RuleParser()
        
        def generate_signal(self, data):
            if self.parser.evaluate(self.buy_rule, data):
                return Signal.BUY
            elif self.parser.evaluate(self.sell_rule, data):
                return Signal.SELL
            return Signal.HOLD
    ```
  - [ ] 集成到回测引擎
  - [ ] 添加规则策略示例

**预计完成时间**: 2周
**关键文件**: 
- `dquant2/core/strategy/rule_parser.py`（新建）
- `dquant2/core/strategy/rule_based.py`（新建）
- `dquant2/core/strategy/indicators_lib.py`（新建）

---

### 📋 任务 3.2：实现交易执行模块
**参考项目**: QuantOL/src/core/execution/Trader.py

- [ ] **订单管理系统**
  - [ ] 实现 `OrderManager` 类
    ```python
    class OrderManager:
        def __init__(self):
            self.orders = {}  # order_id -> Order
            self.order_history = []
        
        def create_order(self, symbol, quantity, order_type, price=None):
            order = Order(symbol, quantity, order_type, price)
            self.orders[order.id] = order
            return order
        
        def cancel_order(self, order_id):
            if order_id in self.orders:
                self.orders[order_id].status = 'CANCELLED'
        
        def get_active_orders(self):
            return [o for o in self.orders.values() if o.status == 'PENDING']
    ```
  - [ ] 实现订单ID生成
  - [ ] 实现订单状态跟踪
  - [ ] 实现订单历史记录

- [ ] **成交回报机制**
  - [ ] 实现模拟成交引擎
    ```python
    class SimulatedExecution:
        def execute_market_order(self, order, current_price):
            # 市价单立即成交
            fill_price = current_price * (1 + self.slippage)
            return Fill(order, fill_price, order.quantity)
        
        def execute_limit_order(self, order, current_price):
            # 限价单条件成交
            if order.side == 'BUY' and current_price <= order.limit_price:
                return Fill(order, order.limit_price, order.quantity)
            elif order.side == 'SELL' and current_price >= order.limit_price:
                return Fill(order, order.limit_price, order.quantity)
            return None
    ```
  - [ ] 实现成交确认
  - [ ] 实现成交通知（事件发布）

- [ ] **执行引擎**
  - [ ] 实现 `ExecutionEngine` 类
    ```python
    class ExecutionEngine:
        def __init__(self, portfolio, risk_manager, order_manager):
            self.portfolio = portfolio
            self.risk_manager = risk_manager
            self.order_manager = order_manager
        
        def process_signal(self, signal_event):
            # 将信号转换为订单
            order = self.create_order_from_signal(signal_event)
            
            # 风险检查
            if not self.risk_manager.validate_order(order):
                return False
            
            # 提交订单
            self.order_manager.create_order(order)
            return True
        
        def process_market_data(self, market_event):
            # 检查待成交订单
            for order in self.order_manager.get_active_orders():
                fill = self.execute_order(order, market_event.price)
                if fill:
                    self.portfolio.update_position(fill)
    ```
  - [ ] 集成风控模块
  - [ ] 集成投资组合模块

- [ ] **交易日志**
  - [ ] 实现交易日志记录
  - [ ] 实现交易统计
  - [ ] 实现交易审计

**预计完成时间**: 1.5周
**关键文件**: 
- `dquant2/core/execution/__init__.py`（新建）
- `dquant2/core/execution/order_manager.py`（新建）
- `dquant2/core/execution/execution_engine.py`（新建）
- `dquant2/core/execution/simulated.py`（新建）

---

## 🎯 阶段四：高级功能（优先级 P2）

### 📋 任务 4.1：实盘交易接口
**参考项目**: sphinx-quant, OSkhQuant

- [ ] **券商API适配器**
  - [ ] 设计统一的券商接口
  - [ ] 实现东方财富接口（可选）
  - [ ] 实现同花顺接口（可选）

- [ ] **实盘下单**
  - [ ] 实现实盘订单提交
  - [ ] 实现实盘订单查询
  - [ ] 实现实盘持仓查询

- [ ] **实盘监控**
  - [ ] 实现实盘监控界面
  - [ ] 实现实时盈亏监控
  - [ ] 实现异常预警

**预计完成时间**: 3周
**关键文件**: 
- `dquant2/core/execution/broker/__init__.py`（新建）
- `dquant2/core/execution/broker/base.py`（新建）

---

### 📋 任务 4.2：机器学习策略
**参考项目**: AShare-AI-Stock-Picker

- [ ] **特征工程**
  - [ ] 实现技术指标特征
  - [ ] 实现基本面特征
  - [ ] 实现因子特征

- [ ] **模型训练**
  - [ ] 集成 scikit-learn
  - [ ] 集成 LightGBM/XGBoost
  - [ ] 实现模型训练流程

- [ ] **模型预测**
  - [ ] 实现在线预测
  - [ ] 实现模型评估
  - [ ] 集成到策略系统

**预计完成时间**: 3周
**关键文件**: 
- `dquant2/ml/__init__.py`（新建）
- `dquant2/ml/features.py`（新建）
- `dquant2/ml/models.py`（新建）

---

## 📊 进度跟踪

### 已完成任务
- [x] 基础回测引擎
- [x] 数据下载和缓存
- [x] 基础策略框架
- [x] Streamlit 界面
- [x] 选股模块

### 进行中任务
- [ ] 风控模块完善
- [ ] 投资组合模块完善

### 待开始任务
- [ ] 数据持久化
- [ ] 规则引擎
- [ ] 交易执行模块

---

## 🎯 里程碑

### 里程碑 1: 核心系统完善 (6周)
- 完成风控模块
- 完成投资组合模块
- 完成数据持久化
- 完成回测引擎扩展

### 里程碑 2: 高级功能 (4周)
- 完成规则引擎
- 完成交易执行模块
- 完成参数优化

### 里程碑 3: 实盘和ML (6周)
- 完成实盘交易接口
- 完成机器学习策略

---

## ⚠️ 注意事项

### 代码质量要求
1. **参考现有项目**：严格按照 QuantOL 等项目的代码风格
2. **单元测试**：每个新功能必须有单元测试
3. **文档**：每个公共方法必须有文档字符串
4. **代码审查**：每次提交前自我审查

### 开发原则
1. **渐进式开发**：每次只修改一个模块
2. **充分测试**：每次修改后运行完整测试套件
3. **版本控制**：频繁提交，保持小步快跑
4. **向后兼容**：保持现有接口的兼容性

### 测试策略
1. **单元测试**：pytest
2. **集成测试**：完整回测流程测试
3. **性能测试**：大数据量回测测试
4. **回归测试**：与现有项目对比验证

---

**更新时间**: 2026-02-02
**版本**: v1.0
