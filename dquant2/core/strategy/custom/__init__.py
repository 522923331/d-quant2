"""自定义策略模块

该模块负责加载和管理用户自定义策略

使用方法：
1. 在 custom/ 目录下创建新的策略文件（可复制 custom_template.py）
2. 修改策略名称和实现逻辑
3. 策略会自动加载并注册到策略工厂
"""

import os
import sys
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# 自定义策略目录
CUSTOM_STRATEGY_DIR = Path(__file__).parent

# 存储已加载的自定义策略元数据
_loaded_custom_strategies: Dict[str, Dict[str, Any]] = {}


def load_custom_strategies() -> Dict[str, Dict[str, Any]]:
    """加载所有自定义策略
    
    扫描 custom/ 目录，加载所有策略文件
    
    Returns:
        策略元数据字典 {策略名: 元数据}
    """
    global _loaded_custom_strategies
    
    if _loaded_custom_strategies:
        return _loaded_custom_strategies
    
    # 扫描目录
    for file_path in CUSTOM_STRATEGY_DIR.glob("*.py"):
        if file_path.name.startswith("_"):
            continue
        
        try:
            # 动态导入模块
            module_name = f"dquant2.core.strategy.custom.{file_path.stem}"
            
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
            
            # 获取策略元数据
            if hasattr(module, 'STRATEGY_METADATA'):
                metadata = module.STRATEGY_METADATA
                strategy_name = metadata.get('name')
                if strategy_name:
                    _loaded_custom_strategies[strategy_name] = metadata
                    logger.info(f"已加载自定义策略: {metadata.get('display_name', strategy_name)}")
        
        except Exception as e:
            logger.warning(f"加载策略文件 {file_path.name} 失败: {e}")
    
    return _loaded_custom_strategies


def get_custom_strategy_list() -> List[Dict[str, Any]]:
    """获取所有自定义策略列表
    
    Returns:
        策略信息列表
    """
    strategies = load_custom_strategies()
    return [
        {
            'name': name,
            'display_name': meta.get('display_name', name),
            'description': meta.get('description', ''),
            'params': meta.get('params', {})
        }
        for name, meta in strategies.items()
    ]


def get_custom_strategy_params(strategy_name: str) -> Dict[str, Any]:
    """获取指定自定义策略的参数定义
    
    Args:
        strategy_name: 策略名称
        
    Returns:
        参数定义字典
    """
    strategies = load_custom_strategies()
    if strategy_name in strategies:
        return strategies[strategy_name].get('params', {})
    return {}


def reload_custom_strategies():
    """重新加载所有自定义策略
    
    在添加新策略文件后调用此方法刷新
    """
    global _loaded_custom_strategies
    _loaded_custom_strategies = {}
    
    # 清除已导入的模块
    modules_to_remove = [
        name for name in sys.modules 
        if name.startswith('dquant2.core.strategy.custom.')
        and not name.endswith('.__init__')
    ]
    for module_name in modules_to_remove:
        del sys.modules[module_name]
    
    # 重新加载
    load_custom_strategies()


# 模块加载时自动加载自定义策略
load_custom_strategies()
