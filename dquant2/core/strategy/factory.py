"""策略工厂

使用工厂模式管理策略注册和创建
"""

from typing import Any, Dict, Type
import logging

from dquant2.core.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyFactory:
    """策略工厂
    
    职责：
    1. 策略注册
    2. 策略创建
    3. 策略管理
    
    使用方法：
        @StrategyFactory.register("my_strategy")
        class MyStrategy(BaseStrategy):
            pass
    """
    
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, name: str):
        """注册策略（装饰器）
        
        Args:
            name: 策略名称
            
        Returns:
            装饰器函数
        """
        def decorator(strategy_class: Type[BaseStrategy]):
            if name in cls._strategies:
                logger.warning(f"策略 '{name}' 已存在，将被覆盖")
            cls._strategies[name] = strategy_class
            logger.info(f"策略 '{name}' 已注册: {strategy_class.__name__}")
            return strategy_class
        return decorator
    
    @classmethod
    def create(cls, name: str, **kwargs) -> BaseStrategy:
        """创建策略实例
        
        Args:
            name: 策略名称
            **kwargs: 策略参数
            
        Returns:
            策略实例
            
        Raises:
            ValueError: 策略不存在
        """
        if name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(
                f"未知策略: '{name}'. 可用策略: {available or '无'}"
            )
        
        strategy_class = cls._strategies[name]
        return strategy_class(**kwargs)
    
    @classmethod
    def list_strategies(cls) -> list:
        """列出所有已注册的策略"""
        return list(cls._strategies.keys())
    
    @classmethod
    def has_strategy(cls, name: str) -> bool:
        """检查策略是否存在"""
        return name in cls._strategies
    
    @classmethod
    def unregister(cls, name: str):
        """取消注册策略"""
        if name in cls._strategies:
            del cls._strategies[name]
            logger.info(f"策略 '{name}' 已取消注册")
    
    @classmethod
    def clear(cls):
        """清除所有注册的策略"""
        cls._strategies.clear()
        logger.info("所有策略已清除")
