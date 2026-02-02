"""日志配置模块

提供统一的日志配置，支持控制台和文件输出
增强功能：支持环境变量配置、运行时日志级别调整、日志轮转
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional


# 从环境变量获取日志级别，默认INFO
DEFAULT_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（用于控制台）"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS and sys.stdout.isatty():
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


class LoggerManager:
    """日志管理器 - 单例模式，支持运行时配置"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.current_level = LOG_LEVELS.get(DEFAULT_LOG_LEVEL, logging.INFO)
            self._initialized = True
    
    def set_level(self, level: str):
        """运行时设置日志级别
        
        Args:
            level: 日志级别字符串 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        new_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        self.current_level = new_level
        
        # 更新所有处理器的级别
        logger = logging.getLogger('dquant2')
        logger.setLevel(new_level)
        for handler in logger.handlers:
            handler.setLevel(new_level)
        
        logger.info(f"日志级别已更新为: {level.upper()}")
    
    def get_level(self) -> str:
        """获取当前日志级别"""
        for name, level in LOG_LEVELS.items():
            if level == self.current_level:
                return name
        return 'INFO'


# 全局日志管理器实例
logger_manager = LoggerManager()


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,  # 改为字符串，支持环境变量
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_filename: Optional[str] = None,
    enable_color: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """配置日志
    
    Args:
        log_dir: 日志目录，默认为当前目录下的 logs 文件夹
        log_level: 日志级别字符串 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   如果为None，则从环境变量 LOG_LEVEL 读取，默认INFO
        log_to_file: 是否输出到文件，默认 True
        log_to_console: 是否输出到控制台，默认 True
        log_filename: 日志文件名，默认按日期自动生成
        enable_color: 是否启用控制台颜色，默认 True
        max_bytes: 日志文件最大大小（字节），超过后自动轮转
        backup_count: 保留的备份文件数量
        
    Returns:
        配置好的 logger 对象
    """
    # 解析日志级别
    if log_level is None:
        log_level = DEFAULT_LOG_LEVEL
    numeric_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    logger_manager.current_level = numeric_level
    
    # 获取根 logger
    logger = logging.getLogger('dquant2')
    logger.setLevel(numeric_level)
    
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
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        
        # 使用带颜色的格式化器
        if enable_color:
            console_handler.setFormatter(ColoredFormatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        else:
            console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    # 文件处理器（带日志轮转）
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
        
        # 使用 RotatingFileHandler 实现日志轮转
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"日志文件已创建: {log_path} (级别: {log_level})")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger
    
    Args:
        name: logger 名称，通常使用 __name__
        
    Returns:
        logger 对象
    """
    return logging.getLogger(f'dquant2.{name}')


def set_log_level(level: str):
    """动态设置日志级别
    
    Args:
        level: 日志级别字符串 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Example:
        set_log_level('DEBUG')  # 切换到调试模式
        set_log_level('INFO')   # 切换到正常模式
    """
    logger_manager.set_level(level)


def get_log_level() -> str:
    """获取当前日志级别
    
    Returns:
        当前日志级别字符串
    """
    return logger_manager.get_level()


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
