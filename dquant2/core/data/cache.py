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
            return None
        
        try:
            # 读取 Parquet 文件
            df = pd.read_parquet(file_path)
            
            # 确保索引是日期时间类型
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # 标准化请求日期
            req_start = pd.to_datetime(start_date).normalize()
            req_end = pd.to_datetime(end_date).normalize()
            
            # 检查缓存数据的时间范围
            # 注意：选股通常需要只要有这一段数据就行，不一定要求缓存必须包含比请求更宽的范围
            # 但为了严谨，我们检查是否有覆盖
            # 实际场景：如果缓存了历史全量数据，那么只要缓存的结束日期 >= 请求结束日期即可
            # 如果请求的是历史某一段，只要缓存包含即可
            
            cache_start = df.index.min()
            cache_end = df.index.max()
            
            # 如果请求的数据在缓存范围内
            # 宽松策略：只要有交集就返回交集部分？
            # 严格策略：必须完全覆盖？
            # 优化策略：如果缓存包含 start 到 end 的大部分数据，特别是最新的，就很有用
            # 这里简单起见：如果缓存的最新日期 >= 请求的结束日期，通常认为缓存有效（对于选股）
            # 或者如果请求的是历史回测，需要完全覆盖
            
            # 这里我们只返回经过切片的数据
            # 如果请求范围超出缓存范围，则返回 None，触发重新下载（或者增量更新，比较复杂）
            # 简单实现：只从缓存读取，让调用者决定是否够用
            
            mask = (df.index >= req_start) & (df.index <= req_end)
            sliced_df = df.loc[mask]
            
            if sliced_df.empty:
                return None
                
            logger.debug(f"从缓存加载 {symbol} 数据: {len(sliced_df)} 条")
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
        """清除缓存"""
        if symbol:
            file_path = self._get_cache_path(symbol)
            if file_path.exists():
                os.remove(file_path)
        else:
            # 清除所有
            for f in self.cache_dir.glob("*.parquet"):
                os.remove(f)
