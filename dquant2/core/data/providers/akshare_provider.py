"""AkShare 数据提供者

使用 AkShare 获取真实市场数据
"""

from datetime import datetime
from typing import List
import logging

import pandas as pd

from dquant2.core.data.interface import BaseDataProvider

logger = logging.getLogger(__name__)


class AkShareProvider(BaseDataProvider):
    """AkShare 数据提供者
    
    使用 AkShare 获取 A 股数据
    """
    
    def __init__(self):
        super().__init__(name="akshare")
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("请安装 akshare: pip install akshare")
            raise
    
    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = 'd'
    ) -> pd.DataFrame:
        """获取K线数据"""
        # 检查缓存
        cache_key = self._get_cache_key(symbol, start, end, freq)
        cached = self._use_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            # 转换日期格式
            start_date = pd.to_datetime(start, format='%Y%m%d').strftime('%Y%m%d')
            end_date = pd.to_datetime(end, format='%Y%m%d').strftime('%Y%m%d')
            
            # 调用 akshare
            if freq == 'd':
                # 日线数据
                df = self.ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"  # 前复权
                )
            else:
                # 其他频率暂不支持，使用日线
                logger.warning(f"AkShare 暂不支持 {freq} 频率，使用日线代替")
                df = self.ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
            })
            
            # 设置索引
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 只保留必需列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # 缓存
            self._set_cache(cache_key, df)
            
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败 {symbol}: {str(e)}")
            raise
    
    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情"""
        try:
            # 获取实时行情
            df = self.ak.stock_zh_a_spot_em()
            
            # 筛选指定股票
            df = df[df['代码'].isin(symbols)]
            
            # 标准化列名
            df = df.rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '成交量': 'volume',
                '成交额': 'amount',
            })
            
            return df[['symbol', 'name', 'price', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"获取实时行情失败: {str(e)}")
            raise
    
    def get_trading_dates(self, start: str, end: str) -> List[datetime]:
        """获取交易日历"""
        try:
            # 获取交易日历
            df = self.ak.tool_trade_date_hist_sina()
            
            # 筛选日期范围
            start_date = pd.to_datetime(start, format='%Y%m%d')
            end_date = pd.to_datetime(end, format='%Y%m%d')
            
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
            
            return df['trade_date'].tolist()
            
        except Exception as e:
            logger.warning(f"获取交易日历失败，使用工作日代替: {str(e)}")
            # 降级方案：使用工作日
            dates = pd.date_range(
                start=pd.to_datetime(start, format='%Y%m%d'),
                end=pd.to_datetime(end, format='%Y%m%d'),
                freq='B'
            )
            return dates.tolist()
    
    def validate_symbol(self, symbol: str) -> bool:
        """验证股票代码"""
        # A股代码格式：6位数字
        if not isinstance(symbol, str):
            return False
        if len(symbol) != 6:
            return False
        if not symbol.isdigit():
            return False
        return True
    def get_stock_data_multi_period(
        self,
        stock_code: str,
        period: str = '1d',
        start_date: str = None,
        end_date: str = None,
        fields: List[str] = None,
        dividend_type: str = 'qfq',
        time_range: str = 'all'
    ) -> pd.DataFrame:
        """获取多周期股票数据
        
        Args:
            stock_code: 股票代码
            period: 周期类型 ('1d', '5m', '60m' 等)
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            fields: 字段列表
            dividend_type: 复权方式 ('qfq', 'hfq', 'none')
            time_range: 时间段 ('all' 或 'HH:MM-HH:MM')
            
        Returns:
            DataFrame
        """
        try:
            # 默认字段
            if fields is None:
                fields = ['open', 'high', 'low', 'close', 'volume']
            
            # 处理股票代码：如果包含后缀（如.SZ, .SH），去掉
            if '.' in stock_code:
                stock_code_clean = stock_code.split('.')[0]
            else:
                stock_code_clean = stock_code
            
            # 日期处理
            if start_date:
                start_fmt = pd.to_datetime(start_date, format='%Y%m%d').strftime('%Y%m%d')
                start_date_dash = pd.to_datetime(start_date, format='%Y%m%d').strftime('%Y-%m-%d')
            if end_date:
                end_fmt = pd.to_datetime(end_date, format='%Y%m%d').strftime('%Y%m%d')
                end_date_dash = pd.to_datetime(end_date, format='%Y%m%d').strftime('%Y-%m-%d')
            
            df = pd.DataFrame()
            
            # 1. 日线数据
            if period == '1d':
                adjust = "" if dividend_type == 'none' else dividend_type
                df = self.ak.stock_zh_a_hist(
                    symbol=stock_code_clean,
                    start_date=start_fmt,
                    end_date=end_fmt,
                    adjust=adjust
                )
                
                if df.empty: 
                    return pd.DataFrame()
                    
                # 重命名列
                col_map = {
                    '日期': 'date',
                    '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close',
                    '成交量': 'volume', '成交额': 'amount',
                    '涨跌幅': 'pct_chg', '换手率': 'turnover'
                }
                df = df.rename(columns=col_map)
                
                # 统一日期格式
                df['date'] = pd.to_datetime(df['date'])
                
            # 2. 分钟数据 (使用 stock_zh_a_hist_min_em)
            elif period in ['1m', '5m', '15m', '30m', '60m']:
                period_map = {
                    '1m': '1', '5m': '5', '15m': '15', 
                    '30m': '30', '60m': '60'
                }
                ak_period = period_map.get(period, '5')
                adjust = "" if dividend_type == 'none' else dividend_type
                
                df = self.ak.stock_zh_a_hist_min_em(
                    symbol=stock_code_clean,
                    start_date=start_date_dash + " 09:30:00",
                    end_date=end_date_dash + " 15:00:00", 
                    period=ak_period,
                    adjust=adjust
                )
                
                if df.empty: 
                    return pd.DataFrame()

                # 重命名:  时间, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 最新价...
                col_map = {
                    '时间': 'time',
                    '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close',
                    '成交量': 'volume', '成交额': 'amount'
                }
                df = df.rename(columns=col_map)
                
                # 统一时间格式
                df['time'] = pd.to_datetime(df['time'])
                # 增加date列方便筛选
                df['date'] = df['time'].dt.strftime('%Y%m%d') # 保持字符串以便和输入比较? 
                # 或者转为datetime
                df['date'] = pd.to_datetime(df['date'])
                
                # 筛选日期范围 (API有时候返回范围较宽)
                s_dt = pd.to_datetime(start_date, format='%Y%m%d')
                e_dt = pd.to_datetime(end_date, format='%Y%m%d')
                df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]

                # 时间段筛选
                if time_range != 'all':
                    # 格式 HH:MM-HH:MM
                    t_start_str, t_end_str = time_range.split('-')
                    t_start = pd.to_datetime(t_start_str, format='%H:%M').time()
                    t_end = pd.to_datetime(t_end_str, format='%H:%M').time()
                    
                    df['time_obj'] = df['time'].dt.time
                    df = df[(df['time_obj'] >= t_start) & (df['time_obj'] <= t_end)]
                    df = df.drop(columns=['time_obj'])

            # 3. Tick数据 (不支持范围下载，通常只支持当日)
            elif period == 'tick':
                logger.warning("AkShare tick数据接口仅支持单日或有限历史，暂未完整实现")
                return pd.DataFrame()
                
            else:
                logger.warning(f"不支持的周期: {period}")
                return pd.DataFrame()
            
            # 过滤字段
            avail_cols = [c for c in fields if c in df.columns]
            # 必须包含 date/time
            if 'time' in df.columns and 'time' not in avail_cols:
                avail_cols.insert(0, 'time')
            if 'date' in df.columns and 'date' not in avail_cols:
                avail_cols.insert(0, 'date')
                
            df = df[avail_cols]
            return df
            
        except Exception as e:
            logger.error(f"获取多周期数据失败 {stock_code} {period}: {e}")
            return pd.DataFrame()
