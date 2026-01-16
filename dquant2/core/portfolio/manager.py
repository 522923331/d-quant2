"""投资组合管理器"""

from datetime import datetime
from typing import Dict, List
import logging

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
    """
    
    def __init__(self, initial_cash: float, commission_rate: float = 0.0003):
        """初始化组合
        
        Args:
            initial_cash: 初始资金
            commission_rate: 佣金费率
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        
        # 持仓字典 {symbol: Position}
        self.positions: Dict[str, Position] = {}
        
        # 交易记录
        self.trades: List[Dict] = []
        
        # 权益曲线 - 将由回测过程中的record_equity()调用来填充
        self.equity_curve: List[Dict] = []
        
        # 统计信息
        self.total_commission = 0.0
        self.realized_pnl = 0.0
    
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
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=fill.quantity,
                avg_price=fill.price,
                current_price=fill.price,
                last_update=fill.timestamp
            )
        else:
            self.positions[symbol].add_quantity(fill.quantity, fill.price)
            self.positions[symbol].update_price(fill.price, fill.timestamp)
    
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
        
        # 计算实现盈亏
        realized = position.reduce_quantity(fill.quantity)
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
        """获取组合总价值"""
        positions_value = sum(
            pos.market_value for pos in self.positions.values()
        )
        return self.cash + positions_value
    
    def get_positions_value(self) -> float:
        """获取持仓总市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
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
        """记录权益曲线"""
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': self.get_total_value(),
            'cash': self.cash,
            'positions_value': self.get_positions_value()
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
