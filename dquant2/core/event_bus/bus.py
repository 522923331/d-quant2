"""事件总线实现

EventBus 是事件驱动架构的核心，负责事件的发布和订阅。
采用观察者模式，实现模块间的解耦。
"""

from collections import defaultdict
from typing import Callable, Dict, List, Any
import logging

from dquant2.core.event_bus.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """事件总线
    
    特点：
    1. 支持多订阅者
    2. 类型安全的事件处理
    3. 异常隔离（一个处理器失败不影响其他处理器）
    4. 完整的日志记录
    """
    
    def __init__(self, enable_logging: bool = True):
        """初始化事件总线
        
        Args:
            enable_logging: 是否启用事件日志
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_history: List[BaseEvent] = []
        self._enable_logging = enable_logging
        self._stats = defaultdict(int)  # 统计信息
    
    def subscribe(self, event_type: str, handler: Callable[[BaseEvent], Any]):
        """订阅事件
        
        Args:
            event_type: 事件类型名称（如 'market_data', 'signal'）
            handler: 事件处理器函数，接收 BaseEvent 对象
        """
        self._subscribers[event_type].append(handler)
        logger.info(f"已订阅事件 '{event_type}': {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: Callable[[BaseEvent], Any]):
        """取消订阅事件
        
        Args:
            event_type: 事件类型名称
            handler: 要移除的处理器
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.info(f"已取消订阅事件 '{event_type}': {handler.__name__}")
            except ValueError:
                logger.warning(f"处理器不存在，无法取消订阅: {handler.__name__}")
    
    def publish(self, event_type: str, event: BaseEvent):
        """发布事件
        
        Args:
            event_type: 事件类型名称
            event: 事件对象
        """
        # 记录事件历史
        if self._enable_logging:
            self._event_history.append(event)
        
        # 更新统计
        self._stats[f"published_{event_type}"] += 1
        
        # 日志
        logger.debug(f"发布事件 '{event_type}': {event.event_id}")
        
        # 通知所有订阅者
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            logger.warning(f"事件 '{event_type}' 没有订阅者")
            return
        
        for handler in handlers:
            try:
                handler(event)
                self._stats[f"handled_{event_type}"] += 1
            except Exception as e:
                # 异常隔离：一个处理器失败不影响其他处理器
                logger.error(
                    f"处理器 {handler.__name__} 处理事件 '{event_type}' 失败: {str(e)}",
                    exc_info=True
                )
                self._stats[f"failed_{event_type}"] += 1
    
    def clear_subscribers(self, event_type: str = None):
        """清除订阅者
        
        Args:
            event_type: 如果指定，只清除该类型的订阅者；否则清除所有
        """
        if event_type:
            self._subscribers[event_type].clear()
            logger.info(f"已清除事件 '{event_type}' 的所有订阅者")
        else:
            self._subscribers.clear()
            logger.info("已清除所有事件订阅者")
    
    def get_event_history(self, event_type: str = None) -> List[BaseEvent]:
        """获取事件历史
        
        Args:
            event_type: 如果指定，只返回该类型的事件
            
        Returns:
            事件列表
        """
        if event_type:
            # 通过事件类名过滤
            return [
                e for e in self._event_history 
                if type(e).__name__.lower().replace('event', '') == event_type.lower()
            ]
        return self._event_history.copy()
    
    def clear_history(self):
        """清除事件历史"""
        self._event_history.clear()
        logger.info("已清除事件历史")
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return dict(self._stats)
    
    def get_subscriber_count(self, event_type: str = None) -> int:
        """获取订阅者数量
        
        Args:
            event_type: 如果指定，返回该类型的订阅者数量
            
        Returns:
            订阅者数量
        """
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self._subscribers.values())
    
    def __repr__(self) -> str:
        """字符串表示"""
        total_subscribers = self.get_subscriber_count()
        event_types = len(self._subscribers)
        return (
            f"EventBus(event_types={event_types}, "
            f"total_subscribers={total_subscribers}, "
            f"history_size={len(self._event_history)})"
        )
