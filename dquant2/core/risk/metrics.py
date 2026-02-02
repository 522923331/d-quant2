"""风险指标计算模块

提供各种风险度量指标的计算，包括 VaR, CVaR, Beta 等
参考: QuantOL 风控架构
"""

import numpy as np
import pandas as pd
from typing import List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskMetrics:
    """风险指标计算器
    
    计算各种风险度量指标，用于实时风险监控
    """
    
    def __init__(self):
        """初始化风险指标计算器"""
        self.equity_history: List[float] = []
        self.benchmark_returns: List[float] = []  # 基准收益率（可选）
        
    def update_equity(self, equity: float):
        """更新权益记录
        
        Args:
            equity: 当前权益值
        """
        self.equity_history.append(equity)
    
    def calculate_returns(self) -> np.ndarray:
        """计算收益率序列
        
        Returns:
            收益率数组
        """
        if len(self.equity_history) < 2:
            return np.array([])
        
        equity_array = np.array(self.equity_history)
        returns = np.diff(equity_array) / equity_array[:-1]
        return returns
    
    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """计算 VaR (Value at Risk) - 风险价值
        
        在给定置信水平下，投资组合在未来一段时间内可能遭受的最大损失
        
        Args:
            confidence_level: 置信水平，默认 95%
            
        Returns:
            VaR 值（百分比）
        """
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return 0.0
        
        # 使用历史模拟法计算 VaR
        var = np.percentile(returns, (1 - confidence_level) * 100)
        
        logger.debug(f"VaR ({confidence_level*100}%): {var*100:.2f}%")
        return var * 100  # 转换为百分比
    
    def calculate_cvar(self, confidence_level: float = 0.95) -> float:
        """计算 CVaR (Conditional VaR) - 条件风险价值
        
        超过 VaR 的损失的平均值，也称为期望短缺 (Expected Shortfall)
        
        Args:
            confidence_level: 置信水平，默认 95%
            
        Returns:
            CVaR 值（百分比）
        """
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return 0.0
        
        # 先计算 VaR
        var = np.percentile(returns, (1 - confidence_level) * 100)
        
        # CVaR 是所有小于 VaR 的收益率的平均值
        cvar = returns[returns <= var].mean()
        
        logger.debug(f"CVaR ({confidence_level*100}%): {cvar*100:.2f}%")
        return cvar * 100  # 转换为百分比
    
    def calculate_beta(self, market_returns: Optional[List[float]] = None) -> float:
        """计算 Beta - 市场相关性
        
        衡量投资组合相对于市场的波动性
        Beta = 1: 与市场波动一致
        Beta > 1: 比市场波动更大
        Beta < 1: 比市场波动更小
        
        Args:
            market_returns: 市场收益率序列（如沪深300收益率）
            
        Returns:
            Beta 值
        """
        if market_returns is None or len(market_returns) == 0:
            logger.warning("未提供市场收益率数据，无法计算 Beta")
            return 1.0  # 默认返回 1.0
        
        portfolio_returns = self.calculate_returns()
        
        if len(portfolio_returns) == 0 or len(portfolio_returns) != len(market_returns):
            return 1.0
        
        # 计算协方差和方差
        covariance = np.cov(portfolio_returns, market_returns)[0][1]
        market_variance = np.var(market_returns)
        
        if market_variance == 0:
            return 1.0
        
        beta = covariance / market_variance
        
        logger.debug(f"Beta: {beta:.2f}")
        return beta
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率
        
        衡量每单位风险的超额收益
        
        Args:
            risk_free_rate: 无风险利率（年化），默认 3%
            
        Returns:
            夏普比率
        """
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return 0.0
        
        # 计算年化收益率和年化波动率
        mean_return = returns.mean() * 252  # 假设252个交易日
        std_return = returns.std() * np.sqrt(252)
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        
        logger.debug(f"Sharpe Ratio: {sharpe:.2f}")
        return sharpe
    
    def calculate_max_drawdown(self) -> tuple:
        """计算最大回撤
        
        Returns:
            (最大回撤百分比, 回撤开始时间索引, 回撤结束时间索引)
        """
        if len(self.equity_history) < 2:
            return 0.0, 0, 0
        
        equity_array = np.array(self.equity_history)
        
        # 计算累计最大值
        cummax = np.maximum.accumulate(equity_array)
        
        # 计算回撤
        drawdown = (equity_array - cummax) / cummax
        
        # 找到最大回撤
        max_dd_idx = np.argmin(drawdown)
        max_dd = drawdown[max_dd_idx]
        
        # 找到回撤开始位置（最大回撤点之前的最高点）
        start_idx = np.argmax(equity_array[:max_dd_idx + 1])
        
        logger.debug(
            f"Max Drawdown: {max_dd*100:.2f}% "
            f"(从索引 {start_idx} 到 {max_dd_idx})"
        )
        
        return max_dd * 100, start_idx, max_dd_idx
    
    def calculate_sortino_ratio(self, risk_free_rate: float = 0.03) -> float:
        """计算索提诺比率
        
        类似夏普比率，但只考虑下行风险（负收益的标准差）
        
        Args:
            risk_free_rate: 无风险利率（年化），默认 3%
            
        Returns:
            索提诺比率
        """
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return 0.0
        
        # 计算年化收益率
        mean_return = returns.mean() * 252
        
        # 只计算负收益的标准差（下行风险）
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')  # 没有负收益
        
        downside_std = downside_returns.std() * np.sqrt(252)
        
        if downside_std == 0:
            return 0.0
        
        sortino = (mean_return - risk_free_rate) / downside_std
        
        logger.debug(f"Sortino Ratio: {sortino:.2f}")
        return sortino
    
    def calculate_calmar_ratio(self) -> float:
        """计算卡玛比率
        
        年化收益率 / 最大回撤
        
        Returns:
            卡玛比率
        """
        if len(self.equity_history) < 2:
            return 0.0
        
        returns = self.calculate_returns()
        annual_return = returns.mean() * 252
        
        max_dd, _, _ = self.calculate_max_drawdown()
        max_dd_ratio = abs(max_dd) / 100  # 转换为比例
        
        if max_dd_ratio == 0:
            return 0.0
        
        calmar = annual_return / max_dd_ratio
        
        logger.debug(f"Calmar Ratio: {calmar:.2f}")
        return calmar
    
    def calculate_omega_ratio(self, threshold: float = 0.0) -> float:
        """计算欧米茄比率
        
        大于阈值的收益概率加权 / 小于阈值的损失概率加权
        
        Args:
            threshold: 阈值收益率，默认 0
            
        Returns:
            欧米茄比率
        """
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return 0.0
        
        # 计算超过阈值的收益和低于阈值的损失
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        
        if losses.sum() == 0:
            return float('inf')  # 没有损失
        
        omega = gains.sum() / losses.sum()
        
        logger.debug(f"Omega Ratio: {omega:.2f}")
        return omega
    
    def get_risk_summary(self, confidence_level: float = 0.95,
                         risk_free_rate: float = 0.03) -> dict:
        """获取风险指标摘要
        
        Args:
            confidence_level: 置信水平
            risk_free_rate: 无风险利率
            
        Returns:
            风险指标字典
        """
        max_dd, dd_start, dd_end = self.calculate_max_drawdown()
        
        summary = {
            'var_95': self.calculate_var(confidence_level),
            'cvar_95': self.calculate_cvar(confidence_level),
            'max_drawdown': max_dd,
            'sharpe_ratio': self.calculate_sharpe_ratio(risk_free_rate),
            'sortino_ratio': self.calculate_sortino_ratio(risk_free_rate),
            'calmar_ratio': self.calculate_calmar_ratio(),
            'omega_ratio': self.calculate_omega_ratio(),
            'beta': self.calculate_beta(),
            'drawdown_start_idx': dd_start,
            'drawdown_end_idx': dd_end,
        }
        
        return summary
    
    def assess_risk_level(self) -> str:
        """评估当前风险等级
        
        Returns:
            风险等级: '低', '中', '高', '极高'
        """
        if len(self.equity_history) < 10:
            return '未知'
        
        max_dd, _, _ = self.calculate_max_drawdown()
        volatility = self.calculate_returns().std() * np.sqrt(252) * 100
        
        # 风险等级评估规则
        if abs(max_dd) > 30 or volatility > 40:
            return '极高'
        elif abs(max_dd) > 20 or volatility > 30:
            return '高'
        elif abs(max_dd) > 10 or volatility > 20:
            return '中'
        else:
            return '低'
    
    def get_risk_alerts(self) -> List[dict]:
        """获取风险预警
        
        Returns:
            预警列表
        """
        alerts = []
        
        if len(self.equity_history) < 10:
            return alerts
        
        # 最大回撤预警
        max_dd, _, _ = self.calculate_max_drawdown()
        if abs(max_dd) > 20:
            alerts.append({
                'type': 'MAX_DRAWDOWN',
                'level': 'HIGH' if abs(max_dd) > 30 else 'MEDIUM',
                'message': f'最大回撤达到 {abs(max_dd):.2f}%',
                'value': max_dd,
                'timestamp': datetime.now()
            })
        
        # 波动率预警
        volatility = self.calculate_returns().std() * np.sqrt(252) * 100
        if volatility > 30:
            alerts.append({
                'type': 'VOLATILITY',
                'level': 'HIGH' if volatility > 40 else 'MEDIUM',
                'message': f'年化波动率达到 {volatility:.2f}%',
                'value': volatility,
                'timestamp': datetime.now()
            })
        
        # VaR 预警
        var_95 = self.calculate_var(0.95)
        if var_95 < -5:  # 日 VaR 超过 5%
            alerts.append({
                'type': 'VAR',
                'level': 'MEDIUM',
                'message': f'日 VaR(95%) 为 {var_95:.2f}%',
                'value': var_95,
                'timestamp': datetime.now()
            })
        
        return alerts


class StopLossTracker:
    """止损追踪器
    
    追踪和管理止损止盈触发
    """
    
    def __init__(self, stop_loss_pct: float = 0.05, take_profit_pct: float = 0.15):
        """初始化止损追踪器
        
        Args:
            stop_loss_pct: 止损比例，默认 5%
            take_profit_pct: 止盈比例，默认 15%
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_records = []
        self.take_profit_records = []
    
    def check_position(self, position, current_price: float) -> dict:
        """检查持仓的止损止盈情况
        
        Args:
            position: Position 对象
            current_price: 当前价格
            
        Returns:
            检查结果字典
        """
        if position is None or position.quantity == 0:
            return {
                'stop_loss': False,
                'take_profit': False,
                'action': 'HOLD'
            }
        
        # 计算盈亏比例
        pnl_pct = position.unrealized_pnl_pct
        
        # 止损检查
        if pnl_pct < -self.stop_loss_pct:
            self.stop_loss_records.append({
                'symbol': position.symbol,
                'trigger_price': current_price,
                'avg_price': position.avg_price,
                'loss_pct': pnl_pct,
                'timestamp': datetime.now()
            })
            return {
                'stop_loss': True,
                'take_profit': False,
                'action': 'SELL',
                'reason': f'止损触发：亏损 {abs(pnl_pct):.2f}%'
            }
        
        # 止盈检查
        if pnl_pct > self.take_profit_pct:
            self.take_profit_records.append({
                'symbol': position.symbol,
                'trigger_price': current_price,
                'avg_price': position.avg_price,
                'profit_pct': pnl_pct,
                'timestamp': datetime.now()
            })
            return {
                'stop_loss': False,
                'take_profit': True,
                'action': 'SELL',
                'reason': f'止盈触发：盈利 {pnl_pct:.2f}%'
            }
        
        return {
            'stop_loss': False,
            'take_profit': False,
            'action': 'HOLD'
        }
    
    def get_stop_loss_stats(self) -> dict:
        """获取止损统计
        
        Returns:
            止损统计字典
        """
        if not self.stop_loss_records:
            return {
                'count': 0,
                'avg_loss_pct': 0.0,
                'total_loss_pct': 0.0
            }
        
        losses = [r['loss_pct'] for r in self.stop_loss_records]
        
        return {
            'count': len(self.stop_loss_records),
            'avg_loss_pct': np.mean(losses),
            'total_loss_pct': np.sum(losses),
            'max_loss_pct': np.min(losses),  # 最大亏损（最小值）
            'records': self.stop_loss_records
        }
    
    def get_take_profit_stats(self) -> dict:
        """获取止盈统计
        
        Returns:
            止盈统计字典
        """
        if not self.take_profit_records:
            return {
                'count': 0,
                'avg_profit_pct': 0.0,
                'total_profit_pct': 0.0
            }
        
        profits = [r['profit_pct'] for r in self.take_profit_records]
        
        return {
            'count': len(self.take_profit_records),
            'avg_profit_pct': np.mean(profits),
            'total_profit_pct': np.sum(profits),
            'max_profit_pct': np.max(profits),  # 最大盈利
            'records': self.take_profit_records
        }


