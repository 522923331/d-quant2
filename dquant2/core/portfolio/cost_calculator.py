"""成本计算模块

提供多种成本计算方法：FIFO, LIFO, 加权平均
参考: QuantOL 投资组合架构
"""

from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CostRecord:
    """成本记录
    
    用于 FIFO/LIFO 成本计算
    """
    
    def __init__(self, quantity: float, price: float, timestamp: datetime):
        """初始化成本记录
        
        Args:
            quantity: 数量
            price: 价格
            timestamp: 时间戳
        """
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp
        self.remaining_quantity = quantity
    
    def __repr__(self):
        return f"CostRecord({self.remaining_quantity}/{self.quantity}@{self.price:.2f})"


class FIFOCostCalculator:
    """FIFO（先进先出）成本计算器
    
    按照买入顺序计算成本
    """
    
    def __init__(self):
        """初始化 FIFO 计算器"""
        self.cost_records: Dict[str, List[CostRecord]] = {}
    
    def add_buy(self, symbol: str, quantity: float, price: float, 
                timestamp: datetime):
        """添加买入记录
        
        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            timestamp: 时间戳
        """
        if symbol not in self.cost_records:
            self.cost_records[symbol] = []
        
        record = CostRecord(quantity, price, timestamp)
        self.cost_records[symbol].append(record)
        
        logger.debug(f"FIFO 买入记录: {symbol} {quantity}@{price:.2f}")
    
    def calculate_sell_cost(self, symbol: str, quantity: float) -> tuple:
        """计算卖出成本（FIFO）
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            
        Returns:
            (平均成本, 已实现盈亏明细)
        """
        if symbol not in self.cost_records:
            logger.warning(f"FIFO: 没有找到 {symbol} 的成本记录")
            return 0.0, []
        
        records = self.cost_records[symbol]
        remaining_qty = quantity
        total_cost = 0.0
        realized_details = []
        
        # FIFO: 从最早的记录开始卖出
        for record in records:
            if remaining_qty <= 0:
                break
            
            if record.remaining_quantity > 0:
                # 计算本次卖出数量
                sell_qty = min(remaining_qty, record.remaining_quantity)
                
                # 累计成本
                total_cost += sell_qty * record.price
                
                # 记录明细
                realized_details.append({
                    'quantity': sell_qty,
                    'cost': record.price,
                    'timestamp': record.timestamp
                })
                
                # 更新剩余数量
                record.remaining_quantity -= sell_qty
                remaining_qty -= sell_qty
        
        if remaining_qty > 0:
            logger.error(f"FIFO: 卖出数量 {quantity} 超过持仓")
            return 0.0, []
        
        avg_cost = total_cost / quantity if quantity > 0 else 0.0
        
        logger.debug(f"FIFO 卖出成本: {symbol} {quantity}@avg {avg_cost:.2f}")
        
        # 清理空记录
        self.cost_records[symbol] = [r for r in records if r.remaining_quantity > 0]
        
        return avg_cost, realized_details
    
    def get_avg_cost(self, symbol: str) -> float:
        """获取平均成本
        
        Args:
            symbol: 股票代码
            
        Returns:
            加权平均成本
        """
        if symbol not in self.cost_records:
            return 0.0
        
        records = self.cost_records[symbol]
        total_qty = sum(r.remaining_quantity for r in records)
        
        if total_qty == 0:
            return 0.0
        
        total_cost = sum(r.remaining_quantity * r.price for r in records)
        return total_cost / total_qty
    
    def get_total_quantity(self, symbol: str) -> float:
        """获取总持仓数量
        
        Args:
            symbol: 股票代码
            
        Returns:
            总数量
        """
        if symbol not in self.cost_records:
            return 0.0
        
        return sum(r.remaining_quantity for r in self.cost_records[symbol])
    
    def clear(self, symbol: str):
        """清除成本记录
        
        Args:
            symbol: 股票代码
        """
        if symbol in self.cost_records:
            del self.cost_records[symbol]


