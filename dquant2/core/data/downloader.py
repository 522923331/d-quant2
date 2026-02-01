"""数据下载模块

统一的数据下载接口，支持批量下载和进度追踪
"""

import logging
from typing import List, Dict, Callable, Optional
from datetime import datetime
import time

import pandas as pd

from .cache import ParquetCache

logger = logging.getLogger(__name__)


class DataDownloader:
    """数据下载器
    
    提供统一的数据下载接口，支持单只、批量和市场级别下载
    支持智能增量更新
    """
    
    def __init__(self, data_provider, cache: Optional[ParquetCache] = None):
        """初始化下载器
        
        Args:
            data_provider: 数据提供者（AkShareDataProvider 或 BaostockDataProvider）
            cache: Parquet缓存实例，默认创建新实例
        """
        self.provider = data_provider
        self.cache = cache or ParquetCache()
        self._logged_in = False
    
    def _ensure_login(self):
        """确保provider已登录并加载股票列表"""
        if not self._logged_in:
            if hasattr(self.provider, 'login'):
                self.provider.login()
            if hasattr(self.provider, 'load_stock_names'):
                self.provider.load_stock_names()
            self._logged_in = True
    
    def _cleanup(self):
        """清理资源"""
        if self._logged_in and hasattr(self.provider, 'logout'):
            self.provider.logout()
            self._logged_in = False
    
    def _get_incremental_date_range(self, symbol: str, requested_start: str, requested_end: str) -> tuple:
        """智能增量更新：计算实际需要下载的日期范围
        
        Args:
            symbol: 股票代码
            requested_start: 请求的开始日期
            requested_end: 请求的结束日期
            
        Returns:
            (需要下载, 实际开始日期, 实际结束日期)
        """
        import pandas as pd
        
        # 检查缓存中的数据
        cache_info = self.cache.get_cache_info(symbol)
        if not cache_info:
            # 无缓存，下载全部
            return (True, requested_start, requested_end)
        
        # 有缓存，检查是否需要增量更新
        req_start = pd.to_datetime(requested_start)
        req_end = pd.to_datetime(requested_end)
        cache_start = cache_info['start_date']
        cache_end = cache_info['end_date']
        
        # 情况1：缓存完全覆盖请求范围
        if cache_start <= req_start and cache_end >= req_end:
            logger.info(f"📦 {symbol} 缓存完全覆盖，无需下载")
            return (False, None, None)
        
        # 情况2：只需要下载新数据（缓存结束日期 < 请求结束日期）
        if cache_end < req_end:
            # 从缓存结束日期的下一天开始下载
            new_start = (cache_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            logger.info(f"📥 {symbol} 增量更新：{new_start} ~ {requested_end}")
            return (True, new_start, requested_end)
        
        # 情况3：需要下载历史数据（缓存开始日期 > 请求开始日期）
        if cache_start > req_start:
            # 下载到缓存开始日期的前一天
            new_end = (cache_start - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            logger.info(f"📥 {symbol} 历史补充：{requested_start} ~ {new_end}")
            return (True, requested_start, new_end)
        
        # 默认：下载全部
        return (True, requested_start, requested_end)
    
    def download_single(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str,
        force: bool = False,
        incremental: bool = True
    ) -> Dict[str, any]:
        """下载单只股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期 YYYYMMDD 或 YYYY-MM-DD
            force: 是否强制重新下载（忽略缓存）
            incremental: 是否启用增量更新（默认True）
            
        Returns:
            下载结果字典: {'success': bool, 'symbol': str, 'rows': int, 'message': str}
        """
        try:
            # 智能增量更新
            if not force and incremental:
                need_download, actual_start, actual_end = self._get_incremental_date_range(
                    symbol, start_date, end_date
                )
                
                if not need_download:
                    # 缓存完全满足需求
                    cached_df = self.cache.load(symbol, start_date, end_date)
                    return {
                        'success': True,
                        'symbol': symbol,
                        'rows': len(cached_df) if cached_df is not None else 0,
                        'message': '缓存已存在'
                    }
                
                # 使用增量范围
                start_date = actual_start
                end_date = actual_end
            
            # 确保provider ready
            self._ensure_login()
            
            # 下载数据（provider内部会自动缓存）
            logger.info(f"⬇️  开始下载 {symbol}: {start_date} ~ {end_date}")
            df = self.provider.get_stock_data(symbol, start_date, end_date)
            
            if df is None or df.empty:
                logger.warning(f"❌ {symbol} 下载失败：无数据")
                return {
                    'success': False,
                    'symbol': symbol,
                    'rows': 0,
                    'message': '无数据'
                }
            
            logger.info(f"✅ {symbol} 下载成功: {len(df)} 条")
            
            return {
                'success': True,
                'symbol': symbol,
                'rows': len(df),
                'message': '下载成功'
            }
            
        except Exception as e:
            logger.error(f"❌ {symbol} 下载异常: {e}")
            return {
                'success': False,
                'symbol': symbol,
                'rows': 0,
                'message': str(e)
            }
    
    def download_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        force: bool = False,
        incremental: bool = True,
        cleanup: bool = True
    ) -> Dict[str, any]:
        """批量下载股票数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调函数(message, current, total)
            force: 是否强制重新下载
            incremental: 是否启用增量更新
            cleanup: 是否在完成后清理资源（默认True，download_market会设为False）
            
        Returns:
            下载统计字典: {'total': int, 'success': int, 'failed': int, 'cached': int, 'results': List[dict]}
        """
        total = len(symbols)
        success_count = 0
        failed_count = 0
        cached_count = 0
        results = []
        
        logger.info(f"📦 开始批量下载 {total} 只股票")
        
        try:
            for i, symbol in enumerate(symbols):
                if progress_callback:
                    progress_callback(f"正在下载 {symbol}...", i + 1, total)
                
                result = self.download_single(symbol, start_date, end_date, force, incremental)
                results.append(result)
                
                if result['success']:
                    if result['message'] == '缓存已存在':
                        cached_count += 1
                    else:
                        success_count += 1
                else:
                    failed_count += 1
                
                # 控制下载速率，避免被限流（缓存命中不延迟）
                if i < total - 1 and result['message'] != '缓存已存在':
                    time.sleep(0.2)
        finally:
            # 只在需要时cleanup（避免download_market时过早关闭）
            if cleanup:
                self._cleanup()
        
        summary = {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'cached': cached_count,
            'results': results
        }
        
        logger.info(f"📊 批量下载完成: 成功{success_count}, 失败{failed_count}, 缓存{cached_count}")
        return summary
    
        def download_one(symbol):
            """下载单个股票的包装函数"""
            result = self.download_single(symbol, start_date, end_date, force, incremental)
            
            # 线程安全地更新进度
            with lock:
                completed[0] += 1
                if progress_callback:
                    progress_callback(f"已完成 {completed[0]}/{total}，正在下载 {symbol}...", 
                                    completed[0], total)
            
            return result
        
        try:
            # 确保provider已登录（在并行执行前）
            self._ensure_login()
            
            # 使用线程池并行下载
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_symbol = {executor.submit(download_one, symbol): symbol 
                                   for symbol in symbols}
                
                # 收集结果
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result['success']:
                            if result['message'] == '缓存已存在':
                                cached_count += 1
                            else:
                                success_count += 1
                        else:
                            failed_count += 1
                            
                    except Exception as e:
                        logger.error(f"下载 {symbol} 时发生异常: {e}")
                        results.append({
                            'success': False,
                            'symbol': symbol,
                            'rows': 0,
                            'message': f'异常: {str(e)}'
                        })
                        failed_count += 1
                        
        finally:
            # 只在需要时cleanup
            if cleanup:
                self._cleanup()
        
        summary = {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'cached': cached_count,
            'results': results
        }
        
        logger.info(f"📊 并行下载完成: 成功{success_count}, 失败{failed_count}, 缓存{cached_count}")
        return summary
    
    
    def download_market(
        self,
        market: str,
        start_date: str,
        end_date: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        force: bool = False,
        incremental: bool = True,
        max_stocks: Optional[int] = None
    ) -> Dict[str, any]:
        """下载整个市场的数据
        
        Args:
            market: 市场代码 'sh' 或 'sz'
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调
            force: 是否强制重新下载
            incremental: 是否启用增量更新
            max_stocks: 最大下载数量（用于测试）
            
        Returns:
            下载统计字典
        """
        try:
            # 确保provider ready
            self._ensure_login()
            
            # 获取股票列表
            if not hasattr(self.provider, 'get_stock_list'):
                logger.error("数据提供者不支持 get_stock_list 方法")
                return {'total': 0, 'success': 0, 'failed': 0, 'cached': 0, 'results': []}
            
            symbols = self.provider.get_stock_list(market)
            
            if max_stocks:
                symbols = symbols[:max_stocks]
            
            logger.info(f"📈 准备下载 {market.upper()} 市场 {len(symbols)} 只股票")
            
            # 调用batch下载，但不让它cleanup（我们在这里统一cleanup）
            summary = self.download_batch(
                symbols, start_date, end_date, 
                progress_callback, 
                force, 
                incremental,
                cleanup=False  # 关键：不让batch提前cleanup
            )
            
            return summary
        except Exception as e:
            logger.error(f"下载市场数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 0, 'cached': 0, 'results': []}
        finally:
            # 在这里统一cleanup
            self._cleanup()