class TrailingStopLoss:
    """移动止损
    
    随着价格上涨，动态提升止损位
    """
    
    def __init__(self, trailing_pct: float = 0.05):
        """初始化移动止损
        
        Args:
            trailing_pct: 移动止损比例，默认 5%
        """
        self.trailing_pct = trailing_pct
        self.peak_prices: dict = {}  # {symbol: peak_price}
    
    def update_peak(self, symbol: str, current_price: float):
        """更新峰值价格
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
        """
        if symbol not in self.peak_prices:
            self.peak_prices[symbol] = current_price
        else:
            self.peak_prices[symbol] = max(self.peak_prices[symbol], current_price)
    
    def should_stop(self, symbol: str, current_price: float) -> bool:
        """判断是否应该移动止损
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            
        Returns:
            是否触发移动止损
        """
        if symbol not in self.peak_prices:
            return False
        
        peak_price = self.peak_prices[symbol]
        drop_pct = (current_price - peak_price) / peak_price
        
        if drop_pct < -self.trailing_pct:
            logger.info(
                f"移动止损触发: {symbol} "
                f"从峰值 {peak_price:.2f} 回落 {abs(drop_pct)*100:.2f}%"
            )
            return True
        
        return False
    
    def reset(self, symbol: str):
        """重置峰值价格
        
        Args:
            symbol: 股票代码
        """
        if symbol in self.peak_prices:
            del self.peak_prices[symbol]


