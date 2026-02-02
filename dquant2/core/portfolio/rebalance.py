"""组合再平衡模块

实现投资组合再平衡策略，包括目标权重调整和最小成本路径
参考: QuantOL 投资组合架构
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RebalanceCalculator:
    """再平衡计算器
    
    计算如何从当前持仓调整到目标持仓，同时最小化交易成本
    """
    
    def __init__(self, commission_rate: float = 0.0003):
        """初始化再平衡计算器
        
        Args:
            commission_rate: 佣金费率
        """
        self.commission_rate = commission_rate
        self.rebalance_history = []
    
    def calculate_rebalance(self, 
                           current_positions: Dict[str, Dict],
                           target_weights: Dict[str, float],
                           portfolio_value: float,
                           current_prices: Dict[str, float],
                           min_trade_value: float = 1000.0) -> Dict:
        """计算再平衡方案
        
        Args:
            current_positions: 当前持仓 {symbol: {'quantity': x, 'value': y}}
            target_weights: 目标权重 {symbol: weight}
            portfolio_value: 组合总价值
            current_prices: 当前价格 {symbol: price}
            min_trade_value: 最小交易金额，默认 1000 元
            
        Returns:
            再平衡方案字典
        """
        # 1. 计算目标持仓价值
        target_values = {
            symbol: portfolio_value * weight 
            for symbol, weight in target_weights.items()
        }
        
        # 2. 计算当前持仓价值
        current_values = {
            symbol: pos['value'] 
            for symbol, pos in current_positions.items()
        }
        
        # 3. 计算需要调整的金额
        adjustments = {}
        for symbol in set(list(target_values.keys()) + list(current_values.keys())):
            target_val = target_values.get(symbol, 0.0)
            current_val = current_values.get(symbol, 0.0)
            diff = target_val - current_val
            
            # 只有调整金额超过最小交易金额才执行
            if abs(diff) >= min_trade_value:
                adjustments[symbol] = diff
        
        # 4. 转换为具体交易指令
        trades = []
        total_commission = 0.0
        
        for symbol, value_diff in adjustments.items():
            if symbol not in current_prices:
                logger.warning(f"再平衡: 缺少 {symbol} 的价格信息")
                continue
            
            price = current_prices[symbol]
            quantity = int(value_diff / price / 100) * 100  # 按手取整
            
            if quantity == 0:
                continue
            
            direction = 'BUY' if quantity > 0 else 'SELL'
            abs_quantity = abs(quantity)
            
            # 计算交易成本
            trade_value = abs_quantity * price
            commission = trade_value * self.commission_rate
            total_commission += commission
            
            trades.append({
                'symbol': symbol,
                'direction': direction,
                'quantity': abs_quantity,
                'price': price,
                'value': trade_value,
                'commission': commission,
                'target_weight': target_weights.get(symbol, 0.0),
                'current_weight': current_val / portfolio_value if portfolio_value > 0 else 0.0
            })
        
        # 5. 生成再平衡方案
        plan = {
            'trades': trades,
            'total_trades': len(trades),
            'total_commission': total_commission,
            'portfolio_value': portfolio_value,
            'timestamp': datetime.now(),
            'executed': False
        }
        
        logger.info(
            f"再平衡方案: {len(trades)} 笔交易, "
            f"预计手续费: {total_commission:.2f} 元"
        )
        
        return plan
    
    def optimize_trade_order(self, trades: List[Dict]) -> List[Dict]:
        """优化交易顺序
        
        先卖后买，减少资金占用
        
        Args:
            trades: 交易列表
            
        Returns:
            优化后的交易列表
        """
        # 分离买卖
        sells = [t for t in trades if t['direction'] == 'SELL']
        buys = [t for t in trades if t['direction'] == 'BUY']
        
        # 先卖后买
        optimized = sells + buys
        
        logger.debug(f"交易顺序优化: {len(sells)} 卖单 + {len(buys)} 买单")
        
        return optimized
    
    def record_rebalance(self, plan: Dict):
        """记录再平衡执行
        
        Args:
            plan: 再平衡方案
        """
        plan['executed'] = True
        plan['executed_at'] = datetime.now()
        self.rebalance_history.append(plan)
        
        logger.info(f"再平衡记录已保存，历史记录数: {len(self.rebalance_history)}")
    
    def get_rebalance_history(self) -> List[Dict]:
        """获取再平衡历史
        
        Returns:
            再平衡历史列表
        """
        return self.rebalance_history.copy()
    
    def calculate_turnover(self, trades: List[Dict], portfolio_value: float) -> float:
        """计算换手率
        
        Args:
            trades: 交易列表
            portfolio_value: 组合价值
            
        Returns:
            换手率（百分比）
        """
        if portfolio_value == 0:
            return 0.0
        
        total_trade_value = sum(t['value'] for t in trades)
        turnover = (total_trade_value / portfolio_value) * 100
        
        logger.debug(f"再平衡换手率: {turnover:.2f}%")
        
        return turnover


class PeriodicRebalancer:
    """定期再平衡器
    
    按照固定周期（月、季、年）自动触发再平衡
    """
    
    def __init__(self, 
                 target_weights: Dict[str, float],
                 rebalance_frequency: str = 'monthly',
                 threshold_pct: float = 0.05):
        """初始化定期再平衡器
        
        Args:
            target_weights: 目标权重
            rebalance_frequency: 再平衡频率 ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            threshold_pct: 偏差阈值，超过此比例才触发再平衡，默认 5%
        """
        self.target_weights = target_weights
        self.rebalance_frequency = rebalance_frequency
        self.threshold_pct = threshold_pct
        self.last_rebalance_date: Optional[datetime] = None
    
    def should_rebalance(self, 
                        current_date: datetime,
                        current_weights: Dict[str, float]) -> bool:
        """判断是否应该再平衡
        
        Args:
            current_date: 当前日期
            current_weights: 当前权重
            
        Returns:
            是否应该再平衡
        """
        # 1. 检查时间周期
        if not self._check_time_period(current_date):
            return False
        
        # 2. 检查权重偏差
        if not self._check_weight_deviation(current_weights):
            return False
        
        logger.info(f"触发再平衡: 时间周期到期且权重偏差超过阈值")
        return True
    
    def _check_time_period(self, current_date: datetime) -> bool:
        """检查时间周期
        
        Args:
            current_date: 当前日期
            
        Returns:
            是否到达再平衡时间
        """
        if self.last_rebalance_date is None:
            return True
        
        delta = current_date - self.last_rebalance_date
        
        if self.rebalance_frequency == 'daily':
            return delta.days >= 1
        elif self.rebalance_frequency == 'weekly':
            return delta.days >= 7
        elif self.rebalance_frequency == 'monthly':
            return delta.days >= 30
        elif self.rebalance_frequency == 'quarterly':
            return delta.days >= 90
        elif self.rebalance_frequency == 'yearly':
            return delta.days >= 365
        
        return False
    
    def _check_weight_deviation(self, current_weights: Dict[str, float]) -> bool:
        """检查权重偏差
        
        Args:
            current_weights: 当前权重
            
        Returns:
            权重偏差是否超过阈值
        """
        for symbol, target_weight in self.target_weights.items():
            current_weight = current_weights.get(symbol, 0.0)
            deviation = abs(current_weight - target_weight)
            
            if deviation > self.threshold_pct:
                logger.debug(
                    f"权重偏差: {symbol} "
                    f"目标 {target_weight:.2%}, 当前 {current_weight:.2%}, "
                    f"偏差 {deviation:.2%}"
                )
                return True
        
        return False
    
    def update_last_rebalance(self, rebalance_date: datetime):
        """更新最后再平衡日期
        
        Args:
            rebalance_date: 再平衡日期
        """
        self.last_rebalance_date = rebalance_date
        logger.info(f"更新再平衡日期: {rebalance_date}")
