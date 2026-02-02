"""数据模块增强功能测试"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from dquant2.core.data.field_mapper import FieldMapper
from dquant2.core.data.quality_checker import DataQualityChecker, DataValidator
from dquant2.core.data.storage.sqlite_adapter import SQLiteAdapter


class TestFieldMapper:
    """测试字段映射器"""
    
    def test_akshare_mapping(self):
        """测试 AkShare 字段映射"""
        # 模拟 AkShare 数据
        df = pd.DataFrame({
            '日期': ['2024-01-01', '2024-01-02'],
            '开盘': [10.0, 10.5],
            '最高': [10.5, 11.0],
            '最低': [9.8, 10.2],
            '收盘': [10.2, 10.8],
            '成交量': [1000000, 1200000],
            '换手率': [2.5, 3.0]
        })
        
        # 映射字段
        df_mapped = FieldMapper.map_fields(df, 'akshare')
        
        # 验证映射
        assert 'date' in df_mapped.columns
        assert 'open' in df_mapped.columns
        assert 'close' in df_mapped.columns
        assert '日期' not in df_mapped.columns
        
        print("\n映射后的列:", df_mapped.columns.tolist())
    
    def test_standardize_dataframe(self):
        """测试数据标准化流程"""
        df = pd.DataFrame({
            '日期': ['2024-01-01', '2024-01-02', '2024-01-02'],  # 有重复
            '开盘': ['10.0', '10.5', '10.3'],  # 字符串类型，修复长度
            '收盘': [10.2, 10.8, 10.6],
            '最高': [10.5, 11.0, 10.9],
            '最低': [9.8, 10.2, 10.0]
        })
        
        # 标准化
        df_std = FieldMapper.standardize_dataframe(df, 'akshare')
        
        # 验证去重
        assert len(df_std) == 2
        
        # 验证类型转换
        assert df_std['open'].dtype in [np.float64, np.float32]
        
        print("\n标准化后的数据:")
        print(df_std.info())


class TestDataQualityChecker:
    """测试数据质量检查器"""
    
    def test_completeness_check(self):
        """测试完整性检查"""
        checker = DataQualityChecker()
        
        # 创建测试数据（有缺失值）
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [10.0, None, 10.5, 10.3, None, 10.8, 11.0, 10.9, 11.2, 11.5],
            'close': [10.2, 10.4, 10.6, 10.5, 10.7, 10.9, 11.1, 11.0, 11.3, 11.6],
            'high': [10.5] * 10,
            'low': [9.8] * 10
        })
        
        result = checker.check_completeness(df, '000001')
        
        assert result['check_type'] == '完整性检查'
        assert len(result['issues']) > 0  # 应该发现缺失值
        
        print("\n完整性检查结果:")
        for issue in result['issues']:
            print(f"  {issue['severity']}: {issue['message']}")
    
    def test_consistency_check(self):
        """测试一致性检查"""
        checker = DataQualityChecker()
        
        # 创建测试数据（有逻辑错误）
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [10.0, 10.5, 10.3, 10.8, 11.0],
            'high': [10.5, 10.0, 10.6, 10.9, 11.2],  # 第2行 high < open，错误
            'low': [9.8, 9.9, 9.7, 9.8, 10.0],
            'close': [10.2, 10.4, 10.5, 10.9, 11.1]
        })
        
        result = checker.check_consistency(df, '000001')
        
        assert len(result['issues']) > 0  # 应该发现逻辑错误
        
        print("\n一致性检查结果:")
        for issue in result['issues']:
            print(f"  {issue['severity']}: {issue['message']}")
    
    def test_data_cleaning(self):
        """测试数据清理"""
        # 创建有问题的数据
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [10.0, 10.5, 0.0, 10.8, 11.0],  # 有0值
            'high': [10.5, 10.8, 10.6, 10.9, 11.2],
            'low': [9.8, 9.9, 9.7, 9.8, 10.0],
            'close': [10.2, 10.4, 10.5, 10.9, 11.1],
            'volume': [1000000, None, 1200000, 1100000, 1300000]  # 有缺失
        })
        
        # 清理数据
        df_clean = DataValidator.clean_data(df)
        
        # 验证清理结果
        assert len(df_clean) == 4  # 应该删除了价格为0的行
        assert df_clean['volume'].isna().sum() == 0  # 缺失值应该被填充为0
        
        print("\n数据清理:")
        print(f"原始数据: {len(df)} 行")
        print(f"清理后: {len(df_clean)} 行")


class TestSQLiteAdapter:
    """测试 SQLite 适配器"""
    
    def test_save_and_load_kline(self):
        """测试保存和加载 K 线数据"""
        # 使用临时数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # 创建适配器
            adapter = SQLiteAdapter(db_path)
            
            # 创建测试数据
            df = pd.DataFrame({
                'date': pd.date_range('2024-01-01', periods=10),
                'open': np.random.uniform(10, 11, 10),
                'high': np.random.uniform(11, 12, 10),
                'low': np.random.uniform(9, 10, 10),
                'close': np.random.uniform(10, 11, 10),
                'volume': np.random.uniform(1000000, 2000000, 10)
            })
            
            # 保存数据
            rows = adapter.save_kline_data('000001', df)
            assert rows == 10
            
            # 加载数据
            df_loaded = adapter.load_kline_data('000001')
            assert len(df_loaded) == 10
            assert 'open' in df_loaded.columns
            assert 'close' in df_loaded.columns
            
            # 加载指定日期范围
            df_range = adapter.load_kline_data(
                '000001',
                '2024-01-03',
                '2024-01-06'
            )
            assert len(df_range) == 4
            
            print(f"\n保存 {rows} 行，加载 {len(df_loaded)} 行")
            
            # 清理
            adapter.close()
            
        finally:
            # 删除临时数据库
            Path(db_path).unlink(missing_ok=True)
    
    def test_database_stats(self):
        """测试数据库统计"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            adapter = SQLiteAdapter(db_path)
            
            # 添加一些数据
            for i, symbol in enumerate(['000001', '000002', '000003']):
                df = pd.DataFrame({
                    'date': pd.date_range('2024-01-01', periods=5),
                    'open': [10.0] * 5,
                    'close': [10.5] * 5,
                    'high': [11.0] * 5,
                    'low': [9.8] * 5,
                    'volume': [1000000] * 5
                })
                adapter.save_kline_data(symbol, df)
            
            # 获取统计
            stats = adapter.get_database_stats()
            
            assert stats['total_symbols'] == 3
            assert stats['total_kline_records'] == 15
            
            print("\n数据库统计:")
            print(f"股票数: {stats['total_symbols']}")
            print(f"K线记录数: {stats['total_kline_records']}")
            print(f"数据库大小: {stats['db_size_mb']:.2f} MB")
            
            adapter.close()
            
        finally:
            Path(db_path).unlink(missing_ok=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
