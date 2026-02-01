"""股票列表管理器

提供股票列表的加载、更新、查询功能
支持预置列表和自定义列表
"""

import os
import csv
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StockListManager:
    """股票列表管理器"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """初始化股票列表管理器
        
        Args:
            data_dir: 股票列表数据目录，默认为模块下的data目录
        """
        if data_dir is None:
            # 默认使用模块下的data目录
            self.data_dir = Path(__file__).parent / 'data'
        else:
            self.data_dir = Path(data_dir)
        
        self._cache: Dict[str, List[Dict]] = {}
        logger.info(f"股票列表管理器初始化，数据目录: {self.data_dir}")
    
    def get_available_lists(self) -> List[str]:
        """获取所有可用的股票列表
        
        Returns:
            股票列表名称列表
        """
        if not self.data_dir.exists():
            logger.warning(f"股票列表目录不存在: {self.data_dir}")
            return []
        
        lists = []
        for file_path in self.data_dir.glob('*_股票列表.csv'):
            # 提取列表名称（去掉_股票列表.csv后缀）
            list_name = file_path.stem.replace('_股票列表', '')
            lists.append(list_name)
        
        logger.info(f"找到 {len(lists)} 个股票列表")
        return sorted(lists)
    
    def load_list(self, list_name: str) -> List[Dict]:
        """加载指定的股票列表
        
        Args:
            list_name: 列表名称，如 '沪深A股'、'创业板' 等
            
        Returns:
            股票信息列表，每项包含 {'code': str, 'name': str}
        """
        # 检查缓存
        if list_name in self._cache:
            logger.debug(f"从缓存加载股票列表: {list_name}")
            return self._cache[list_name]
        
        # 构建文件路径
        file_path = self.data_dir / f"{list_name}_股票列表.csv"
        
        if not file_path.exists():
            logger.error(f"股票列表文件不存在: {file_path}")
            return []
        
        try:
            stocks = []
            # 尝试多种编码
            encodings = ['utf-8', 'gb18030', 'gbk', 'gb2312']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if len(row) >= 2:
                                code = row[0].strip()
                                name = row[1].strip()
                                
                                # 验证代码格式（需要包含交易所后缀）
                                if '.' in code and code.endswith(('.SH', '.SZ', '.BJ')):
                                    stocks.append({
                                        'code': code,
                                        'name': name
                                    })
                    
                    # 成功读取，跳出编码尝试循环
                    break
                    
                except UnicodeDecodeError:
                    if encoding == encodings[-1]:
                        raise
                    continue
            
            # 缓存结果
            self._cache[list_name] = stocks
            logger.info(f"成功加载股票列表 '{list_name}': {len(stocks)} 只股票")
            return stocks
            
        except Exception as e:
            logger.error(f"加载股票列表 '{list_name}' 失败: {e}")
            return []
    
    def get_stock_codes(self, list_name: str) -> List[str]:
        """获取指定列表的股票代码
        
        Args:
            list_name: 列表名称
            
        Returns:
            股票代码列表
        """
        stocks = self.load_list(list_name)
        return [stock['code'] for stock in stocks]
    
    def get_stock_names(self, list_name: str) -> Dict[str, str]:
        """获取指定列表的股票代码到名称映射
        
        Args:
            list_name: 列表名称
            
        Returns:
            股票代码到名称的映射字典
        """
        stocks = self.load_list(list_name)
        return {stock['code']: stock['name'] for stock in stocks}
    
    def filter_by_codes(self, list_name: str, codes: List[str]) -> List[Dict]:
        """从列表中筛选指定代码的股票
        
        Args:
            list_name: 列表名称
            codes: 股票代码列表
            
        Returns:
            筛选后的股票信息列表
        """
        stocks = self.load_list(list_name)
        code_set = set(codes)
        return [stock for stock in stocks if stock['code'] in code_set]
    
    def create_custom_list(self, name: str, stocks: List[Dict]) -> bool:
        """创建自定义股票列表
        
        Args:
            name: 列表名称
            stocks: 股票信息列表，每项包含 {'code': str, 'name': str}
            
        Returns:
            是否创建成功
        """
        try:
            # 确保数据目录存在
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = self.data_dir / f"{name}_股票列表.csv"
            
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                for stock in stocks:
                    writer.writerow([stock['code'], stock['name']])
            
            # 更新缓存
            self._cache[name] = stocks
            logger.info(f"成功创建自定义股票列表 '{name}': {len(stocks)} 只股票")
            return True
            
        except Exception as e:
            logger.error(f"创建自定义股票列表 '{name}' 失败: {e}")
            return False
    
    def update_list_from_provider(self, list_name: str, data_provider: str = 'akshare') -> bool:
        """从数据源更新股票列表
        
        Args:
            list_name: 列表名称
            data_provider: 数据源，'akshare' 或 'baostock'
            
        Returns:
            是否更新成功
        """
        try:
            if data_provider == 'akshare':
                from dquant2.stock.data_provider import AkShareDataProvider
                provider = AkShareDataProvider()
            else:
                from dquant2.stock.data_provider import BaostockDataProvider
                provider = BaostockDataProvider()
            
            # 加载股票名称
            provider.login()
            provider.load_stock_names()
            
            # 根据列表名称获取股票
            stocks = []
            if list_name in ['沪深A股', '全部股票']:
                # 获取所有A股
                sh_codes = provider.get_stock_list('sh')
                sz_codes = provider.get_stock_list('sz')
                all_codes = sh_codes + sz_codes
                
                for code in all_codes:
                    name = provider.get_stock_name(code)
                    # 添加交易所后缀
                    if code.startswith('6'):
                        full_code = f"{code}.SH"
                    else:
                        full_code = f"{code}.SZ"
                    stocks.append({'code': full_code, 'name': name})
            
            elif list_name == '上证A股':
                codes = provider.get_stock_list('sh')
                for code in codes:
                    name = provider.get_stock_name(code)
                    stocks.append({'code': f"{code}.SH", 'name': name})
            
            elif list_name == '深证A股':
                codes = provider.get_stock_list('sz')
                for code in codes:
                    name = provider.get_stock_name(code)
                    stocks.append({'code': f"{code}.SZ", 'name': name})
            
            provider.logout()
            
            # 保存列表
            if stocks:
                return self.create_custom_list(list_name, stocks)
            else:
                logger.warning(f"未获取到 '{list_name}' 的股票数据")
                return False
                
        except Exception as e:
            logger.error(f"从 {data_provider} 更新股票列表 '{list_name}' 失败: {e}")
            return False
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        logger.info("股票列表缓存已清除")
