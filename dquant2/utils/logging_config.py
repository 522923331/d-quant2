"""日志配置模块

提供统一的日志配置，支持控制台和文件输出
"""

import logging
import os
from datetime import datetime
from typing import Optional


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_filename: Optional[str] = None
) -> logging.Logger:
    """配置日志
    
    Args:
        log_dir: 日志目录，默认为当前目录下的 logs 文件夹
        log_level: 日志级别，默认 INFO
        log_to_file: 是否输出到文件，默认 True
        log_to_console: 是否输出到控制台，默认 True
        log_filename: 日志文件名，默认按日期自动生成
        
    Returns:
        配置好的 logger 对象
    """
    # 获取根 logger
    logger = logging.getLogger('dquant2')
    logger.setLevel(log_level)
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 详细格式（用于文件）
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if log_to_file:
        # 确定日志目录
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), 'logs')
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 确定日志文件名
        if log_filename is None:
            log_filename = f"dquant2_{datetime.now().strftime('%Y%m%d')}.log"
        
        log_path = os.path.join(log_dir, log_filename)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"日志文件已创建: {log_path}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger
    
    Args:
        name: logger 名称，通常使用 __name__
        
    Returns:
        logger 对象
    """
    return logging.getLogger(f'dquant2.{name}')


class BacktestLogger:
    """回测专用日志器
    
    提供结构化的回测日志记录
    """
    
    def __init__(self, backtest_id: str, log_dir: Optional[str] = None):
        """初始化回测日志器
        
        Args:
            backtest_id: 回测ID
            log_dir: 日志目录
        """
        self.backtest_id = backtest_id
        self.log_dir = log_dir or os.path.join(os.getcwd(), 'logs', 'backtests')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建专用 logger
        self.logger = logging.getLogger(f'dquant2.backtest.{backtest_id}')
        self.logger.setLevel(logging.DEBUG)
        
        # 添加文件处理器
        log_path = os.path.join(self.log_dir, f'{backtest_id}.log')
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(handler)
        
        self.log_path = log_path
    
    def log_config(self, config: dict):
        """记录回测配置"""
        self.logger.info("=" * 60)
        self.logger.info("回测配置")
        self.logger.info("=" * 60)
        for key, value in config.items():
            self.logger.info(f"  {key}: {value}")
    
    def log_trade(self, trade: dict):
        """记录交易"""
        direction = trade.get('direction', 'UNKNOWN')
        symbol = trade.get('symbol', 'UNKNOWN')
        price = trade.get('price', 0)
        quantity = trade.get('quantity', 0)
        self.logger.info(f"交易 | {direction} | {symbol} | {quantity}@{price:.2f}")
    
    def log_signal(self, signal_type: str, symbol: str, reason: str):
        """记录信号"""
        self.logger.info(f"信号 | {signal_type} | {symbol} | {reason}")
    
    def log_daily_summary(self, date: str, equity: float, cash: float, positions_value: float):
        """记录每日摘要"""
        self.logger.debug(f"日结 | {date} | 权益:{equity:.2f} | 现金:{cash:.2f} | 持仓:{positions_value:.2f}")
    
    def log_performance(self, performance: dict):
        """记录绩效指标"""
        self.logger.info("=" * 60)
        self.logger.info("绩效指标")
        self.logger.info("=" * 60)
        for key, value in performance.items():
            if isinstance(value, float):
                self.logger.info(f"  {key}: {value:.4f}")
            else:
                self.logger.info(f"  {key}: {value}")
    
    def log_error(self, message: str, exc_info=False):
        """记录错误"""
        self.logger.error(message, exc_info=exc_info)
    
    def get_log_path(self) -> str:
        """获取日志文件路径"""
        return self.log_path