class LIFOCostCalculator:
    """LIFO（后进先出）成本计算器
    
    按照买入顺序倒序计算成本
    """
    
    def __init__(self):
        """初始化 LIFO 计算器"""
        self.cost_records: Dict[str, List[CostRecord]] = {}
    
    def add_buy(self, symbol: str, quantity: float, price: float, 
                timestamp: datetime):
        """添加买入记录"""
        if symbol not in self.cost_records:
            self.cost_records[symbol] = []
        
        record = CostRecord(quantity, price, timestamp)
        self.cost_records[symbol].append(record)
        
        logger.debug(f"LIFO 买入记录: {symbol} {quantity}@{price:.2f}")
    
    def calculate_sell_cost(self, symbol: str, quantity: float) -> tuple:
        """计算卖出成本（LIFO）
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            
        Returns:
            (平均成本, 已实现盈亏明细)
        """
        if symbol not in self.cost_records:
            logger.warning(f"LIFO: 没有找到 {symbol} 的成本记录")
            return 0.0, []
        
        records = self.cost_records[symbol]
        remaining_qty = quantity
        total_cost = 0.0
        realized_details = []
        
        # LIFO: 从最新的记录开始卖出
        for record in reversed(records):
            if remaining_qty <= 0:
                break
            
            if record.remaining_quantity > 0:
                # 计算本次卖出数量
                sell_qty = min(remaining_qty, record.remaining_quantity)
                
                # 累计成本
                total_cost += sell_qty * record.price
                
                # 记录明细
                realized_details.append({
                    'quantity': sell_qty,
                    'cost': record.price,
                    'timestamp': record.timestamp
                })
                
                # 更新剩余数量
                record.remaining_quantity -= sell_qty
                remaining_qty -= sell_qty
        
        if remaining_qty > 0:
            logger.error(f"LIFO: 卖出数量 {quantity} 超过持仓")
            return 0.0, []
        
        avg_cost = total_cost / quantity if quantity > 0 else 0.0
        
        logger.debug(f"LIFO 卖出成本: {symbol} {quantity}@avg {avg_cost:.2f}")
        
        # 清理空记录
        self.cost_records[symbol] = [r for r in records if r.remaining_quantity > 0]
        
        return avg_cost, realized_details
    
    def get_avg_cost(self, symbol: str) -> float:
        """获取平均成本"""
        if symbol not in self.cost_records:
            return 0.0
        
        records = self.cost_records[symbol]
        total_qty = sum(r.remaining_quantity for r in records)
        
        if total_qty == 0:
            return 0.0
        
        total_cost = sum(r.remaining_quantity * r.price for r in records)
        return total_cost / total_qty
    
    def get_total_quantity(self, symbol: str) -> float:
        """获取总持仓数量"""
        if symbol not in self.cost_records:
            return 0.0
        
        return sum(r.remaining_quantity for r in self.cost_records[symbol])
    
    def clear(self, symbol: str):
        """清除成本记录"""
        if symbol in self.cost_records:
            del self.cost_records[symbol]


class WeightedAverageCostCalculator:
    """加权平均成本计算器
    
    简单的加权平均成本计算
    """
    
    def __init__(self):
        """初始化加权平均计算器"""
        self.positions: Dict[str, Dict] = {}  # {symbol: {'quantity': x, 'avg_cost': y}}
    
    def add_buy(self, symbol: str, quantity: float, price: float, 
                timestamp: datetime):
        """添加买入记录
        
        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            timestamp: 时间戳
        """
        if symbol not in self.positions:
            self.positions[symbol] = {
                'quantity': quantity,
                'avg_cost': price
            }
        else:
            pos = self.positions[symbol]
            total_cost = pos['quantity'] * pos['avg_cost'] + quantity * price
            new_quantity = pos['quantity'] + quantity
            self.positions[symbol] = {
                'quantity': new_quantity,
                'avg_cost': total_cost / new_quantity
            }
        
        logger.debug(
            f"加权平均买入: {symbol} {quantity}@{price:.2f}, "
            f"新平均成本: {self.positions[symbol]['avg_cost']:.2f}"
        )
    
    def calculate_sell_cost(self, symbol: str, quantity: float) -> tuple:
        """计算卖出成本（加权平均）
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            
        Returns:
            (平均成本, 已实现盈亏明细)
        """
        if symbol not in self.positions:
            logger.warning(f"加权平均: 没有找到 {symbol} 的持仓")
            return 0.0, []
        
        pos = self.positions[symbol]
        
        if quantity > pos['quantity']:
            logger.error(f"加权平均: 卖出数量 {quantity} 超过持仓 {pos['quantity']}")
            return 0.0, []
        
        avg_cost = pos['avg_cost']
        
        # 更新剩余数量
        pos['quantity'] -= quantity
        
        if pos['quantity'] == 0:
            del self.positions[symbol]
        
        realized_details = [{
            'quantity': quantity,
            'cost': avg_cost,
            'timestamp': datetime.now()
        }]
        
        logger.debug(f"加权平均卖出: {symbol} {quantity}@{avg_cost:.2f}")
        
        return avg_cost, realized_details
    
    def get_avg_cost(self, symbol: str) -> float:
        """获取平均成本"""
        if symbol not in self.positions:
            return 0.0
        return self.positions[symbol]['avg_cost']
    
    def get_total_quantity(self, symbol: str) -> float:
        """获取总持仓数量"""
        if symbol not in self.positions:
            return 0.0
        return self.positions[symbol]['quantity']
    
    def clear(self, symbol: str):
        """清除成本记录"""
        if symbol in self.positions:
            del self.positions[symbol]
