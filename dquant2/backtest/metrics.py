"""绩效指标计算

计算各种回测性能指标
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """绩效指标计算器
    
    计算：
    - 收益率指标
    - 风险指标  
    - 风险调整指标
    - 交易统计
    """
    
    def __init__(self, portfolio):
        """初始化
        
        Args:
            portfolio: Portfolio对象
        """
        self.portfolio = portfolio
    
    def calculate(self) -> Dict:
        """计算所有指标"""
        equity_curve = pd.DataFrame(self.portfolio.get_equity_curve())
        
        if len(equity_curve) < 2:
            return self._empty_metrics()
        
        equity_curve.set_index('timestamp', inplace=True)
        
        # 计算收益率序列
        returns = equity_curve['equity'].pct_change().dropna()
        
        metrics = {}
        
        # 收益率指标
        metrics.update(self._calculate_returns(equity_curve, returns))
        
        # 风险指标
        metrics.update(self._calculate_risk(equity_curve, returns))
        
        # 风险调整指标
        metrics.update(self._calculate_risk_adjusted(returns))
        
        # 交易统计
        metrics.update(self._calculate_trade_stats())
        
        return metrics
    
    def _calculate_returns(self, equity_curve: pd.DataFrame, returns: pd.Series) -> Dict:
        """计算收益率指标"""
        initial_value = equity_curve['equity'].iloc[0]
        final_value = equity_curve['equity'].iloc[-1]
        
        total_return = (final_value / initial_value - 1) * 100
        
        # 年化收益率 - 确保timestamp索引是datetime类型
        # 检查索引是否是datetime类型，如果不是则转换
        if not pd.api.types.is_datetime64_any_dtype(equity_curve.index):
            logger.info(f"索引类型不是datetime，当前类型: {equity_curve.index.dtype}，正在转换...")
            equity_curve.index = pd.to_datetime(equity_curve.index)
        
        # 计算时间跨度
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        years = days / 365.0
        
        # 添加日志以便调试
        logger.info(f"年化收益率计算 - 初始:{equity_curve.index[0]}, 结束:{equity_curve.index[-1]}, 天数:{days}, 年数:{years:.4f}, 初始值:{initial_value:.2f}, 最终值:{final_value:.2f}")
        
        annual_return = (pow(final_value / initial_value, 1 / years) - 1) * 100 if years > 0 else 0
        
        logger.info(f"年化收益率计算结果: {annual_return:.2f}%")
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
        }
    
    def _calculate_risk(self, equity_curve: pd.DataFrame, returns: pd.Series) -> Dict:
        """计算风险指标"""
        # 最大回撤
        cummax = equity_curve['equity'].cummax()
        drawdown = (equity_curve['equity'] - cummax) / cummax * 100
        max_drawdown = drawdown.min()
        
        # 波动率（年化）
        volatility = returns.std() * np.sqrt(252) * 100
        
        return {
            'max_drawdown': max_drawdown,
            'volatility': volatility,
        }
    
    def _calculate_risk_adjusted(self, returns: pd.Series) -> Dict:
        """计算风险调整指标"""
        # 无风险利率假设为3%
        risk_free_rate = 0.03 / 252
        
        # 夏普比率
        excess_returns = returns - risk_free_rate
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # 索提诺比率（只考虑下行波动）
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = excess_returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
        }
    
    def _calculate_trade_stats(self) -> Dict:
        """计算交易统计（FIFO配对方式）"""
        trades = self.portfolio.get_trade_history()

        if len(trades) < 2:
            return {
                'num_trades': len(trades),
                'win_rate': None,
                'profit_loss_ratio': None,
            }

        # ── FIFO 配对：每次卖出消耗最早的买入记录 ──────────────────────
        buy_queue: list = []   # 元素: {'price': float, 'quantity': int, 'comm_per_share': float}
        trade_pnls: list = []  # 每笔完整交易的盈亏额

        for t in trades:
            if t['direction'] == 'BUY':
                comm_per_share = t['commission'] / t['quantity'] if t['quantity'] > 0 else 0
                buy_queue.append({'price': t['price'], 'quantity': t['quantity'], 'comm_per_share': comm_per_share})
            elif t['direction'] == 'SELL':
                remaining = t['quantity']
                sell_price = t['price']
                sell_comm_per_share = t['commission'] / t['quantity'] if t['quantity'] > 0 else 0
                while remaining > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched = min(remaining, buy['quantity'])
                    pnl = matched * (sell_price - buy['price'] - buy['comm_per_share'] - sell_comm_per_share)
                    trade_pnls.append(pnl)
                    remaining -= matched
                    buy['quantity'] -= matched
                    if buy['quantity'] == 0:
                        buy_queue.pop(0)

        if not trade_pnls:
            return {
                'num_trades': len(trades),
                'win_rate': None,
                'profit_loss_ratio': None,
            }

        # 胜率
        winning = [p for p in trade_pnls if p > 0]
        losing  = [abs(p) for p in trade_pnls if p < 0]
        win_rate = len(winning) / len(trade_pnls) * 100

        # 盈亏比
        avg_win  = float(sum(winning) / len(winning)) if winning else 0.0
        avg_loss = float(sum(losing)  / len(losing))  if losing  else 1.0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        return {
            'num_trades': len(trades),
            'num_complete_trades': len(trade_pnls),
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
        }
    
    def _empty_metrics(self) -> Dict:
        """返回空指标"""
        return {
            'total_return': 0,
            'annual_return': 0,
            'max_drawdown': 0,
            'volatility': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'num_trades': 0,
            'win_rate': None,
            'profit_loss_ratio': None,
        }
