"""数据文件管理器

提供标准化的数据文件命名、解析和存储管理
"""

import os
import re
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataFileManager:
    """数据文件管理器
    
    文件命名规范: {股票代码}_{周期类型}_{起始日期}_{结束日期}_{时间段}_{复权方式}.csv
    示例: 000001.SZ_1d_20240101_20241231_all_qfq.csv
    """
    
    # 支持的周期类型
    PERIOD_TYPES = ['tick', '1m', '5m', '15m', '30m', '60m', '1d', '1w', '1M']
    
    # 支持的复权方式
    DIVIDEND_TYPES = {
        'none': '不复权',
        'qfq': '前复权',
        'hfq': '后复权',
        'front': '前复权',  # 兼容baostock
        'back': '后复权',   # 兼容baostock
    }
    
    def __init__(self, base_path: Optional[str] = None):
        """初始化数据文件管理器
        
        Args:
            base_path: 数据存储基础路径，默认为当前目录下的 stock_data
        """
        if base_path is None:
            self.base_path = Path.cwd() / 'stock_data'
        else:
            self.base_path = Path(base_path)
        
        # 创建子目录
        self.daily_dir = self.base_path / 'daily'
        self.minute_dir = self.base_path / 'minute'
        self.tick_dir = self.base_path / 'tick'
        
        logger.info(f"数据文件管理器初始化，基础路径: {self.base_path}")
    
    def generate_filename(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        time_range: str = 'all',
        dividend_type: str = 'none'
    ) -> str:
        """生成标准化文件名
        
        Args:
            stock_code: 股票代码，如 000001.SZ
            period: 周期类型，如 1d, 5m
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
            time_range: 时间段，'all' 或 'HH:MM-HH:MM'
            dividend_type: 复权方式
            
        Returns:
            标准化文件名
        """
        # 验证周期类型
        if period not in self.PERIOD_TYPES:
            logger.warning(f"不支持的周期类型: {period}")
        
        # 验证复权方式
        if dividend_type not in self.DIVIDEND_TYPES:
            logger.warning(f"不支持的复权方式: {dividend_type}")
        
        # 时间段格式化（替换 : 为 _）
        time_range_fmt = time_range.replace(':', '_')
        
        filename = f"{stock_code}_{period}_{start_date}_{end_date}_{time_range_fmt}_{dividend_type}.csv"
        return filename
    
    def parse_filename(self, filename: str) -> Optional[Dict]:
        """解析文件名获取参数
        
        Args:
            filename: 文件名
            
        Returns:
            解析结果字典，包含 code, period, start_date, end_date, time_range, dividend_type
            解析失败返回 None
        """
        # 去掉.csv后缀
        if filename.endswith('.csv'):
            filename = filename[:-4]
        
        # 正则匹配
        pattern = r'^(.+?)_(\w+)_(\d{8})_(\d{8})_(.+?)_(\w+)$'
        match = re.match(pattern, filename)
        
        if not match:
            logger.warning(f"文件名格式不符合规范: {filename}")
            return None
        
        code, period, start_date, end_date, time_range, dividend_type = match.groups()
        
        # 时间段格式还原（替换 _ 为 :）
        if time_range != 'all':
            time_range = time_range.replace('_', ':')
        
        return {
            'code': code,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'time_range': time_range,
            'dividend_type': dividend_type
        }
    
    def get_storage_dir(self, period: str) -> Path:
        """根据周期类型获取存储目录
        
        Args:
            period: 周期类型
            
        Returns:
            存储目录路径
        """
        if period == '1d' or period == '1w' or period == '1M':
            return self.daily_dir
        elif period == 'tick':
            return self.tick_dir
        else:
            return self.minute_dir
    
    def save_data(
        self,
        df: pd.DataFrame,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        time_range: str = 'all',
        dividend_type: str = 'none'
    ) -> bool:
        """保存数据到文件
        
        Args:
            df: 数据DataFrame
            stock_code: 股票代码
            period: 周期类型
            start_date: 起始日期
            end_date: 结束日期
            time_range: 时间段
            dividend_type: 复权方式
            
        Returns:
            是否保存成功
        """
        try:
            # 生成文件名
            filename = self.generate_filename(
                stock_code, period, start_date, end_date, time_range, dividend_type
            )
            
            # 获取存储目录
            storage_dir = self.get_storage_dir(period)
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # 完整路径
            file_path = storage_dir / filename
            
            # 保存CSV
            df.to_csv(file_path, index=False, encoding='utf-8')
            
            file_size = file_path.stat().st_size
            logger.info(f"数据已保存: {file_path} ({file_size / 1024:.2f} KB, {len(df)} 行)")
            return True
            
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
    
    def load_data(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        time_range: str = 'all',
        dividend_type: str = 'none'
    ) -> Optional[pd.DataFrame]:
        """加载数据文件
        
        Args:
            stock_code: 股票代码
            period: 周期类型
            start_date: 起始日期
            end_date: 结束日期
            time_range: 时间段
            dividend_type: 复权方式
            
        Returns:
            数据DataFrame，文件不存在返回None
        """
        try:
            # 生成文件名
            filename = self.generate_filename(
                stock_code, period, start_date, end_date, time_range, dividend_type
            )
            
            # 获取存储目录
            storage_dir = self.get_storage_dir(period)
            file_path = storage_dir / filename
            
            if not file_path.exists():
                logger.debug(f"文件不存在: {file_path}")
                return None
            
            # 读取CSV
            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"数据已加载: {file_path} ({len(df)} 行)")
            return df
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return None
    
    def list_files(
        self,
        period: Optional[str] = None,
        stock_code: Optional[str] = None
    ) -> List[Dict]:
        """列出数据文件
        
        Args:
            period: 周期类型筛选，None表示全部
            stock_code: 股票代码筛选，None表示全部
            
        Returns:
            文件信息列表
        """
        files = []
        
        # 确定搜索目录
        if period:
            search_dirs = [self.get_storage_dir(period)]
        else:
            search_dirs = [self.daily_dir, self.minute_dir, self.tick_dir]
        
        # 遍历目录
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            
            for file_path in search_dir.glob('*.csv'):
                parsed = self.parse_filename(file_path.name)
                if parsed is None:
                    continue
                
                # 代码筛选
                if stock_code and parsed['code'] != stock_code:
                    continue
                
                # 添加文件信息
                file_stat = file_path.stat()
                files.append({
                    'path': str(file_path),
                    'filename': file_path.name,
                    'size': file_stat.st_size,
                    'modified_time': datetime.fromtimestamp(file_stat.st_mtime),
                    **parsed
                })
        
        return files
    
    def delete_file(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        time_range: str = 'all',
        dividend_type: str = 'none'
    ) -> bool:
        """删除数据文件
        
        Args:
            stock_code: 股票代码
            period: 周期类型
            start_date: 起始日期
            end_date: 结束日期
            time_range: 时间段
            dividend_type: 复权方式
            
        Returns:
            是否删除成功
        """
        try:
            filename = self.generate_filename(
                stock_code, period, start_date, end_date, time_range, dividend_type
            )
            
            storage_dir = self.get_storage_dir(period)
            file_path = storage_dir / filename
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"文件已删除: {file_path}")
                return True
            else:
                logger.warning(f"文件不存在: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
