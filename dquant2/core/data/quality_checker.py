"""数据质量检查模块

检查数据的完整性、一致性和异常值
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """数据质量检查器
    
    检查数据质量，包括完整性、一致性、异常值
    """
    
    def __init__(self):
        """初始化质量检查器"""
        self.check_results = []
    
    def check_completeness(self, df: pd.DataFrame, symbol: str) -> Dict:
        """检查数据完整性
        
        Args:
            df: 数据DataFrame
            symbol: 股票代码
            
        Returns:
            检查结果字典
        """
        results = {
            'symbol': symbol,
            'check_type': '完整性检查',
            'timestamp': datetime.now(),
            'issues': []
        }
        
        if df.empty:
            results['issues'].append({
                'severity': 'ERROR',
                'message': '数据为空'
            })
            return results
        
        # 检查缺失值
        missing_cols = df.isnull().sum()
        for col, count in missing_cols.items():
            if count > 0:
                pct = count / len(df) * 100
                severity = 'ERROR' if pct > 10 else 'WARNING'
                results['issues'].append({
                    'severity': severity,
                    'field': col,
                    'message': f'{col} 列有 {count} 个缺失值 ({pct:.2f}%)'
                })
        
        # 检查日期连续性
        if 'date' in df.columns or isinstance(df.index, pd.DatetimeIndex):
            if isinstance(df.index, pd.DatetimeIndex):
                date_series = pd.Series(df.index)
            else:
                date_series = pd.to_datetime(df['date'])
            
            date_diff = date_series.diff().dt.days
            
            # 跳过周末（2-3天）是正常的，超过5天可能有问题
            large_gaps = date_diff[date_diff > 5]
            if len(large_gaps) > 0:
                results['issues'].append({
                    'severity': 'WARNING',
                    'message': f'发现 {len(large_gaps)} 个较大的日期间隔（>5天）'
                })
        
        if not results['issues']:
            results['issues'].append({
                'severity': 'INFO',
                'message': '数据完整性良好'
            })
        
        return results
    
    def check_consistency(self, df: pd.DataFrame, symbol: str) -> Dict:
        """检查数据一致性
        
        Args:
            df: 数据DataFrame
            symbol: 股票代码
            
        Returns:
            检查结果字典
        """
        results = {
            'symbol': symbol,
            'check_type': '一致性检查',
            'timestamp': datetime.now(),
            'issues': []
        }
        
        if df.empty:
            return results
        
        # 检查价格逻辑关系
        required_cols = ['open', 'high', 'low', 'close']
        if all(col in df.columns for col in required_cols):
            # high 应该 >= max(open, close, low)
            invalid_high = (
                (df['high'] < df['open']) | 
                (df['high'] < df['close']) | 
                (df['high'] < df['low'])
            ).sum()
            
            if invalid_high > 0:
                results['issues'].append({
                    'severity': 'ERROR',
                    'message': f'发现 {invalid_high} 行最高价不一致（最高价 < 开盘/收盘/最低）'
                })
            
            # low 应该 <= min(open, close, high)
            invalid_low = (
                (df['low'] > df['open']) | 
                (df['low'] > df['close']) | 
                (df['low'] > df['high'])
            ).sum()
            
            if invalid_low > 0:
                results['issues'].append({
                    'severity': 'ERROR',
                    'message': f'发现 {invalid_low} 行最低价不一致（最低价 > 开盘/收盘/最高）'
                })
        
        # 检查负值
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                negative_count = (df[col] <= 0).sum()
                if negative_count > 0:
                    results['issues'].append({
                        'severity': 'ERROR',
                        'field': col,
                        'message': f'{col} 列有 {negative_count} 个非正值'
                    })
        
        if not results['issues']:
            results['issues'].append({
                'severity': 'INFO',
                'message': '数据一致性良好'
            })
        
        return results
    
    def check_outliers(self, df: pd.DataFrame, symbol: str) -> Dict:
        """检查异常值
        
        使用 3-sigma 规则和 IQR 方法检测异常值
        
        Args:
            df: 数据DataFrame
            symbol: 股票代码
            
        Returns:
            检查结果字典
        """
        results = {
            'symbol': symbol,
            'check_type': '异常值检查',
            'timestamp': datetime.now(),
            'issues': []
        }
        
        if df.empty or len(df) < 30:
            return results
        
        # 检查涨跌幅异常
        if 'pct_chg' in df.columns:
            pct_chg = df['pct_chg'].dropna()
            
            if len(pct_chg) > 0:
                # 3-sigma 规则
                mean = pct_chg.mean()
                std = pct_chg.std()
                outliers_3sigma = ((pct_chg - mean).abs() > 3 * std).sum()
                
                # IQR 方法
                Q1 = pct_chg.quantile(0.25)
                Q3 = pct_chg.quantile(0.75)
                IQR = Q3 - Q1
                outliers_iqr = (
                    (pct_chg < Q1 - 1.5 * IQR) | 
                    (pct_chg > Q3 + 1.5 * IQR)
                ).sum()
                
                if outliers_3sigma > 0:
                    results['issues'].append({
                        'severity': 'WARNING',
                        'field': 'pct_chg',
                        'message': f'发现 {outliers_3sigma} 个异常涨跌幅（3-sigma）',
                        'method': '3-sigma'
                    })
                
                if outliers_iqr > 0:
                    results['issues'].append({
                        'severity': 'INFO',
                        'field': 'pct_chg',
                        'message': f'发现 {outliers_iqr} 个异常涨跌幅（IQR）',
                        'method': 'IQR'
                    })
        
        # 检查成交量异常
        if 'volume' in df.columns:
            volume = df['volume'].dropna()
            
            if len(volume) > 0:
                # 检查零成交量
                zero_volume = (volume == 0).sum()
                if zero_volume > 0:
                    results['issues'].append({
                        'severity': 'WARNING',
                        'field': 'volume',
                        'message': f'发现 {zero_volume} 个零成交量交易日'
                    })
                
                # 检查异常放量
                median_volume = volume.median()
                extreme_volume = (volume > median_volume * 10).sum()
                if extreme_volume > 0:
                    results['issues'].append({
                        'severity': 'INFO',
                        'field': 'volume',
                        'message': f'发现 {extreme_volume} 个异常放量（>中位数10倍）'
                    })
        
        if not results['issues']:
            results['issues'].append({
                'severity': 'INFO',
                'message': '未发现明显异常值'
            })
        
        return results
    
    def run_full_check(self, df: pd.DataFrame, symbol: str) -> Dict:
        """运行完整质量检查
        
        Args:
            df: 数据DataFrame
            symbol: 股票代码
            
        Returns:
            完整检查结果
        """
        logger.info(f"开始数据质量检查: {symbol}")
        
        results = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'checks': []
        }
        
        # 1. 完整性检查
        completeness = self.check_completeness(df, symbol)
        results['checks'].append(completeness)
        
        # 2. 一致性检查
        consistency = self.check_consistency(df, symbol)
        results['checks'].append(consistency)
        
        # 3. 异常值检查
        outliers = self.check_outliers(df, symbol)
        results['checks'].append(outliers)
        
        # 统计问题数量
        total_errors = sum(
            1 for check in results['checks'] 
            for issue in check['issues'] 
            if issue['severity'] == 'ERROR'
        )
        total_warnings = sum(
            1 for check in results['checks'] 
            for issue in check['issues'] 
            if issue['severity'] == 'WARNING'
        )
        
        results['summary'] = {
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'quality_score': self._calculate_quality_score(total_errors, total_warnings, len(df))
        }
        
        logger.info(
            f"质量检查完成: {symbol}, "
            f"错误: {total_errors}, 警告: {total_warnings}, "
            f"评分: {results['summary']['quality_score']:.1f}/100"
        )
        
        return results
    
    def _calculate_quality_score(self, errors: int, warnings: int, total_rows: int) -> float:
        """计算数据质量评分
        
        Args:
            errors: 错误数量
            warnings: 警告数量
            total_rows: 总行数
            
        Returns:
            质量评分（0-100）
        """
        # 基础分 100
        score = 100.0
        
        # 每个错误扣 10 分
        score -= errors * 10
        
        # 每个警告扣 2 分
        score -= warnings * 2
        
        # 不低于 0 分
        score = max(0.0, score)
        
        return score
    
    def generate_report(self, check_results: Dict) -> str:
        """生成质量检查报告
        
        Args:
            check_results: 检查结果字典
            
        Returns:
            报告文本
        """
        report = []
        report.append("=" * 60)
        report.append(f"数据质量检查报告 - {check_results['symbol']}")
        report.append("=" * 60)
        report.append(f"检查时间: {check_results['timestamp']}")
        report.append("")
        
        # 摘要
        summary = check_results['summary']
        report.append(f"质量评分: {summary['quality_score']:.1f}/100")
        report.append(f"错误: {summary['total_errors']}")
        report.append(f"警告: {summary['total_warnings']}")
        report.append("")
        
        # 详细结果
        for check in check_results['checks']:
            report.append(f"【{check['check_type']}】")
            for issue in check['issues']:
                severity_icon = {
                    'ERROR': '❌',
                    'WARNING': '⚠️',
                    'INFO': 'ℹ️'
                }.get(issue['severity'], '•')
                
                report.append(f"  {severity_icon} {issue['message']}")
            report.append("")
        
        report.append("=" * 60)
        
        return '\n'.join(report)


class DataValidator:
    """数据验证器
    
    提供快速的数据验证方法
    """
    
    @staticmethod
    def is_valid_ohlc_data(df: pd.DataFrame) -> bool:
        """验证是否为有效的 OHLC 数据
        
        Args:
            df: 数据DataFrame
            
        Returns:
            是否有效
        """
        required_cols = ['open', 'high', 'low', 'close']
        
        # 检查必需列
        if not all(col in df.columns for col in required_cols):
            return False
        
        # 检查数据量
        if len(df) < 2:
            return False
        
        # 检查价格逻辑
        invalid = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ).any()
        
        return not invalid
    
    @staticmethod
    def has_sufficient_data(df: pd.DataFrame, min_days: int = 60) -> bool:
        """检查数据是否足够
        
        Args:
            df: 数据DataFrame
            min_days: 最小天数要求
            
        Returns:
            数据是否足够
        """
        return len(df) >= min_days
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """清理数据
        
        1. 删除缺失值过多的行
        2. 修正明显错误的数据
        3. 删除重复行
        
        Args:
            df: 原始数据
            
        Returns:
            清理后的数据
        """
        if df.empty:
            return df
        
        df_clean = df.copy()
        
        # 1. 删除关键列全为空的行
        key_cols = ['open', 'high', 'low', 'close']
        existing_key_cols = [col for col in key_cols if col in df_clean.columns]
        if existing_key_cols:
            df_clean = df_clean.dropna(subset=existing_key_cols, how='all')
        
        # 2. 填充缺失的成交量为0
        if 'volume' in df_clean.columns:
            df_clean['volume'] = df_clean['volume'].fillna(0)
        
        # 3. 删除价格为0或负数的行
        for col in ['open', 'high', 'low', 'close']:
            if col in df_clean.columns:
                df_clean = df_clean[df_clean[col] > 0]
        
        # 4. 删除重复行
        if 'date' in df_clean.columns:
            df_clean = df_clean.drop_duplicates(subset=['date'], keep='last')
        elif isinstance(df_clean.index, pd.DatetimeIndex):
            df_clean = df_clean[~df_clean.index.duplicated(keep='last')]
        
        # 5. 修正明显错误的 high/low
        if all(col in df_clean.columns for col in ['open', 'high', 'low', 'close']):
            # high 应该是四个价格中的最大值
            df_clean['high'] = df_clean[['open', 'high', 'low', 'close']].max(axis=1)
            # low 应该是四个价格中的最小值
            df_clean['low'] = df_clean[['open', 'high', 'low', 'close']].min(axis=1)
        
        cleaned_rows = len(df) - len(df_clean)
        if cleaned_rows > 0:
            logger.info(f"数据清理: 删除 {cleaned_rows} 行问题数据")
        
        return df_clean
