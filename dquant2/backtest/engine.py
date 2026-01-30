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
        # 导入策略模块以触发注册
        from dquant2.core.strategy.hypothesis import ma_cross
        self.strategy = StrategyFactory.create(
            config.strategy_name,
            params=config.strategy_params
        )

        # 初始化投资组合
        self.portfolio = Portfolio(
            initial_cash=config.initial_cash,
            commission_rate=config.commission_rate  # 佣金率
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

        # 回测状态
        self.current_time: Optional[datetime] = None
        self.current_bar = None
        self.is_running = False

        # 注册事件处理器
        self._register_handlers()

        logger.info("回测引擎初始化完成")

    def _create_data_provider(self, provider_name: str):
        """创建数据提供者"""
        if provider_name == 'mock':
            return MockDataProvider()
        elif provider_name == 'akshare':
            return AkShareProvider()
        elif provider_name == 'baostock':
            return BaostockProvider()
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
            # 卖出：清空持仓
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
        # 风控检查
        if self.config.enable_risk_control:
            is_valid, messages = self.risk_manager.validate_order(event)
            if not is_valid:
                logger.warning(f"订单被风控拒绝: {'; '.join(messages)}")
                return

        # 模拟成交
        fill = self._simulate_fill(event)
        self.event_bus.publish('fill', fill)

    def _simulate_fill(self, order: OrderEvent) -> FillEvent:
        """模拟订单成交
        
        在回测中，市价单立即成交
        滑点处理：买入时价格上滑，卖出时价格下滑，使滑点始终对交易者不利
        """
        if order.direction == 'BUY':
            fill_price = order.price * (1 + self.config.slippage)  # 买入时成交价更高
        else:
            fill_price = order.price * (1 - self.config.slippage)  # 卖出时成交价更低
        commission = order.quantity * fill_price * self.config.commission_rate

        fill = FillEvent(
            timestamp=self.current_time,
            symbol=order.symbol,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
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
        for i, (timestamp, bar) in enumerate(data.iterrows()):
            self.current_time = timestamp
            self.current_bar = bar

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
