"""股票数据提供者

支持从baostock等数据源获取股票数据
"""

import pandas as pd
import baostock as bs
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaostockDataProvider:
    """Baostock数据提供者"""
    
    def __init__(self):
        """初始化Baostock连接"""
        self.is_logged_in = False
        self.stock_name_map: Dict[str, str] = {}
    
    def login(self) -> bool:
        """登录Baostock
        
        Returns:
            是否登录成功
        """
        try:
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"Baostock登录失败: {lg.error_code}, {lg.error_msg}")
                return False
            
            self.is_logged_in = True
            logger.info("Baostock登录成功")
            return True
        except Exception as e:
            logger.error(f"Baostock登录异常: {e}")
            return False
    
    def logout(self):
        """登出Baostock"""
        try:
            if self.is_logged_in:
                bs.logout()
                self.is_logged_in = False
                logger.info("Baostock登出成功")
        except Exception as e:
            logger.error(f"Baostock登出异常: {e}")
    
    def load_stock_names(self) -> bool:
        """加载股票名称映射
        
        Returns:
            是否加载成功
        """
        try:
            if not self.is_logged_in:
                if not self.login():
                    return False
            
            rs = bs.query_stock_basic(code_name="")
            if rs.error_code != '0':
                logger.error(f"查询股票基本信息失败: {rs.error_code}, {rs.error_msg}")
                return False
            
            while rs.next():
                row = rs.get_row_data()
                code = row[0].split('.')[1]  # 去掉市场前缀
                name = row[1]
                self.stock_name_map[code] = name
            
            logger.info(f"加载{len(self.stock_name_map)}只股票信息")
            return True
        except Exception as e:
            logger.error(f"加载股票名称映射异常: {e}")
            return False
    
    def get_stock_list(self, market: str = 'sh') -> List[str]:
        """获取指定市场的股票列表
        
        Args:
            market: 市场代码, 'sh'或'sz'
            
        Returns:
            股票代码列表
        """
        try:
            if not self.is_logged_in:
                if not self.login():
                    return []
            
            all_stocks = []
            rs = bs.query_stock_basic(code_name="")
            if rs.error_code == '0':
                while rs.next():
                    row = rs.get_row_data()
                    code = row[0]
                    if code.startswith(market):
                        stock_code = code.split('.')[1]
                        all_stocks.append(stock_code)
            
            logger.info(f"获取{market}市场{len(all_stocks)}只股票")
            return all_stocks
        except Exception as e:
            logger.error(f"获取股票列表异常: {e}")
            return []
    
    def get_stock_data(
        self, 
        stock_code: str, 
        start_date: str, 
        end_date: str,
        retries: int = 3
    ) -> pd.DataFrame:
        """获取股票历史数据
        
        Args:
            stock_code: 股票代码(不含市场前缀)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            retries: 重试次数
            
        Returns:
            股票数据DataFrame
        """
        if not self.is_logged_in:
            if not self.login():
                return pd.DataFrame()
        
        # 添加市场前缀
        if stock_code.startswith('6'):
            baostock_code = f"sh.{stock_code}"
        else:
            baostock_code = f"sz.{stock_code}"
        
        for attempt in range(retries):
            try:
                rs = bs.query_history_k_data_plus(
                    baostock_code,
                    "date,open,high,low,close,volume,turn",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="2"  # 后复权
                )
                
                if rs.error_code != '0':
                    logger.warning(f"查询{stock_code}数据失败(尝试{attempt+1}/{retries}): {rs.error_msg}")
                    continue
                
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if not data_list:
                    logger.warning(f"股票{stock_code}无数据")
                    return pd.DataFrame()
                
                stock_df = pd.DataFrame(data_list, columns=rs.fields)
                
                # 列名转换
                stock_df.rename(columns={
                    'date': 'date',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume',
                    'turn': 'turnover'
                }, inplace=True)
                
                # 数据类型转换
                for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                    stock_df[col] = pd.to_numeric(stock_df[col], errors='coerce')
                
                stock_df = stock_df.dropna()
                
                # 关键：将date列转换为datetime并设置为索引
                stock_df['date'] = pd.to_datetime(stock_df['date'])
                stock_df.set_index('date', inplace=True)
                
                # 保存到缓存
                from dquant2.core.data.cache import ParquetCache
                cache = ParquetCache()
                cache.save(stock_code, stock_df)
                
                logger.debug(f"成功获取{stock_code}数据: {len(stock_df)}条")
                return stock_df
                
            except Exception as e:
                logger.warning(f"获取{stock_code}数据异常(尝试{attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    continue
        
        return pd.DataFrame()
    
    def get_fundamental_data(self, stock_code: str, year: str, quarter: int = 4) -> pd.DataFrame:
        """获取基本面数据
        
        Args:
            stock_code: 股票代码
            year: 年份
            quarter: 季度(1-4)
            
        Returns:
            基本面数据DataFrame
        """
        if not self.is_logged_in:
            if not self.login():
                return pd.DataFrame()
        
        # 添加市场前缀
        if stock_code.startswith('6'):
            baostock_code = f"sh.{stock_code}"
        else:
            baostock_code = f"sz.{stock_code}"
        
        try:
            rs = bs.query_profit_data(code=baostock_code, year=year, quarter=quarter)
            
            if rs.error_code != '0':
                logger.warning(f"查询{stock_code}基本面数据失败: {rs.error_msg}")
                return pd.DataFrame()
            
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            fundamental_df = pd.DataFrame(data_list, columns=rs.fields)
            return fundamental_df
            
        except Exception as e:
            logger.warning(f"获取{stock_code}基本面数据异常: {e}")
            return pd.DataFrame()
    
    
    def get_stock_basics(self) -> pd.DataFrame:
        """获取所有股票的基础信息（市值、成交量等）
        
        Note: Baostock 不直接提供总市值数据，这里仅返回代码和名称
        实际选股时，如果需要市值筛选，建议使用 AkShare
        """
        if not self.is_logged_in:
            if not self.login():
                return pd.DataFrame()
        
        try:
            # Baostock的query_stock_basic只包含基本上市信息
            rs = bs.query_stock_basic(code_name="")
            data_list = []
            while rs.next():
                row = rs.get_row_data()
                # code, code_name, ipoDate, outDate, type, status
                if row[5] == '1': # 在上市
                    code = row[0].split('.')[1]
                    name = row[1]
                    data_list.append({
                        'code': code,
                        'name': name,
                        'market_cap': None,  # Baostock暂不支持直接获取市值
                        'volume': None       # 也不支持获取当日成交量
                    })
            
            return pd.DataFrame(data_list)
        except Exception as e:
            logger.error(f"Baostock获取基础信息失败: {e}")
            return pd.DataFrame()

    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票名称
        """
        return self.stock_name_map.get(stock_code, stock_code)
    
    def __enter__(self):
        """上下文管理器进入"""
        self.login()
        self.load_stock_names()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.logout()


class AkShareDataProvider:
    """AkShare数据提供者
    
    使用AkShare作为选股模块的数据源，与回测模块保持一致
    """
    
    def __init__(self):
        """初始化AkShare"""
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("请安装 akshare: pip install akshare")
            raise
        
        self.stock_name_map: Dict[str, str] = {}
        self._cache: Dict[str, pd.DataFrame] = {}
    
    def login(self) -> bool:
        """登录（AkShare不需要登录，保持接口一致）"""
        logger.info("AkShare 初始化成功")
        return True
    
    def logout(self):
        """登出（AkShare不需要登出，保持接口一致）"""
        pass
    
    def load_stock_names(self) -> bool:
        """加载股票名称映射"""
        try:
            df = self.ak.stock_zh_a_spot_em()
            for _, row in df.iterrows():
                self.stock_name_map[row['代码']] = row['名称']
            logger.info(f"AkShare: 加载{len(self.stock_name_map)}只股票信息")
            return True
        except Exception as e:
            logger.error(f"AkShare加载股票名称异常: {e}")
            return False
    
    def get_stock_list(self, market: str = 'sh') -> List[str]:
        """获取指定市场的股票列表"""
        try:
            df = self.ak.stock_zh_a_spot_em()
            all_stocks = []
            
            for _, row in df.iterrows():
                code = row['代码']
                # 上证: 6开头, 深证: 0/3开头
                if market == 'sh' and code.startswith('6'):
                    all_stocks.append(code)
                elif market == 'sz' and (code.startswith('0') or code.startswith('3')):
                    all_stocks.append(code)
            
            logger.info(f"AkShare: 获取{market}市场{len(all_stocks)}只股票")
            return all_stocks
        except Exception as e:
            logger.error(f"AkShare获取股票列表异常: {e}")
            return []
    
    def get_stock_data(
        self, 
        stock_code: str, 
        start_date: str, 
        end_date: str,
        retries: int = 3
    ) -> pd.DataFrame:
        """获取股票历史数据"""
        # 检查Parquet缓存
        from dquant2.core.data.cache import ParquetCache
        cache = ParquetCache()
        
        # 尝试从缓存加载（只加载符合日期范围的数据）
        cached_df = cache.load(stock_code, start_date, end_date)
        if cached_df is not None:
            return cached_df
        
        # 内存缓存（仅作为二级缓存）
        cache_key = f"{stock_code}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        for attempt in range(retries):
            try:
                # 转换日期格式
                start_fmt = start_date.replace('-', '')
                end_fmt = end_date.replace('-', '')
                
                df = self.ak.stock_zh_a_hist(
                    symbol=stock_code,
                    start_date=start_fmt,
                    end_date=end_fmt,
                    adjust="qfq"
                )
                
                if df.empty:
                    return pd.DataFrame()
                
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '换手率': 'turnover',
                    '涨跌幅': 'pct_chg'
                })
                
                # 设置日期索引
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                # 保存到 Parquet 缓存
                cache.save(stock_code, df)
                
                # 内存缓存
                self._cache[cache_key] = df
                return df
                
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(f"AkShare获取{stock_code}数据失败，重试 {attempt+1}/{retries}: {e}")
                    import time
                    time.sleep(0.5)
                else:
                    logger.error(f"AkShare获取{stock_code}数据最终失败: {e}")
                    return pd.DataFrame()
        
        return pd.DataFrame()
    
    
    def get_stock_basics(self) -> pd.DataFrame:
        """获取所有股票的基础信息（市值、成交量等）"""
        try:
            df = self.ak.stock_zh_a_spot_em()
            # akshare返回列可能包含: 代码, 名称, 最新价, 涨跌幅, ..., 成交量, 成交额, ..., 总市值
            
            basics = []
            for _, row in df.iterrows():
                try:
                    # 总市值通常单位为元，需转为亿元
                    # 列名可能是 '总市值' 或 '总市值(元)'，需检查，这里假设为 '总市值'
                    market_cap_raw = row.get('总市值')
                    if market_cap_raw:
                         market_cap = float(market_cap_raw) / 100000000
                    else:
                        market_cap = 0
                except:
                    market_cap = 0
                
                try:
                    volume = float(row['成交量'])  # 手
                except:
                    volume = 0
                
                basics.append({
                    'code': str(row['代码']),
                    'name': str(row['名称']),
                    'market_cap': market_cap,
                    'volume': volume
                })
            
            return pd.DataFrame(basics)
        except Exception as e:
            logger.error(f"AkShare获取基础信息失败: {e}")
            return pd.DataFrame()

    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        return self.stock_name_map.get(stock_code, stock_code)
    
    def __enter__(self):
        """上下文管理器进入"""
        self.login()
        self.load_stock_names()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.logout()


def create_data_provider(provider_name: str = 'baostock'):
    """创建数据提供者工厂函数
    
    Args:
        provider_name: 数据源名称，'baostock' 或 'akshare'
        
    Returns:
        数据提供者实例
    """
    if provider_name.lower() == 'akshare':
        return AkShareDataProvider()
    else:
        return BaostockDataProvider()

