"""自定义异常类

统一的异常处理体系
"""


class DQuant2Error(Exception):
    """所有d-quant2异常的基类"""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'details': self.details
        }


# ==================== 数据相关异常 ====================

class DataError(DQuant2Error):
    """数据相关错误的基类"""
    pass


class DataNotFoundError(DataError):
    """数据未找到"""
    pass


class DataFormatError(DataError):
    """数据格式错误"""
    pass


class DataQualityError(DataError):
    """数据质量问题"""
    pass


class DataSourceError(DataError):
    """数据源错误"""
    pass


class DataDownloadError(DataError):
    """数据下载失败"""
    pass


# ==================== 策略相关异常 ====================

class StrategyError(DQuant2Error):
    """策略相关错误的基类"""
    pass


class StrategyNotFoundError(StrategyError):
    """策略未找到"""
    pass


class StrategyConfigError(StrategyError):
    """策略配置错误"""
    pass


class StrategyExecutionError(StrategyError):
    """策略执行错误"""
    pass


# ==================== 回测相关异常 ====================

class BacktestError(DQuant2Error):
    """回测相关错误的基类"""
    pass


class BacktestConfigError(BacktestError):
    """回测配置错误"""
    pass


class BacktestExecutionError(BacktestError):
    """回测执行错误"""
    pass


class InsufficientDataError(BacktestError):
    """数据不足以进行回测"""
    pass


# ==================== 交易相关异常 ====================

class TradingError(DQuant2Error):
    """交易相关错误的基类"""
    pass


class InsufficientFundsError(TradingError):
    """资金不足"""
    pass


class InsufficientPositionError(TradingError):
    """持仓不足"""
    pass


class OrderValidationError(TradingError):
    """订单验证失败"""
    pass


class OrderExecutionError(TradingError):
    """订单执行失败"""
    pass


# ==================== 风控相关异常 ====================

class RiskControlError(DQuant2Error):
    """风控相关错误的基类"""
    pass


class MaxPositionExceededError(RiskControlError):
    """超过最大持仓限制"""
    pass


class MaxDrawdownExceededError(RiskControlError):
    """超过最大回撤限制"""
    pass


class RiskLimitExceededError(RiskControlError):
    """超过风险限制"""
    pass


# ==================== 配置相关异常 ====================

class ConfigError(DQuant2Error):
    """配置相关错误的基类"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    pass


class MissingConfigError(ConfigError):
    """缺少必需的配置"""
    pass


# ==================== 系统相关异常 ====================

class SystemError(DQuant2Error):
    """系统相关错误的基类"""
    pass


class DatabaseError(SystemError):
    """数据库错误"""
    pass


class CacheError(SystemError):
    """缓存错误"""
    pass


class FileSystemError(SystemError):
    """文件系统错误"""
    pass


# ==================== 异常处理器 ====================

class ExceptionHandler:
    """统一的异常处理器"""
    
    @staticmethod
    def handle(error: Exception, context: str = "", logger=None):
        """统一处理异常
        
        Args:
            error: 异常对象
            context: 上下文信息
            logger: 日志记录器
            
        Returns:
            错误信息字典
        """
        # 判断异常类型
        if isinstance(error, DQuant2Error):
            error_info = error.to_dict()
            error_info['context'] = context
            
            if logger:
                logger.error(
                    f"{context} - {error.__class__.__name__}: {error.message}",
                    extra={'details': error.details}
                )
        else:
            # 未知异常
            error_info = {
                'error_type': error.__class__.__name__,
                'message': str(error),
                'context': context,
                'details': {}
            }
            
            if logger:
                logger.exception(f"{context} - 未知错误: {error}")
        
        return error_info
    
    @staticmethod
    def safe_execute(func, *args, default=None, context="", logger=None, **kwargs):
        """安全执行函数，捕获并处理异常
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            default: 发生异常时的默认返回值
            context: 上下文信息
            logger: 日志记录器
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果或默认值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ExceptionHandler.handle(e, context, logger)
            return default


# ==================== 装饰器 ====================

def handle_exceptions(context: str = "", default=None, logger=None):
    """异常处理装饰器
    
    Args:
        context: 上下文信息
        default: 发生异常时的默认返回值
        logger: 日志记录器
    
    Example:
        @handle_exceptions(context="加载数据", default=pd.DataFrame())
        def load_data(symbol):
            return download_data(symbol)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ExceptionHandler.handle(e, context or func.__name__, logger)
                return default
        return wrapper
    return decorator


def validate_config(required_keys: list):
    """配置验证装饰器
    
    Args:
        required_keys: 必需的配置键列表
    
    Example:
        @validate_config(['symbol', 'start_date', 'end_date'])
        def run_backtest(config):
            pass
    """
    def decorator(func):
        def wrapper(config, *args, **kwargs):
            # 检查必需的键
            missing_keys = [key for key in required_keys if key not in config]
            if missing_keys:
                raise MissingConfigError(
                    f"缺少必需的配置项",
                    details={'missing_keys': missing_keys}
                )
            return func(config, *args, **kwargs)
        return wrapper
    return decorator
