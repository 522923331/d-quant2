"""并行回测模块

使用多进程加速批量回测
"""

import logging
from typing import List, Dict, Callable, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import time

from dquant2.backtest.engine import BacktestEngine
from dquant2.backtest.config import BacktestConfig

logger = logging.getLogger(__name__)


def run_single_backtest(config_dict: Dict) -> Dict:
    """运行单个回测（用于多进程）
    
    Args:
        config_dict: 回测配置字典
        
    Returns:
        回测结果字典
    """
    try:
        # 从字典创建配置对象
        config = BacktestConfig(**config_dict)
        
        # 创建并运行回测引擎
        engine = BacktestEngine(config)
        results = engine.run()
        
        # 添加成功标记
        results['success'] = True
        results['error'] = None
        
        return results
    
    except Exception as e:
        # 返回错误信息
        return {
            'success': False,
            'error': str(e),
            'config': config_dict
        }


class ParallelBacktest:
    """并行回测管理器"""
    
    def __init__(self, max_workers: Optional[int] = None):
        """初始化
        
        Args:
            max_workers: 最大工作进程数，默认为CPU核心数
        """
        self.max_workers = max_workers or cpu_count()
        logger.info(f"并行回测初始化，最大工作进程数: {self.max_workers}")
    
    def run_batch(
        self,
        configs: List[BacktestConfig],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict]:
        """批量运行回测（并行）
        
        Args:
            configs: 回测配置列表
            progress_callback: 进度回调函数 (message, current, total)
            
        Returns:
            回测结果列表
        """
        total = len(configs)
        logger.info(f"开始并行回测，共 {total} 个任务")
        
        # 转换配置为字典（多进程需要可序列化对象）
        config_dicts = [config.to_dict() for config in configs]
        
        # 使用进程池执行
        results = []
        start_time = time.time()
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_config = {
                executor.submit(run_single_backtest, config_dict): i
                for i, config_dict in enumerate(config_dicts)
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_config):
                completed += 1
                config_idx = future_to_config[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # 调用进度回调
                    if progress_callback:
                        symbol = config_dicts[config_idx].get('symbol', 'N/A')
                        if result['success']:
                            message = f"✓ {symbol} 完成"
                        else:
                            message = f"✗ {symbol} 失败: {result['error']}"
                        progress_callback(message, completed, total)
                    
                except Exception as e:
                    # 捕获执行异常
                    logger.error(f"任务 {config_idx} 执行失败: {e}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'config': config_dicts[config_idx]
                    })
        
        # 统计结果
        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in results if r['success'])
        failure_count = total - success_count
        
        logger.info(
            f"并行回测完成 - 耗时: {elapsed_time:.2f}秒, "
            f"成功: {success_count}, 失败: {failure_count}"
        )
        
        return results
    
    def run_batch_for_symbols(
        self,
        symbols: List[str],
        base_config: Dict,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict]:
        """为多个股票批量运行回测
        
        Args:
            symbols: 股票代码列表
            base_config: 基础配置字典（除symbol外的配置）
            progress_callback: 进度回调函数
            
        Returns:
            回测结果列表
        """
        # 为每个股票创建配置
        configs = []
        for symbol in symbols:
            config_dict = base_config.copy()
            config_dict['symbol'] = symbol
            config = BacktestConfig(**config_dict)
            configs.append(config)
        
        # 批量运行
        return self.run_batch(configs, progress_callback)
    
    def run_parameter_optimization(
        self,
        base_config: Dict,
        param_grid: Dict[str, List],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict]:
        """参数优化（网格搜索）
        
        Args:
            base_config: 基础配置字典
            param_grid: 参数网格，例如：
                {
                    'fast_period': [3, 5, 10],
                    'slow_period': [20, 30, 60]
                }
            progress_callback: 进度回调函数
            
        Returns:
            回测结果列表（按收益率排序）
        """
        import itertools
        
        # 生成所有参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))
        
        logger.info(f"参数优化 - 共 {len(param_combinations)} 个参数组合")
        
        # 为每个参数组合创建配置
        configs = []
        for combo in param_combinations:
            config_dict = base_config.copy()
            
            # 更新策略参数
            strategy_params = config_dict.get('strategy_params', {}).copy()
            for name, value in zip(param_names, combo):
                strategy_params[name] = value
            config_dict['strategy_params'] = strategy_params
            
            config = BacktestConfig(**config_dict)
            configs.append(config)
        
        # 批量运行
        results = self.run_batch(configs, progress_callback)
        
        # 按收益率排序
        successful_results = [r for r in results if r['success']]
        successful_results.sort(
            key=lambda x: x.get('portfolio', {}).get('total_return_pct', -float('inf')),
            reverse=True
        )
        
        # 打印最佳参数
        if successful_results:
            best = successful_results[0]
            best_params = best['config'].get('strategy_params', {})
            best_return = best['portfolio']['total_return_pct']
            logger.info(f"最佳参数: {best_params}, 收益率: {best_return:.2f}%")
        
        return successful_results


# 便捷函数
def parallel_backtest_symbols(
    symbols: List[str],
    base_config: Dict,
    max_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> List[Dict]:
    """并行回测多个股票（便捷函数）
    
    Args:
        symbols: 股票代码列表
        base_config: 基础配置字典
        max_workers: 最大工作进程数
        progress_callback: 进度回调函数
        
    Returns:
        回测结果列表
    """
    parallel = ParallelBacktest(max_workers)
    return parallel.run_batch_for_symbols(symbols, base_config, progress_callback)


def optimize_parameters(
    base_config: Dict,
    param_grid: Dict[str, List],
    max_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> List[Dict]:
    """参数优化（便捷函数）
    
    Args:
        base_config: 基础配置字典
        param_grid: 参数网格
        max_workers: 最大工作进程数
        progress_callback: 进度回调函数
        
    Returns:
        回测结果列表（按收益率排序）
    """
    parallel = ParallelBacktest(max_workers)
    return parallel.run_parameter_optimization(base_config, param_grid, progress_callback)
