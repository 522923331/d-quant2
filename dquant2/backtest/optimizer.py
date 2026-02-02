"""策略参数优化模块

提供多种参数优化方法：网格搜索、随机搜索
"""

import itertools
import random
from typing import Dict, List, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """参数优化器基类"""
    
    def __init__(self, 
                 backtest_func: Callable,
                 param_space: Dict[str, List],
                 objective: str = 'sharpe_ratio'):
        """初始化参数优化器
        
        Args:
            backtest_func: 回测函数，接收参数字典，返回回测结果
            param_space: 参数空间 {'param_name': [value1, value2, ...]}
            objective: 优化目标 ('sharpe_ratio', 'total_return', 'calmar_ratio')
        """
        self.backtest_func = backtest_func
        self.param_space = param_space
        self.objective = objective
        self.results = []
    
    def optimize(self) -> Dict:
        """执行优化
        
        Returns:
            最优结果字典
        """
        raise NotImplementedError
    
    def _evaluate_params(self, params: Dict) -> Dict:
        """评估一组参数
        
        Args:
            params: 参数字典
            
        Returns:
            评估结果
        """
        try:
            result = self.backtest_func(params)
            
            # 提取目标值
            if self.objective == 'sharpe_ratio':
                objective_value = result['performance'].get('sharpe_ratio', 0.0)
            elif self.objective == 'total_return':
                objective_value = result['portfolio'].get('total_return_pct', 0.0)
            elif self.objective == 'calmar_ratio':
                # 计算卡玛比率
                annual_return = result['performance'].get('annual_return', 0.0)
                max_dd = abs(result['performance'].get('max_drawdown', 0.01))
                objective_value = annual_return / max_dd if max_dd > 0 else 0.0
            else:
                objective_value = result['performance'].get(self.objective, 0.0)
            
            return {
                'params': params,
                'objective_value': objective_value,
                'result': result,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"参数评估失败: {params}, 错误: {e}")
            return {
                'params': params,
                'objective_value': float('-inf'),
                'result': None,
                'success': False,
                'error': str(e)
            }


class GridSearchOptimizer(ParameterOptimizer):
    """网格搜索优化器
    
    遍历所有参数组合
    """
    
    def optimize(self, max_iterations: int = None) -> Dict:
        """执行网格搜索
        
        Args:
            max_iterations: 最大迭代次数，None表示遍历所有组合
            
        Returns:
            最优结果字典
        """
        logger.info("开始网格搜索优化...")
        logger.info(f"参数空间: {self.param_space}")
        
        # 生成所有参数组合
        param_names = list(self.param_space.keys())
        param_values = list(self.param_space.values())
        all_combinations = list(itertools.product(*param_values))
        
        total_combinations = len(all_combinations)
        logger.info(f"总组合数: {total_combinations}")
        
        # 限制迭代次数
        if max_iterations and total_combinations > max_iterations:
            logger.warning(f"组合数过多，随机采样 {max_iterations} 个组合")
            all_combinations = random.sample(all_combinations, max_iterations)
        
        # 评估每组参数
        self.results = []
        for i, combination in enumerate(all_combinations):
            params = dict(zip(param_names, combination))
            
            logger.info(f"[{i+1}/{len(all_combinations)}] 测试参数: {params}")
            
            result = self._evaluate_params(params)
            self.results.append(result)
            
            if result['success']:
                logger.info(
                    f"  -> {self.objective}: {result['objective_value']:.4f}"
                )
        
        # 找出最优结果
        best_result = max(
            [r for r in self.results if r['success']], 
            key=lambda x: x['objective_value'],
            default=None
        )
        
        if best_result:
            logger.info("="*60)
            logger.info("优化完成！")
            logger.info(f"最优参数: {best_result['params']}")
            logger.info(f"最优{self.objective}: {best_result['objective_value']:.4f}")
            logger.info("="*60)
        
        return {
            'best_params': best_result['params'] if best_result else None,
            'best_score': best_result['objective_value'] if best_result else None,
            'best_result': best_result['result'] if best_result else None,
            'all_results': self.results,
            'total_tested': len(all_combinations),
            'successful': sum(1 for r in self.results if r['success']),
            'objective': self.objective
        }


