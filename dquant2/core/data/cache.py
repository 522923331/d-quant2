"""数据缓存模块

实现基于 Parquet 的本地文件缓存，加速数据读取
"""

import os
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ParquetCache:
    """Parquet 本地缓存管理器
    
    将股票数据缓存为 Parquet 文件，按股票代码存储
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录，默认为 data/cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, symbol: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{symbol}.parquet"
    
    def load(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期 YYYYMMDD 或 YYYY-MM-DD
            
        Returns:
            如果缓存存在且覆盖请求的时间范围，返回 DataFrame；否则返回 None
        """
        file_path = self._get_cache_path(symbol)
        if not file_path.exists():
            logger.debug(f"缓存未命中 {symbol}: 文件不存在")
            return None
        
        try:
            # 读取 Parquet 文件
            df = pd.read_parquet(file_path)
            
            # 确保索引是日期时间类型
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # 标准化请求日期（兼容两种格式）
            req_start = pd.to_datetime(start_date, format='mixed').normalize()
            req_end = pd.to_datetime(end_date, format='mixed').normalize()
            
            # 检查缓存数据的时间范围
            cache_start = df.index.min()
            cache_end = df.index.max()
            
            logger.info(f"📦 缓存检查 {symbol}: 请求 {req_start.date()} ~ {req_end.date()}, 缓存 {cache_start.date()} ~ {cache_end.date()}")
            
            # 计算覆盖率：缓存是否完全覆盖请求范围
            # 策略：如果缓存的起始日期 <= 请求起始，且缓存的结束日期 >= 请求结束，认为完全覆盖
            # 考虑到交易日的不连续性，我们允许一定的容差
            fully_covered = (cache_start <= req_start) and (cache_end >= req_end)
            
            if not fully_covered:
                # 计算实际数据可用性
                mask = (df.index >= req_start) & (df.index <= req_end)
                available_data = df.loc[mask]
                
                if available_data.empty:
                    logger.info(f"❌ 缓存无效 {symbol}: 请求范围完全在缓存外")
                    return None
                
                # 有部分数据，计算覆盖率
                # 简单策略：如果缓存数据少于请求范围的70%，认为不够，返回None触发完整下载
                # 这里用天数估算（实际交易日会更少）
                requested_days = (req_end - req_start).days
                available_days = (available_data.index.max() - available_data.index.min()).days
                
                coverage_ratio = available_days / max(requested_days, 1)
                
                logger.info(f"⚠️  部分缓存 {symbol}: 覆盖率 {coverage_ratio:.1%} ({len(available_data)}条/{requested_days}天)")
                
                # 如果覆盖率太低，返回None触发重新下载
                if coverage_ratio < 0.7:
                    logger.info(f"❌ 缓存覆盖率不足 {symbol}: {coverage_ratio:.1%} < 70%")
                    return None
            
            # 返回请求范围内的数据
            mask = (df.index >= req_start) & (df.index <= req_end)
            sliced_df = df.loc[mask]
            
            if sliced_df.empty:
                logger.info(f"❌ 缓存无效 {symbol}: 切片后无数据")
                return None
            
            logger.info(f"✅ 缓存命中 {symbol}: 返回 {len(sliced_df)} 条数据")
            return sliced_df
            
        except Exception as e:
            logger.warning(f"读取缓存失败 {symbol}: {e}")
            return None
    
    def save(self, symbol: str, df: pd.DataFrame):
        """保存数据到缓存
        
        Args:
            symbol: 股票代码
            df: 股票数据 DataFrame
        """
        if df is None or df.empty:
            return
            
        file_path = self._get_cache_path(symbol)
        
        try:
            # 如果文件已存在，合并数据
            if file_path.exists():
                try:
                    existing_df = pd.read_parquet(file_path)
                    # 合并并去重
                    combined_df = pd.concat([existing_df, df])
                    combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                    combined_df.sort_index(inplace=True)
                    df = combined_df
                except Exception as e:
                    logger.warning(f"合并缓存失败 {symbol}, 将覆盖: {e}")
            
            # 保存为 Parquet
            df.to_parquet(file_path, compression='snappy')
            logger.debug(f"已缓存 {symbol} 数据: {len(df)} 条")
            
        except Exception as e:
            logger.error(f"写入缓存失败 {symbol}: {e}")

    def clear(self, symbol: Optional[str] = None):
        """清除缓存
        
        Args:
            symbol: 股票代码，如果为None则清除所有缓存
        """
        if symbol:
            file_path = self._get_cache_path(symbol)
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"🗑️  已清除 {symbol} 的缓存")
        else:
            # 清除所有
            count = 0
            for f in self.cache_dir.glob("*.parquet"):
                os.remove(f)
                count += 1
            logger.info(f"🗑️  已清除所有缓存 ({count} 个文件)")
    
    def get_cache_info(self, symbol: str) -> Optional[dict]:
        """获取指定股票的缓存信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            缓存信息字典，包含：文件大小、数据条数、日期范围等
        """
        file_path = self._get_cache_path(symbol)
        if not file_path.exists():
            return None
        
        try:
            df = pd.read_parquet(file_path)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            file_size = os.path.getsize(file_path)
            
            return {
                'symbol': symbol,
                'file_path': str(file_path),
                'file_size': file_size,
                'file_size_mb': file_size / (1024 * 1024),
                'rows': len(df),
                'columns': list(df.columns),
                'start_date': df.index.min(),
                'end_date': df.index.max(),
                'days_span': (df.index.max() - df.index.min()).days
            }
        except Exception as e:
            logger.error(f"获取缓存信息失败 {symbol}: {e}")
            return None
    
    def get_cache_stats(self) -> dict:
        """获取缓存目录统计信息
        
        Returns:
            统计信息字典
        """
        parquet_files = list(self.cache_dir.glob("*.parquet"))
        total_size = sum(f.stat().st_size for f in parquet_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'total_files': len(parquet_files),
            'total_size_mb': total_size / (1024 * 1024),
            'files': [f.stem for f in parquet_files]
        }