class TimedStopLoss:
    """时间止损
    
    持仓超过指定天数自动平仓
    """
    
    def __init__(self, max_hold_days: int = 30):
        """初始化时间止损
        
        Args:
            max_hold_days: 最大持仓天数，默认 30 天
        """
        self.max_hold_days = max_hold_days
        self.entry_dates: dict = {}  # {symbol: entry_date}
    
    def record_entry(self, symbol: str, entry_date: datetime):
        """记录开仓日期
        
        Args:
            symbol: 股票代码
            entry_date: 开仓日期
        """
        self.entry_dates[symbol] = entry_date
    
    def should_stop(self, symbol: str, current_date: datetime) -> bool:
        """判断是否应该时间止损
        
        Args:
            symbol: 股票代码
            current_date: 当前日期
            
        Returns:
            是否触发时间止损
        """
        if symbol not in self.entry_dates:
            return False
        
        entry_date = self.entry_dates[symbol]
        hold_days = (current_date - entry_date).days
        
        if hold_days >= self.max_hold_days:
            logger.info(
                f"时间止损触发: {symbol} "
                f"持仓 {hold_days} 天超过限制 {self.max_hold_days} 天"
            )
            return True
        
        return False
    
    def clear_entry(self, symbol: str):
        """清除开仓记录
        
        Args:
            symbol: 股票代码
        """
        if symbol in self.entry_dates:
            del self.entry_dates[symbol]
