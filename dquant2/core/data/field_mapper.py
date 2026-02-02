"""字段映射器

统一不同数据源的字段名和数据类型
参考: QuantOL/src/core/data/field_mapper.py
"""

import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class FieldMapper:
    """字段映射器
    
    将不同数据源的字段名统一为标准字段名
    """
    
    # 标准字段名
    STANDARD_FIELDS = [
        'date', 'open', 'high', 'low', 'close', 
        'volume', 'amount', 'turnover', 'pct_chg'
    ]
    
    # 数据源字段映射
    FIELD_MAPS = {
        'akshare': {
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '换手率': 'turnover',
            '涨跌幅': 'pct_chg',
            '涨跌额': 'change',
            '振幅': 'amplitude'
        },
        'baostock': {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'turn': 'turnover',
            'pctChg': 'pct_chg',
            'peTTM': 'pe_ttm',
            'pbMRQ': 'pb_mrq',
            'psTTM': 'ps_ttm'
        },
        'tushare': {
            'trade_date': 'date',
            'ts_code': 'symbol',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'amount',
            'turnover_rate': 'turnover',
            'pct_chg': 'pct_chg'
        }
    }
    
    # 数据类型定义
    FIELD_TYPES = {
        'date': 'datetime',
        'symbol': 'str',
        'open': 'float',
        'high': 'float',
        'low': 'float',
        'close': 'float',
        'volume': 'float',
        'amount': 'float',
        'turnover': 'float',
        'pct_chg': 'float',
        'pe_ratio': 'float',
        'pb_ratio': 'float',
        'market_cap': 'float'
    }
    
    @classmethod
    def map_fields(cls, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """映射字段名
        
        Args:
            df: 原始数据DataFrame
            source: 数据源名称 ('akshare', 'baostock', 'tushare')
            
        Returns:
            映射后的DataFrame
        """
        if df.empty:
            return df
        
        source = source.lower()
        
        if source not in cls.FIELD_MAPS:
            logger.warning(f"未知的数据源: {source}，跳过字段映射")
            return df
        
        field_map = cls.FIELD_MAPS[source]
        
        # 重命名列
        df_mapped = df.rename(columns=field_map)
        
        logger.debug(f"字段映射完成: {source}, {len(df_mapped.columns)} 列")
        
        return df_mapped
    
    @classmethod
    def convert_types(cls, df: pd.DataFrame) -> pd.DataFrame:
        """转换数据类型
        
        Args:
            df: 数据DataFrame
            
        Returns:
            类型转换后的DataFrame
        """
        if df.empty:
            return df
        
        df_converted = df.copy()
        
        for field, dtype in cls.FIELD_TYPES.items():
            if field in df_converted.columns:
                try:
                    if dtype == 'datetime':
                        df_converted[field] = pd.to_datetime(df_converted[field])
                    elif dtype == 'float':
                        df_converted[field] = pd.to_numeric(
                            df_converted[field], 
                            errors='coerce'
                        )
                    elif dtype == 'int':
                        df_converted[field] = pd.to_numeric(
                            df_converted[field], 
                            errors='coerce'
                        ).astype('Int64')  # 使用可空整数类型
                    elif dtype == 'str':
                        df_converted[field] = df_converted[field].astype(str)
                except Exception as e:
                    logger.warning(f"字段类型转换失败: {field}, {e}")
        
        return df_converted
    
    @classmethod
    def validate_fields(cls, df: pd.DataFrame, required_fields: list = None) -> bool:
        """验证必需字段是否存在
        
        Args:
            df: 数据DataFrame
            required_fields: 必需字段列表，默认为 ['date', 'open', 'high', 'low', 'close']
            
        Returns:
            是否通过验证
        """
        if required_fields is None:
            required_fields = ['date', 'open', 'high', 'low', 'close']
        
        missing_fields = [field for field in required_fields if field not in df.columns]
        
        if missing_fields:
            logger.error(f"缺少必需字段: {missing_fields}")
            return False
        
        return True
    
    @classmethod
    def standardize_dataframe(cls, 
                             df: pd.DataFrame, 
                             source: str,
                             validate: bool = True) -> pd.DataFrame:
        """标准化数据框
        
        完整的标准化流程：字段映射 -> 类型转换 -> 字段验证
        
        Args:
            df: 原始数据DataFrame
            source: 数据源名称
            validate: 是否验证字段
            
        Returns:
            标准化后的DataFrame
        """
        if df.empty:
            return df
        
        # 1. 字段映射
        df_std = cls.map_fields(df, source)
        
        # 2. 类型转换
        df_std = cls.convert_types(df_std)
        
        # 3. 字段验证
        if validate:
            if not cls.validate_fields(df_std):
                logger.warning("字段验证失败，但继续处理")
        
        # 4. 删除重复行
        if 'date' in df_std.columns:
            df_std = df_std.drop_duplicates(subset=['date'], keep='last')
        
        # 5. 排序
        if 'date' in df_std.columns:
            df_std = df_std.sort_values('date')
        
        logger.info(
            f"数据标准化完成: {source}, {len(df_std)} 行, "
            f"{len(df_std.columns)} 列"
        )
        
        return df_std
    
    @classmethod
    def get_field_info(cls, source: str = None) -> Dict:
        """获取字段映射信息
        
        Args:
            source: 数据源名称，为空则返回所有
            
        Returns:
            字段映射信息
        """
        if source:
            return cls.FIELD_MAPS.get(source.lower(), {})
        else:
            return cls.FIELD_MAPS
