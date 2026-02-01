"""批量下载管理器 Implementation"""

import time
import logging
import pandas as pd
from typing import List, Callable, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from dquant2.core.data.storage import DataFileManager
from dquant2.core.data.providers.akshare_provider import AkShareProvider
from dquant2.core.data.providers.baostock_provider import BaostockProvider

logger = logging.getLogger(__name__)


class BatchDownloader:
    """批量下载管理器"""
    
    def __init__(self, max_workers: int = 4):
        """初始化
        
        Args:
            max_workers: 最大并发线程数
        """
        self.max_workers = max_workers
        self.file_manager = DataFileManager()
    
    def download_bulk(
        self,
        stock_list: List[str],
        period: str = '1d',
        start_date: str = None,
        end_date: str = None,
        fields: List[str] = None,
        dividend_type: str = 'qfq',
        time_range: str = 'all',
        data_provider: str = 'akshare',
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        check_interrupt: Optional[Callable[[], bool]] = None
    ):
        """批量下载股票数据
        
        Args:
            stock_list: 股票代码列表
            period: 周期类型
            start_date: 起始日期
            end_date: 结束日期
            fields: 字段列表
            dividend_type: 复权方式
            time_range: 时间段
            data_provider: 数据源名称
            progress_callback: 进度回调 (current, total, message)
            log_callback: 日志回调 (message)
            check_interrupt: 中断检查回调 (返回True表示中断)
        """
        # 初始化数据源
        if data_provider == 'akshare':
            provider = AkShareProvider()
        else:
            provider = BaostockProvider()
            
        total = len(stock_list)
        completed = 0
        failed = []
        
        if log_callback:
            log_callback(f"开始批量下载 {total} 只股票数据...")
            
        # 串行还是并行？
        # API通常有频率限制，Baostock单连接，AkShare也是接口调用
        # 保守起见，简单的串行或者低并发
        # 这里为了演示和控制，先使用串行，因为多线程请求可能导致IP封禁或接口报错
        # OSkhQuant实现似乎也是循环串行 (见 khQTTools.py:1130 time.sleep(1))
        
        # 既然OSkhQuant是循环，这里也先串行，避免并发问题
        
        for i, code in enumerate(stock_list):
            # 检查中断
            if check_interrupt and check_interrupt():
                if log_callback:
                    log_callback("下载任务被用户中断")
                return
            
            try:
                msg = f"正在下载 {code} ({i+1}/{total})"
                if log_callback:
                    log_callback(msg)
                
                # 获取数据
                df = provider.get_stock_data_multi_period(
                    stock_code=code,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    fields=fields,
                    dividend_type=dividend_type,
                    time_range=time_range
                )
                
                if not df.empty:
                    # 保存数据
                    success = self.file_manager.save_data(
                        df=df,
                        stock_code=code,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        time_range=time_range,
                        dividend_type=dividend_type
                    )
                    
                    if success:
                        if log_callback:
                            log_callback(f"成功保仔: {code}")
                    else:
                        failed.append(code)
                        if log_callback:
                            log_callback(f"保存失败: {code}")
                else:
                    if log_callback:
                        log_callback(f"无数据: {code}")
            
            except Exception as e:
                failed.append(code)
                logger.error(f"下载 {code} 失败: {e}")
                if log_callback:
                    log_callback(f"下载异常 {code}: {str(e)}")
            
            # 更新进度
            completed += 1
            if progress_callback:
                progress_callback(completed, total, f"已完成 {completed}/{total}")
            
            # 延时避免封禁
            time.sleep(0.5)
            
        if log_callback:
            log_callback(f"批量下载完成。成功: {total - len(failed)}, 失败: {len(failed)}")
            if failed:
                log_callback(f"失败列表: {failed}")
