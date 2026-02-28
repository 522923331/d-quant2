"""回测引擎

事件驱动的回测引擎实现
"""

from datetime import datetime
from typing import Optional
import logging

from dquant2.backtest.config import BacktestConfig
from dquant2.core.event_bus import EventBus
from dquant2.core.event_bus.events import (
    MarketDataEvent, SignalEvent, OrderEvent, FillEvent
)
from dquant2.core.data import DataManager
from dquant2.core.data.providers import MockDataProvider, AkShareProvider, BaostockProvider
from dquant2.core.strategy import StrategyFactory
from dquant2.core.risk import RiskManager
from dquant2.core.risk.manager import MaxPositionControl, CashControl
from dquant2.core.capital.fixed_ratio import FixedRatioStrategy
from dquant2.core.capital.kelly import KellyStrategy
from dquant2.core.portfolio import Portfolio
from dquant2.backtest.metrics import PerformanceMetrics
from dquant2.core.trading.cost import TradingCostCalculator  # 新增

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎
    
    核心组件：
    1. EventBus: 事件总线
    2. DataManager: 数据管理
    3. Strategy: 策略
    4. RiskManager: 风控
    5. Portfolio: 投资组合
    6. CapitalStrategy: 资金管理
    
    事件流：
    MarketData -> Strategy -> Signal -> Capital -> Order -> Risk -> Fill -> Portfolio
    """

    def __init__(self, config: BacktestConfig):
        """初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config
        config.validate()

        # 初始化事件总线
        self.event_bus = EventBus(enable_logging=config.enable_logging)

        # 初始化数据管理器
        provider = self._create_data_provider(config.data_provider)
        self.data_manager = DataManager(provider)

        # 初始化策略
        # 导入所有策略模块以触发注册
        from dquant2.core.strategy.hypothesis import (
            ma_cross, rsi_strategy, macd_strategy, bollinger_strategy,
            grid_trading, momentum_strategy, mean_reversion
        )
        self.strategy = StrategyFactory.create(
            config.strategy_name,
            params=config.strategy_params
        )

        # 初始化投资组合
        self.portfolio = Portfolio(
            initial_cash=config.initial_cash,
            commission_rate=config.commission_rate,  # 佣金率
            enable_t0_mode=config.enable_t0_mode  # T+0/T+1模式
        )

        # 初始化风控
        self.risk_manager = RiskManager(self.portfolio)
        if config.enable_risk_control:
            self.risk_manager.add_control(
                MaxPositionControl(config.max_position_ratio)
            )
            self.risk_manager.add_control(CashControl())

        # 初始化资金管理
        self.capital_strategy = self._create_capital_strategy(
            config.capital_strategy,
            config.capital_params
        )
        
        # 初始化交易成本计算器（新增）
        self.cost_calculator = TradingCostCalculator(
            min_commission=config.min_commission,
            commission_rate=config.commission_rate,
            stamp_tax_rate=config.stamp_tax_rate,
            transfer_fee_rate=config.transfer_fee_rate,
            flow_fee=config.flow_fee,
            slippage_type=config.slippage_type,
            slippage_tick_size=config.slippage_tick_size,
            slippage_tick_count=config.slippage_tick_count,
            slippage_ratio=config.slippage_ratio,
            price_decimals=2  # 默认股票精度，可以根据ETF动态调整
        )

        # 回测状态
        self.current_time: Optional[datetime] = None
        self.current_bar = None
        self.is_running = False
        self.pending_orders = []  # 挂单队列，用于存次日执行的订单

        # 注册事件处理器
        self._register_handlers()

        logger.info("回测引擎初始化完成")
        
        # 打印成本配置
        logger.info("\n" + "="*60)
        logger.info("交易成本配置")
        logger.info("="*60)
        logger.info(f"最低佣金: {config.min_commission}元")
        logger.info(f"佣金比例: {config.commission_rate*100}%")
        logger.info(f"印花税率: {config.stamp_tax_rate*100}%（仅卖出）")
        logger.info(f"过户费率: {config.transfer_fee_rate*100}%（沪市股票）")
        logger.info(f"流量费: {config.flow_fee}元/笔")
        logger.info(f"滑点类型: {config.slippage_type}")
        if config.slippage_type == 'tick':
            logger.info(f"  tick大小: {config.slippage_tick_size}元")
            logger.info(f"  tick跳数: {config.slippage_tick_count}")
        else:
            logger.info(f"  滑点比例: {config.slippage_ratio*100}%")
        logger.info("="*60 + "\n")

    def _create_data_provider(self, provider_name: str):
        """创建数据提供者"""
        if provider_name == 'mock':
            return MockDataProvider()
        elif provider_name == 'akshare':
            return AkShareProvider()
        elif provider_name == 'baostock':
            return BaostockProvider()
        elif provider_name == 'local_db':
            from dquant2.core.data.providers.local_db_provider import LocalDBProvider
            return LocalDBProvider()
        else:
            raise ValueError(f"未知的数据提供者: {provider_name}")

    def _create_capital_strategy(self, strategy_name: str, params: dict):
        """创建资金管理策略"""
        if strategy_name == 'fixed_ratio':
            return FixedRatioStrategy(**params)
        elif strategy_name == 'kelly':
            return KellyStrategy(**params)
        else:
            raise ValueError(f"未知的资金管理策略: {strategy_name}")

    def _register_handlers(self):
        """注册事件处理器"""
        self.event_bus.subscribe('market_data', self._on_market_data)
        self.event_bus.subscribe('signal', self._on_signal)
        self.event_bus.subscribe('order', self._on_order)
        self.event_bus.subscribe('fill', self._on_fill)

    def _on_market_data(self, event: MarketDataEvent):
        """处理市场数据事件"""
        # 更新组合中的持仓价格
        prices = {event.symbol: event.data['close']}
        self.portfolio.update_prices(prices, event.timestamp)

        # 策略处理数据并生成信号
        signals = self.strategy.on_data(event)

        # 发布信号事件
        for signal in signals:
            self.event_bus.publish('signal', signal)

    def _on_signal(self, event: SignalEvent):
        """处理信号事件"""
        # 通过资金管理计算仓位
        current_price = self.current_bar['close']

        if event.signal_type == 'BUY':
            quantity = self.capital_strategy.calculate_position_size(
                signal=event,
                portfolio_value=self.portfolio.get_total_value(),
                cash=self.portfolio.cash,
                current_price=current_price
            )
        elif event.signal_type == 'SELL':
            # 卖出：清空持仓 (次日开盘执行时已解锁)
            position = self.portfolio.get_position(event.symbol)
            quantity = position.quantity if position else 0
        else:  # HOLD
            return

        if quantity <= 0:
            return

        # 创建订单
        order = OrderEvent(
            timestamp=event.timestamp,
            symbol=event.symbol,
            order_type='MARKET',
            direction=event.signal_type,
            quantity=quantity,
            price=current_price,
            strategy_id=event.strategy_id
        )

        self.event_bus.publish('order', order)

    def _on_order(self, event: OrderEvent):
        """处理订单事件"""
        # A股交易为次日开盘价执行，暂存到挂单队列中
        self.pending_orders.append(event)

    def _simulate_fill(self, order: OrderEvent) -> FillEvent:
        """模拟订单成交
        
        使用 TradingCostCalculator 进行完整的成本计算
        """
        # 使用新的成本计算器
        cost_detail = self.cost_calculator.calculate(
            stock_code=order.symbol,
            price=order.price,
            volume=order.quantity,
            direction=order.direction
        )
        
        # 记录详细成本
        logger.debug(
            f"交易成本 - {order.symbol} {order.direction} "
            f"{order.quantity}@{order.price:.3f} -> "
            f"实际价格:{cost_detail.actual_price:.3f}, "
            f"佣金:{cost_detail.commission:.2f}, "
            f"印花税:{cost_detail.stamp_tax:.2f}, "
            f"过户费:{cost_detail.transfer_fee:.2f}, "
            f"流量费:{cost_detail.flow_fee:.2f}, "
            f"总成本:{cost_detail.total_cost:.2f}"
        )
        
        fill = FillEvent(
            timestamp=self.current_time,
            symbol=order.symbol,
            quantity=order.quantity,
            price=cost_detail.actual_price,  # 使用考虑滑点后的价格
            commission=cost_detail.total_cost,  # 总成本
            direction=order.direction,
            order_id=order.order_id
        )

        return fill

    def _on_fill(self, event: FillEvent):
        """处理成交事件"""
        self.portfolio.update_fill(event)

    def run(self) -> dict:
        """运行回测
        
        Returns:
            回测结果字典
        """
        logger.info("=" * 60)
        logger.info(f"开始回测: {self.config.symbol}")
        logger.info(f"时间范围: {self.config.start_date} - {self.config.end_date}")
        logger.info(f"初始资金: {self.config.initial_cash:,.2f}")
        logger.info(f"策略: {self.config.strategy_name}")
        logger.info("=" * 60)

        self.is_running = True
        self.strategy.on_start()

        # 加载数据
        data = self.data_manager.prepare_backtest_data(
            symbol=self.config.symbol,
            start=self.config.start_date,
            end=self.config.end_date,
            freq=self.config.data_freq
        )

        total_bars = len(data)
        logger.info(f"数据加载完成，共 {total_bars} 条")

        # 事件循环
        prev_date = None  # 用于检测新交易日
        for i, (timestamp, bar) in enumerate(data.iterrows()):
            self.current_time = timestamp
            self.current_bar = bar

            # ── 新交易日开始：解锁 T+1 持仓 ──────────────────────────
            current_date = timestamp.date()
            if prev_date is None or current_date > prev_date:
                self.portfolio.unlock_positions_for_next_day()
                logger.debug(f"新交易日 {current_date}：T+1 持仓已解锁")
                
                # ── 处理前一日的挂单（以今日开盘价成交） ──
                open_price = bar['open']
                for order in self.pending_orders:
                    order.price = open_price
                    order.timestamp = timestamp
                    
                    # 校验资金与可用仓位（由于开盘价与昨日收盘价有跳空）
                    if order.direction == 'BUY':
                        est_cost = order.quantity * open_price * 1.005 # 预估滑点和佣金上限
                        if est_cost > self.portfolio.cash:
                            max_shares = int(self.portfolio.cash / (open_price * 1.005) / 100) * 100
                            if max_shares > 0:
                                logger.info(f"开盘跳空调整买单数量: {order.quantity} -> {max_shares}")
                                order.quantity = max_shares
                            else:
                                continue
                    elif order.direction == 'SELL':
                        pos = self.portfolio.get_position(order.symbol)
                        avail_qty = pos.available_quantity if pos else 0
                        order.quantity = min(order.quantity, avail_qty)
                        if order.quantity <= 0:
                            continue
                            
                    # 取重新调整的订单经过风控
                    if self.config.enable_risk_control:
                        is_valid, messages = self.risk_manager.validate_order(order)
                        if not is_valid:
                            logger.warning(f"挂单风控拒绝: {'; '.join(messages)}")
                            continue
                            
                    fill = self._simulate_fill(order)
                    self.event_bus.publish('fill', fill)
                    
                self.pending_orders.clear()
                
            prev_date = current_date
            # ──────────────────────────────────────────────────────────

            # 创建市场数据事件
            event = MarketDataEvent(
                timestamp=timestamp,
                symbol=self.config.symbol,
                data=bar
            )

            # 发布事件
            self.event_bus.publish('market_data', event)

            # 记录权益曲线
            self.portfolio.record_equity(timestamp)

            # 进度显示
            if (i + 1) % 100 == 0 or i == total_bars - 1:
                progress = (i + 1) / total_bars * 100
                logger.info(f"进度: {progress:.1f}% ({i + 1}/{total_bars})")


        self.strategy.on_stop()
        self.is_running = False

        # 生成回测报告
        results = self._generate_report()

        logger.info("=" * 60)
        logger.info("回测完成")
        logger.info("=" * 60)

        return results

    def _generate_report(self) -> dict:
        """生成回测报告"""
        # 获取组合摘要
        portfolio_summary = self.portfolio.get_summary()

        # 计算性能指标
        metrics = PerformanceMetrics(self.portfolio)
        performance = metrics.calculate()

        # 合并结果
        results = {
            'config': self.config.to_dict(),
            'portfolio': portfolio_summary,
            'performance': performance,
            'equity_curve': self.portfolio.get_equity_curve(),
            'trades': self.portfolio.get_trade_history(),
            'event_stats': self.event_bus.get_stats(),
        }

        # 打印关键指标
        self._print_summary(portfolio_summary, performance)

        return results

    def _print_summary(self, portfolio: dict, performance: dict):
        """打印摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("回测结果摘要")
        logger.info("=" * 60)

        logger.info(f"\n【资金情况】")
        logger.info(f"初始资金: {portfolio['initial_cash']:,.2f}")
        logger.info(f"最终资金: {portfolio['total_value']:,.2f}")
        logger.info(f"现金余额: {portfolio['current_cash']:,.2f}")
        logger.info(f"持仓市值: {portfolio['positions_value']:,.2f}")

        logger.info(f"\n【收益情况】")
        logger.info(f"总收益: {portfolio['total_return']:,.2f}")
        logger.info(f"总收益率: {portfolio['total_return_pct']:.2f}%")
        logger.info(f"年化收益率: {performance['annual_return']:.2f}%")

        logger.info(f"\n【风险指标】")
        logger.info(f"最大回撤: {performance['max_drawdown']:.2f}%")
        logger.info(f"夏普比率: {performance['sharpe_ratio']:.2f}")
        logger.info(f"波动率: {performance['volatility']:.2f}%")

        logger.info(f"\n【交易统计】")
        logger.info(f"交易次数: {portfolio['num_trades']}")
        logger.info(f"总手续费: {portfolio['total_commission']:,.2f}")
        logger.info(f"当前持仓数: {portfolio['num_positions']}")

        if performance['win_rate'] is not None:
            logger.info(f"\n【胜率分析】")
            logger.info(f"胜率: {performance['win_rate']:.2f}%")
            logger.info(f"盈亏比: {performance['profit_loss_ratio']:.2f}")

        logger.info("=" * 60 + "\n")
