"""投资组合管理器"""

from datetime import datetime
from typing import Dict, List, Optional
import logging
import time
from functools import lru_cache

from dquant2.core.portfolio.position import Position
from dquant2.core.event_bus.events import FillEvent

logger = logging.getLogger(__name__)


class Portfolio:
    """投资组合管理器
    
    负责：
    1. 持仓管理
    2. 资金管理
    3. 盈亏统计
    4. 绩效跟踪
    5. 缓存优化（参考 QuantOL）
    """
    
    def __init__(self, initial_cash: float, commission_rate: float = 0.0003,
                 enable_t0_mode: bool = False, cost_method: str = 'weighted_avg'):
        """初始化组合
        
        Args:
            initial_cash: 初始资金
            commission_rate: 佣金费率
            enable_t0_mode: 是否启用T+0模式（ETF或期权）
            cost_method: 成本计算方法 ('fifo', 'lifo', 'weighted_avg')
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.enable_t0_mode = enable_t0_mode
        self.cost_method = cost_method
        
        # 持仓字典 {symbol: Position}
        self.positions: Dict[str, Position] = {}
        
        # 交易记录
        self.trades: List[Dict] = []
        
        # 权益曲线 - 将由回测过程中的record_equity()调用来填充
        self.equity_curve: List[Dict] = []
        
        # 统计信息
        self.total_commission = 0.0
        self.realized_pnl = 0.0
        
        # 缓存相关（参考 QuantOL）
        self._portfolio_value_cache: Optional[float] = None
        self._positions_value_cache: Optional[float] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 1.0  # 缓存有效期 1 秒
        self._last_update_time: float = time.time()
        
        # 峰值和回撤跟踪
        self._peak_value: float = initial_cash
        self._max_drawdown: float = 0.0
        
        # 成本计算器
        self._cost_calculator = None
        self._init_cost_calculator()
    
    def _init_cost_calculator(self):
        """初始化成本计算器"""
        from dquant2.core.portfolio.cost_calculator import (
            FIFOCostCalculator, LIFOCostCalculator, WeightedAverageCostCalculator
        )
        
        if self.cost_method == 'fifo':
            self._cost_calculator = FIFOCostCalculator()
        elif self.cost_method == 'lifo':
            self._cost_calculator = LIFOCostCalculator()
        else:  # weighted_avg
            self._cost_calculator = WeightedAverageCostCalculator()
        
        logger.info(f"成本计算方法: {self.cost_method}")
    
    def invalidate_cache(self):
        """使缓存失效
        
        在持仓或现金变动时调用，使缓存失效以保证数据一致性
        """
        self._portfolio_value_cache = None
        self._positions_value_cache = None
        self._last_update_time = time.time()
    
    def update_fill(self, fill: FillEvent):
        """更新成交
        
        Args:
            fill: 成交事件
        """
        symbol = fill.symbol
        
        if fill.direction == 'BUY':
            self._handle_buy(fill)
        else:  # SELL
            self._handle_sell(fill)
        
        # 记录交易
        self.trades.append({
            'timestamp': fill.timestamp,
            'symbol': symbol,
            'direction': fill.direction,
            'quantity': fill.quantity,
            'price': fill.price,
            'commission': fill.commission,
            'fill_id': fill.fill_id
        })
        
        # 更新佣金统计
        self.total_commission += fill.commission
        
        # 使缓存失效
        self.invalidate_cache()
        
        logger.info(
            f"成交更新: {fill.direction} {symbol} "
            f"{fill.quantity}@{fill.price:.2f}, "
            f"现金余额: {self.cash:.2f}"
        )
    
    def _handle_buy(self, fill: FillEvent):
        """处理买入"""
        symbol = fill.symbol
        cost = fill.total_cost
        
        # 检查现金
        if cost > self.cash:
            logger.error(f"现金不足: 需要 {cost:.2f}, 可用 {self.cash:.2f}")
            return
        
        # 扣除现金
        self.cash -= cost
        
        # 更新持仓
        if symbol not in self.positions:
            # 判断是否为ETF（T+0）
            is_t0 = self._is_etf(symbol) or self.enable_t0_mode
            
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=fill.quantity,
                available_quantity=fill.quantity if is_t0 else 0,  # T+0立即可用
                avg_price=fill.price,
                current_price=fill.price,
                last_update=fill.timestamp,
                is_t0_mode=is_t0
            )
            
            logger.info(
                f"新建持仓: {symbol} (模式: {'T+0' if is_t0 else 'T+1'}), "
                f"持仓:{fill.quantity}, 可用:{fill.quantity if is_t0 else 0}"
            )
        else:
            self.positions[symbol].add_quantity(fill.quantity, fill.price)
            self.positions[symbol].update_price(fill.price, fill.timestamp)
            
            pos = self.positions[symbol]
            logger.info(
                f"增加持仓: {symbol}, "
                f"持仓:{pos.quantity}, 可用:{pos.available_quantity}"
            )
    
    def _handle_sell(self, fill: FillEvent):
        """处理卖出"""
        symbol = fill.symbol
        
        if symbol not in self.positions:
            logger.error(f"无持仓: {symbol}")
            return
        
        position = self.positions[symbol]
        
        if fill.quantity > position.quantity:
            logger.error(
                f"卖出数量超过持仓: {fill.quantity} > {position.quantity}"
            )
            return
        
        # 计算实现盈亏，使用实际成交价格
        realized = position.reduce_quantity(fill.quantity, sell_price=fill.price)
        self.realized_pnl += realized
        
        # 增加现金
        self.cash += fill.total_cost
        
        # 如果仓位清空，删除持仓记录
        if position.quantity == 0:
            del self.positions[symbol]
    
    def update_prices(self, prices: Dict[str, float], timestamp: datetime):
        """更新所有持仓价格
        
        Args:
            prices: {symbol: price}
            timestamp: 时间戳
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price, timestamp)
    
    def get_total_value(self) -> float:
        """获取组合总价值（带缓存优化）
        
        参考 QuantOL 的缓存机制，提升性能
        """
        current_time = time.time()
        
        # 检查缓存是否有效
        if (self._portfolio_value_cache is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._portfolio_value_cache
        
        # 计算组合价值
        positions_value = self.get_positions_value()
        total_value = self.cash + positions_value
        
        # 更新缓存
        self._portfolio_value_cache = total_value
        self._cache_timestamp = current_time
        
        # 更新峰值和回撤
        self._update_peak_and_drawdown(total_value)
        
        return total_value
    
    def get_positions_value(self) -> float:
        """获取持仓总市值（带缓存优化）"""
        current_time = time.time()
        
        # 检查缓存是否有效
        if (self._positions_value_cache is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._positions_value_cache
        
        # 计算持仓市值
        positions_value = sum(pos.market_value for pos in self.positions.values())
        
        # 更新缓存
        self._positions_value_cache = positions_value
        
        return positions_value
    
    def _update_peak_and_drawdown(self, current_value: float):
        """更新峰值和最大回撤
        
        Args:
            current_value: 当前组合价值
        """
        # 更新峰值
        if current_value > self._peak_value:
            self._peak_value = current_value
        
        # 计算当前回撤
        if self._peak_value > 0:
            current_drawdown = (self._peak_value - current_value) / self._peak_value
            
            # 更新最大回撤
            if current_drawdown > self._max_drawdown:
                self._max_drawdown = current_drawdown
                logger.debug(f"最大回撤更新: {self._max_drawdown*100:.2f}%")
    
    def get_current_drawdown(self) -> float:
        """获取当前回撤
        
        Returns:
            当前回撤百分比
        """
        current_value = self.get_total_value()
        if self._peak_value > 0:
            return (self._peak_value - current_value) / self._peak_value * 100
        return 0.0
    
    def get_max_drawdown(self) -> float:
        """获取最大回撤
        
        Returns:
            最大回撤百分比
        """
        return self._max_drawdown * 100
    
    def get_position(self, symbol: str) -> Position:
        """获取指定持仓"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """是否持有该股票"""
        return symbol in self.positions and self.positions[symbol].quantity > 0
    
    def get_unrealized_pnl(self) -> float:
        """获取未实现盈亏"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def get_total_pnl(self) -> float:
        """获取总盈亏（已实现 + 未实现）"""
        return self.realized_pnl + self.get_unrealized_pnl()
    
    def record_equity(self, timestamp: datetime):
        """记录权益曲线（增强版）
        
        记录更详细的信息，包括回撤、峰值等
        """
        total_value = self.get_total_value()
        current_drawdown = self.get_current_drawdown()
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': total_value,
            'cash': self.cash,
            'positions_value': self.get_positions_value(),
            'return_pct': (total_value / self.initial_cash - 1) * 100,
            'drawdown_pct': current_drawdown,
            'peak_value': self._peak_value,
            'num_positions': len(self.positions)
        })
    
    def get_equity_curve(self) -> List[Dict]:
        """获取权益曲线"""
        return self.equity_curve.copy()
    
    def get_trade_history(self) -> List[Dict]:
        """获取交易历史"""
        return self.trades.copy()
    
    def get_summary(self) -> Dict:
        """获取组合摘要"""
        total_value = self.get_total_value()
        total_pnl = self.get_total_pnl()
        
        return {
            'initial_cash': self.initial_cash,
            'current_cash': self.cash,
            'positions_value': self.get_positions_value(),
            'total_value': total_value,
            'total_return': total_value - self.initial_cash,
            'total_return_pct': (total_value / self.initial_cash - 1) * 100,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.get_unrealized_pnl(),
            'total_pnl': total_pnl,
            'total_commission': self.total_commission,
            'num_trades': len(self.trades),
            'num_positions': len(self.positions)
        }
    
    def _is_etf(self, symbol: str) -> bool:
        """判断是否为ETF（T+0模式）
        
        ETF代码特征：
        - 沪市: 51xxxx.SH, 56xxxx.SH
        - 深市: 15xxxx.SZ, 16xxxx.SZ
        
        Args:
            symbol: 股票代码
            
        Returns:
            是否为ETF
        """
        # 去除后缀，只看代码
        code = symbol.split('.')[0] if '.' in symbol else symbol
        
        # ETF代码规则
        if code.startswith('51') or code.startswith('56'):  # 沪市ETF
            return True
        if code.startswith('15') or code.startswith('16'):  # 深市ETF
            return True
        
        return False
    
    def unlock_positions_for_next_day(self):
        """解锁T+1持仓（每个交易日开盘时调用）
        
        将所有T+1持仓的数量解锁为可用
        """
        for position in self.positions.values():
            if not position.is_t0_mode:
                position.unlock_available()
    
    def get_positions_summary(self) -> Dict:
        """获取持仓汇总（增强版）
        
        Returns:
            持仓汇总字典
        """
        if not self.positions:
            return {
                'total_symbols': 0,
                'total_value': 0.0,
                'total_cost': 0.0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'positions': []
            }
        
        positions_list = []
        total_value = 0.0
        total_cost = 0.0
        
        for symbol, pos in self.positions.items():
            pos_dict = {
                'symbol': symbol,
                'quantity': pos.quantity,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'market_value': pos.market_value,
                'cost_basis': pos.quantity * pos.avg_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct,
                'weight': 0.0  # 稍后计算
            }
            positions_list.append(pos_dict)
            total_value += pos.market_value
            total_cost += pos.quantity * pos.avg_price
        
        # 计算权重
        portfolio_value = self.get_total_value()
        for pos_dict in positions_list:
            if portfolio_value > 0:
                pos_dict['weight'] = pos_dict['market_value'] / portfolio_value * 100
        
        # 按市值排序
        positions_list.sort(key=lambda x: x['market_value'], reverse=True)
        
        return {
            'total_symbols': len(self.positions),
            'total_value': total_value,
            'total_cost': total_cost,
            'total_pnl': total_value - total_cost,
            'total_pnl_pct': (total_value / total_cost - 1) * 100 if total_cost > 0 else 0.0,
            'positions': positions_list
        }
    
    def get_concentration_analysis(self) -> Dict:
        """获取持仓集中度分析
        
        Returns:
            集中度分析字典
        """
        if not self.positions:
            return {
                'top1_weight': 0.0,
                'top3_weight': 0.0,
                'top5_weight': 0.0,
                'herfindahl_index': 0.0
            }
        
        portfolio_value = self.get_total_value()
        
        # 计算各持仓权重
        weights = []
        for pos in self.positions.values():
            weight = pos.market_value / portfolio_value if portfolio_value > 0 else 0.0
            weights.append(weight)
        
        # 按权重排序
        weights.sort(reverse=True)
        
        # 计算集中度指标
        top1_weight = weights[0] * 100 if len(weights) >= 1 else 0.0
        top3_weight = sum(weights[:3]) * 100 if len(weights) >= 3 else sum(weights) * 100
        top5_weight = sum(weights[:5]) * 100 if len(weights) >= 5 else sum(weights) * 100
        
        # Herfindahl 指数（赫芬达尔指数）- 衡量集中度
        # H = Σ(wi^2)，H越大表示越集中
        herfindahl_index = sum(w**2 for w in weights)
        
        return {
            'top1_weight': top1_weight,
            'top3_weight': top3_weight,
            'top5_weight': top5_weight,
            'herfindahl_index': herfindahl_index,
            'concentration_level': self._assess_concentration(herfindahl_index)
        }
    
    def _assess_concentration(self, herfindahl_index: float) -> str:
        """评估集中度等级
        
        Args:
            herfindahl_index: 赫芬达尔指数
            
        Returns:
            集中度等级
        """
        if herfindahl_index > 0.5:
            return '高度集中'
        elif herfindahl_index > 0.25:
            return '中度集中'
        else:
            return '分散'
    
    def get_top_positions(self, n: int = 5) -> List[Dict]:
        """获取前N大持仓
        
        Args:
            n: 返回数量
            
        Returns:
            持仓列表
        """
        summary = self.get_positions_summary()
        return summary['positions'][:n]
    
    def get_profit_ranking(self) -> List[Dict]:
        """获取盈利排行
        
        Returns:
            按盈亏排序的持仓列表
        """
        positions_list = []
        
        for symbol, pos in self.positions.items():
            positions_list.append({
                'symbol': symbol,
                'quantity': pos.quantity,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct
            })
        
        # 按盈亏百分比排序
        positions_list.sort(key=lambda x: x['unrealized_pnl_pct'], reverse=True)
        
        return positions_list
