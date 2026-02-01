"""批量下载管理器

提供多线程/多进程批量下载功能，支持进度回调和中断
"""

__all__ = ['BatchDownloader']

from .batch_downloader import BatchDownloader