class RandomSearchOptimizer(ParameterOptimizer):
    """随机搜索优化器
    
    随机采样参数空间
    """
    
    def optimize(self, n_iterations: int = 50) -> Dict:
        """执行随机搜索
        
        Args:
            n_iterations: 迭代次数，默认 50
            
        Returns:
            最优结果字典
        """
        logger.info("开始随机搜索优化...")
        logger.info(f"参数空间: {self.param_space}")
        logger.info(f"迭代次数: {n_iterations}")
        
        # 随机采样参数
        self.results = []
        for i in range(n_iterations):
            # 为每个参数随机选择一个值
            params = {
                name: random.choice(values)
                for name, values in self.param_space.items()
            }
            
            logger.info(f"[{i+1}/{n_iterations}] 测试参数: {params}")
            
            result = self._evaluate_params(params)
            self.results.append(result)
            
            if result['success']:
                logger.info(
                    f"  -> {self.objective}: {result['objective_value']:.4f}"
                )
        
        # 找出最优结果
        best_result = max(
            [r for r in self.results if r['success']], 
            key=lambda x: x['objective_value'],
            default=None
        )
        
        if best_result:
            logger.info("="*60)
            logger.info("优化完成！")
            logger.info(f"最优参数: {best_result['params']}")
            logger.info(f"最优{self.objective}: {best_result['objective_value']:.4f}")
            logger.info("="*60)
        
        return {
            'best_params': best_result['params'] if best_result else None,
            'best_score': best_result['objective_value'] if best_result else None,
            'best_result': best_result['result'] if best_result else None,
            'all_results': self.results,
            'total_tested': n_iterations,
            'successful': sum(1 for r in self.results if r['success']),
            'objective': self.objective
        }


class WalkForwardOptimizer:
    """Walk-Forward 优化器
    
    滚动优化，避免过拟合
    """
    
    def __init__(self,
                 backtest_func: Callable,
                 param_space: Dict[str, List],
                 train_period: int = 252,
                 test_period: int = 63,
                 objective: str = 'sharpe_ratio'):
        """初始化 Walk-Forward 优化器
        
        Args:
            backtest_func: 回测函数
            param_space: 参数空间
            train_period: 训练期长度（交易日），默认 252 天（1年）
            test_period: 测试期长度（交易日），默认 63 天（3个月）
            objective: 优化目标
        """
        self.backtest_func = backtest_func
        self.param_space = param_space
        self.train_period = train_period
        self.test_period = test_period
        self.objective = objective
        self.walk_results = []
    
    def optimize(self, data_length: int) -> Dict:
        """执行 Walk-Forward 优化
        
        Args:
            data_length: 数据总长度
            
        Returns:
            优化结果字典
        """
        logger.info("开始 Walk-Forward 优化...")
        logger.info(f"训练期: {self.train_period} 天, 测试期: {self.test_period} 天")
        
        # 计算窗口数量
        total_windows = (data_length - self.train_period) // self.test_period
        logger.info(f"总窗口数: {total_windows}")
        
        self.walk_results = []
        
        for i in range(total_windows):
            train_start = i * self.test_period
            train_end = train_start + self.train_period
            test_start = train_end
            test_end = test_start + self.test_period
            
            logger.info(f"\n窗口 {i+1}/{total_windows}")
            logger.info(f"训练期: [{train_start}, {train_end})")
            logger.info(f"测试期: [{test_start}, {test_end})")
            
            # 在训练期进行参数优化
            train_optimizer = GridSearchOptimizer(
                self.backtest_func,
                self.param_space,
                self.objective
            )
            
            # TODO: 实现区间回测
            # 这里需要修改 backtest_func 支持指定数据区间
            
            logger.info("训练期优化暂未实现，需要支持区间回测")
        
        return {
            'method': 'walk_forward',
            'windows': self.walk_results,
            'total_windows': total_windows,
            'status': 'pending_implementation'
        }


def optimize_strategy_params(backtest_engine_class,
                            config_base: Dict,
                            param_space: Dict[str, List],
                            method: str = 'grid',
                            objective: str = 'sharpe_ratio',
                            n_iterations: int = 50) -> Dict:
    """便捷的策略参数优化函数
    
    Args:
        backtest_engine_class: 回测引擎类
        config_base: 基础配置字典
        param_space: 参数空间
        method: 优化方法 ('grid', 'random')
        objective: 优化目标
        n_iterations: 迭代次数（随机搜索）
        
    Returns:
        优化结果
    """
    # 定义回测函数
    def run_backtest(params: Dict) -> Dict:
        from dquant2.backtest.config import BacktestConfig
        
        # 合并参数
        config_dict = config_base.copy()
        config_dict['strategy_params'] = params
        
        # 创建配置
        config = BacktestConfig(**config_dict)
        
        # 运行回测
        engine = backtest_engine_class(config)
        return engine.run()
    
    # 选择优化器
    if method == 'grid':
        optimizer = GridSearchOptimizer(run_backtest, param_space, objective)
        return optimizer.optimize()
    elif method == 'random':
        optimizer = RandomSearchOptimizer(run_backtest, param_space, objective)
        return optimizer.optimize(n_iterations)
    else:
        raise ValueError(f"未知的优化方法: {method}")
