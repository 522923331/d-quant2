"""回测历史记录管理器

使用SQLite数据库存储和查询回测历史
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

import pandas as pd

logger = logging.getLogger(__name__)


class BacktestHistoryManager:
    """回测历史记录管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化
        
        Args:
            db_path: 数据库文件路径，默认为项目数据目录
        """
        if db_path is None:
            # 使用默认路径
            from dquant2.config import DB_DIR
            db_path = str(Path(DB_DIR) / 'backtest_history.db')
        
        self.db_path = db_path
        self._init_database()
        
        logger.info(f"回测历史记录管理器初始化，数据库: {db_path}")
    
    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建回测历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_cash REAL NOT NULL,
                    config_json TEXT NOT NULL,
                    
                    -- 性能指标
                    total_return REAL,
                    total_return_pct REAL,
                    annual_return REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    sortino_ratio REAL,
                    volatility REAL,
                    win_rate REAL,
                    num_trades INTEGER,
                    
                    -- 完整结果（JSON）
                    results_json TEXT,
                    
                    -- 元数据
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    tags TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_symbol 
                ON backtest_history(symbol)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_strategy 
                ON backtest_history(strategy_name)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON backtest_history(created_at DESC)
            ''')
            
            conn.commit()
    
    def save_backtest(
        self,
        results: Dict,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """保存回测记录
        
        Args:
            results: 回测结果字典
            notes: 备注
            tags: 标签列表
            
        Returns:
            记录ID
        """
        config = results.get('config', {})
        portfolio = results.get('portfolio', {})
        performance = results.get('performance', {})
        
        # 提取关键信息
        symbol = config.get('symbol', 'N/A')
        strategy_name = config.get('strategy_name', 'N/A')
        start_date = config.get('start_date', 'N/A')
        end_date = config.get('end_date', 'N/A')
        initial_cash = config.get('initial_cash', 0)
        
        # 序列化
        config_json = json.dumps(config, ensure_ascii=False)
        results_json = json.dumps(results, ensure_ascii=False, default=str)
        tags_str = ','.join(tags) if tags else None
        
        # 插入数据库
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO backtest_history (
                    symbol, strategy_name, start_date, end_date, initial_cash,
                    config_json,
                    total_return, total_return_pct, annual_return, max_drawdown,
                    sharpe_ratio, sortino_ratio, volatility, win_rate, num_trades,
                    results_json,
                    created_at, notes, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, strategy_name, start_date, end_date, initial_cash,
                config_json,
                portfolio.get('total_return'),
                portfolio.get('total_return_pct'),
                performance.get('annual_return'),
                performance.get('max_drawdown'),
                performance.get('sharpe_ratio'),
                performance.get('sortino_ratio'),
                performance.get('volatility'),
                performance.get('win_rate'),
                portfolio.get('num_trades'),
                results_json,
                datetime.now().isoformat(),
                notes,
                tags_str
            ))
            
            conn.commit()
            record_id = cursor.lastrowid
        
        logger.info(f"回测记录已保存 - ID: {record_id}, 股票: {symbol}, 策略: {strategy_name}")
        return record_id
    
    def get_backtest(self, backtest_id: int) -> Optional[Dict]:
        """获取指定回测记录
        
        Args:
            backtest_id: 回测ID
            
        Returns:
            回测记录字典
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM backtest_history WHERE id = ?
            ''', (backtest_id,))
            
            row = cursor.fetchone()
            
            if row:
                return self._row_to_dict(row)
            return None
    
    def list_backtests(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """列出回测记录
        
        Args:
            symbol: 股票代码过滤
            strategy_name: 策略名称过滤
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            回测记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 构建查询
            query = 'SELECT * FROM backtest_history WHERE 1=1'
            params = []
            
            if symbol:
                query += ' AND symbol = ?'
                params.append(symbol)
            
            if strategy_name:
                query += ' AND strategy_name = ?'
                params.append(strategy_name)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def search_backtests(
        self,
        min_return: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        min_sharpe: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict]:
        """搜索回测记录
        
        Args:
            min_return: 最小收益率
            max_drawdown: 最大回撤限制
            min_sharpe: 最小夏普比率
            tags: 标签过滤
            limit: 返回数量限制
            
        Returns:
            回测记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 构建查询
            query = 'SELECT * FROM backtest_history WHERE 1=1'
            params = []
            
            if min_return is not None:
                query += ' AND total_return_pct >= ?'
                params.append(min_return)
            
            if max_drawdown is not None:
                query += ' AND max_drawdown <= ?'
                params.append(max_drawdown)
            
            if min_sharpe is not None:
                query += ' AND sharpe_ratio >= ?'
                params.append(min_sharpe)
            
            if tags:
                # 标签搜索（简单实现，支持单个标签）
                tag_conditions = ' OR '.join(['tags LIKE ?' for _ in tags])
                query += f' AND ({tag_conditions})'
                params.extend([f'%{tag}%' for tag in tags])
            
            query += ' ORDER BY total_return_pct DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def compare_backtests(self, backtest_ids: List[int]) -> pd.DataFrame:
        """对比多个回测结果
        
        Args:
            backtest_ids: 回测ID列表
            
        Returns:
            对比结果DataFrame
        """
        import pandas as pd
        
        records = []
        for backtest_id in backtest_ids:
            record = self.get_backtest(backtest_id)
            if record:
                records.append({
                    'ID': record['id'],
                    '股票': record['symbol'],
                    '策略': record['strategy_name'],
                    '开始日期': record['start_date'],
                    '结束日期': record['end_date'],
                    '总收益率(%)': record['total_return_pct'],
                    '年化收益率(%)': record['annual_return'],
                    '最大回撤(%)': record['max_drawdown'],
                    '夏普比率': record['sharpe_ratio'],
                    '交易次数': record['num_trades'],
                    '创建时间': record['created_at']
                })
        
        return pd.DataFrame(records)
    
    def delete_backtest(self, backtest_id: int) -> bool:
        """删除回测记录
        
        Args:
            backtest_id: 回测ID
            
        Returns:
            是否删除成功
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM backtest_history WHERE id = ?
            ''', (backtest_id,))
            
            conn.commit()
            deleted = cursor.rowcount > 0
        
        if deleted:
            logger.info(f"回测记录已删除 - ID: {backtest_id}")
        
        return deleted
    
    def update_notes(self, backtest_id: int, notes: str) -> bool:
        """更新备注
        
        Args:
            backtest_id: 回测ID
            notes: 新的备注
            
        Returns:
            是否更新成功
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE backtest_history SET notes = ? WHERE id = ?
            ''', (notes, backtest_id))
            
            conn.commit()
            updated = cursor.rowcount > 0
        
        return updated
    
    def add_tags(self, backtest_id: int, tags: List[str]) -> bool:
        """添加标签
        
        Args:
            backtest_id: 回测ID
            tags: 标签列表
            
        Returns:
            是否添加成功
        """
        # 获取现有标签
        record = self.get_backtest(backtest_id)
        if not record:
            return False
        
        # record['tags'] 已经是列表了（在_row_to_dict中处理）
        existing_tags = record.get('tags', [])
        if isinstance(existing_tags, str):
            existing_tags = [t.strip() for t in existing_tags.split(',') if t.strip()]
        
        # 合并标签
        all_tags = list(set(existing_tags + tags))
        tags_str = ','.join(all_tags)
        
        # 更新数据库
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE backtest_history SET tags = ? WHERE id = ?
            ''', (tags_str, backtest_id))
            
            conn.commit()
            updated = cursor.rowcount > 0
        
        return updated
    
    def get_statistics(self) -> Dict:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 总记录数
            cursor.execute('SELECT COUNT(*) FROM backtest_history')
            total_count = cursor.fetchone()[0]
            
            # 策略统计
            cursor.execute('''
                SELECT strategy_name, COUNT(*) as count
                FROM backtest_history
                GROUP BY strategy_name
                ORDER BY count DESC
            ''')
            strategy_stats = dict(cursor.fetchall())
            
            # 股票统计
            cursor.execute('''
                SELECT symbol, COUNT(*) as count
                FROM backtest_history
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 10
            ''')
            symbol_stats = dict(cursor.fetchall())
            
            # 平均性能
            cursor.execute('''
                SELECT 
                    AVG(total_return_pct) as avg_return,
                    AVG(sharpe_ratio) as avg_sharpe,
                    AVG(max_drawdown) as avg_drawdown
                FROM backtest_history
            ''')
            row = cursor.fetchone()
            avg_performance = {
                'avg_return': row[0] or 0,
                'avg_sharpe': row[1] or 0,
                'avg_drawdown': row[2] or 0
            }
        
        return {
            'total_count': total_count,
            'strategy_stats': strategy_stats,
            'symbol_stats': symbol_stats,
            'avg_performance': avg_performance
        }
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """将数据库行转换为字典"""
        record = dict(row)
        
        # 解析JSON字段
        if record.get('config_json'):
            record['config'] = json.loads(record['config_json'])
        
        if record.get('results_json'):
            record['results'] = json.loads(record['results_json'])
        
        # 解析标签
        if record.get('tags'):
            record['tags'] = [t.strip() for t in record['tags'].split(',') if t.strip()]
        else:
            record['tags'] = []
        
        return record


# 便捷函数
def save_backtest_to_history(results: Dict, notes: Optional[str] = None, tags: Optional[List[str]] = None) -> int:
    """保存回测到历史记录（便捷函数）
    
    Args:
        results: 回测结果字典
        notes: 备注
        tags: 标签列表
        
    Returns:
        记录ID
    """
    manager = BacktestHistoryManager()
    return manager.save_backtest(results, notes, tags)
