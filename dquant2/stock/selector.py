"""股票选择器核心模块

实现无GUI依赖的选股逻辑
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Callable, Optional
import logging

from .config import StockSelectorConfig
from .data_provider import BaostockDataProvider
from .indicators import (
    calculate_macd,
    calculate_kdj,
    calculate_rsi,
    calculate_cci,
    calculate_bollinger_bands,
    calculate_wma,
    calculate_ema,
    calculate_sma,
    is_golden_cross
)

logger = logging.getLogger(__name__)


class StockSelector:
    """股票选择器
    
    根据技术指标、基本面、财务面等条件筛选股票
    """
    
    def __init__(self, config: StockSelectorConfig):
        """初始化股票选择器
        
        Args:
            config: 选股配置
        """
        self.config = config
        self.data_provider = BaostockDataProvider()
        self.progress_callback: Optional[Callable] = None
        self.stop_flag = False
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """设置进度回调函数
        
        Args:
            callback: 回调函数(message, current, total)
        """
        self.progress_callback = callback
    
    def _notify_progress(self, message: str, current: int = 0, total: int = 0):
        """通知进度
        
        Args:
            message: 进度消息
            current: 当前进度
            total: 总进度
        """
        if self.progress_callback:
            self.progress_callback(message, current, total)
        logger.info(message)
    
    def stop(self):
        """停止筛选"""
        self.stop_flag = True
        self._notify_progress("收到停止信号")
    
    def select_stocks(self) -> List[Dict]:
        """执行选股
        
        Returns:
            符合条件的股票列表,每个元素为字典包含股票信息
        """
        self.stop_flag = False
        qualified_stocks = []
        
        try:
            # 登录并加载股票列表
            self._notify_progress("正在连接证券数据中心...")
            if not self.data_provider.login():
                self._notify_progress("连接失败")
                return []
            
            if not self.data_provider.load_stock_names():
                self._notify_progress("加载股票信息失败")
                return []
            
            # 获取股票列表
            stock_list = self.data_provider.get_stock_list(self.config.market)
            if not stock_list:
                self._notify_progress("未找到股票")
                return []
            
            self._notify_progress(f"开始筛选{self.config.market.upper()}市场{len(stock_list)}只股票...")
            
            # 逐个检查股票
            for i, stock_code in enumerate(stock_list):
                if self.stop_flag:
                    self._notify_progress("筛选已停止")
                    break
                
                stock_name = self.data_provider.get_stock_name(stock_code)
                
                # 过滤异常股票（ST、停牌等）
                if not self._is_valid_stock(stock_code, stock_name):
                    continue
                
                self._notify_progress(
                    f"检查 {stock_name}({stock_code})",
                    i + 1,
                    len(stock_list)
                )
                
                # 检查条件
                result = self._check_stock(stock_code)
                if result:
                    qualified_stocks.append(result)
                    self._notify_progress(
                        f"✓ {stock_name}({stock_code}) 符合条件 (当前{len(qualified_stocks)}只)"
                    )
                
                # 达到数量上限
                if len(qualified_stocks) >= self.config.max_stocks:
                    self._notify_progress(f"已达到目标数量{self.config.max_stocks}只")
                    break
            
            self._notify_progress(f"筛选完成,共找到{len(qualified_stocks)}只股票")
            return qualified_stocks
            
        finally:
            self.data_provider.logout()
    
    def _is_valid_stock(self, stock_code: str, stock_name: str) -> bool:
        """过滤异常股票
        
        过滤掉ST股票、停牌股票、新股等不适合交易的股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            是否为有效股票
        """
        # 排除ST股票（包括ST、*ST、S*ST等）
        if 'ST' in stock_name.upper() or 'S*' in stock_name.upper():
            logger.debug(f"跳过ST股票: {stock_name}({stock_code})")
            return False
        
        # 排除退市整理期股票
        if '退' in stock_name:
            logger.debug(f"跳过退市整理期股票: {stock_name}({stock_code})")
            return False
        
        # 排除创业板和科创板（可选，这些板块波动较大）
        # 创业板: 300xxx, 科创板: 688xxx
        # if stock_code.startswith('300') or stock_code.startswith('688'):
        #     return False
        
        return True
    
    def _check_stock(self, stock_code: str) -> Optional[Dict]:
        """检查单只股票是否符合条件
        
        Args:
            stock_code: 股票代码
            
        Returns:
            如果符合返回股票信息字典,否则返回None
        """
        try:
            # 获取历史数据
            end_date = datetime.today().strftime("%Y-%m-%d")
            start_date = (datetime.today() - timedelta(days=self.config.lookback_days)).strftime("%Y-%m-%d")
            
            stock_df = self.data_provider.get_stock_data(stock_code, start_date, end_date)
            if stock_df.empty:
                return None
            
            # 计算技术指标
            stock_df = self._calculate_indicators(stock_df)
            if stock_df.empty:
                return None
            
            # 检查条件
            conditions_met, details = self._evaluate_conditions(stock_df)
            
            if conditions_met:
                stock_name = self.data_provider.get_stock_name(stock_code)
                last_close = float(stock_df['close'].iloc[-1])
                last_date = stock_df['date'].iloc[-1]
                
                return {
                    'code': stock_code,
                    'name': stock_name,
                    'price': last_close,
                    'date': last_date,
                    'conditions': details
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"检查股票{stock_code}时出错: {e}")
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标
        
        Args:
            df: 股票数据DataFrame
            
        Returns:
            添加了指标列的DataFrame
        """
        try:
            # 布林带
            upper_band, lower_band = calculate_bollinger_bands(
                df,
                period=self.config.bollinger_period,
                std_dev=self.config.bollinger_std_dev
            )
            df['upper_band'] = upper_band
            df['lower_band'] = lower_band
            
            # MACD
            df = calculate_macd(
                df,
                short_window=self.config.macd_short,
                long_window=self.config.macd_long,
                signal_window=self.config.macd_signal
            )
            
            # KDJ
            df = calculate_kdj(
                df,
                period=self.config.kdj_period,
                k_smooth=self.config.kdj_k_smooth,
                d_smooth=self.config.kdj_d_smooth
            )
            
            # RSI
            df = calculate_rsi(df, period=self.config.rsi_period)
            
            # CCI
            df = calculate_cci(df, period=self.config.cci_period)
            
            # 均线
            df['WMA'] = calculate_wma(df, period=self.config.ma_period)
            df['EMA'] = calculate_ema(df, period=self.config.ma_period)
            df['SMA'] = calculate_sma(df, period=self.config.ma_period)
            
            df = df.dropna()
            return df
            
        except Exception as e:
            logger.warning(f"计算指标时出错: {e}")
            return pd.DataFrame()
    
    def _evaluate_conditions(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """评估所有筛选条件
        
        Args:
            df: 包含指标的DataFrame
            
        Returns:
            (是否全部满足, 条件详情列表)
        """
        conditions = []
        details = []
        
        last_close = float(df['close'].iloc[-1])
        
        # 技术指标条件
        if self.config.use_macd:
            cond = is_golden_cross(df['MACD'], df['Signal_Line'])
            conditions.append(cond)
            details.append(f"MACD金叉: {'通过' if cond else '未通过'}")
        
        if self.config.use_kdj:
            k = float(df['K'].iloc[-1])
            d = float(df['D'].iloc[-1])
            j = float(df['J'].iloc[-1])
            cond = k > d and j < 30
            conditions.append(cond)
            details.append(f"KDJ可买入(K={k:.1f},D={d:.1f},J={j:.1f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_rsi:
            rsi = float(df['RSI'].iloc[-1])
            cond = rsi < 30
            conditions.append(cond)
            details.append(f"RSI超卖(RSI={rsi:.1f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_cci:
            cci = float(df['CCI'].iloc[-1])
            cond = cci < -100
            conditions.append(cond)
            details.append(f"CCI超卖(CCI={cci:.1f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_wma:
            wma = float(df['WMA'].iloc[-1])
            cond = last_close > wma
            conditions.append(cond)
            details.append(f"价格>WMA(价格={last_close:.2f},WMA={wma:.2f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_ema:
            ema = float(df['EMA'].iloc[-1])
            cond = last_close > ema
            conditions.append(cond)
            details.append(f"价格>EMA(价格={last_close:.2f},EMA={ema:.2f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_sma:
            sma = float(df['SMA'].iloc[-1])
            cond = last_close > sma
            conditions.append(cond)
            details.append(f"价格>SMA(价格={last_close:.2f},SMA={sma:.2f}): {'通过' if cond else '未通过'}")
        
        if self.config.use_volume and len(df) >= 5:
            avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
            last_volume = df['volume'].iloc[-1]
            cond = last_volume > self.config.volume_ratio_threshold * avg_volume
            conditions.append(cond)
            details.append(f"成交量放大: {'通过' if cond else '未通过'}")
        
        if self.config.use_price_range:
            cond = self.config.min_price <= last_close <= self.config.max_price
            conditions.append(cond)
            details.append(f"价格区间({self.config.min_price}-{self.config.max_price}): {'通过' if cond else '未通过'}")
        
        if self.config.use_boll:
            lower_band = float(df['lower_band'].iloc[-1])
            tolerance = 0.05
            cond = last_close <= lower_band * (1 + tolerance)
            conditions.append(cond)
            details.append(f"布林下轨: {'通过' if cond else '未通过'}")
        
        if self.config.use_turnover and 'turnover' in df.columns:
            turnover = float(df['turnover'].iloc[-1])
            cond = self.config.min_turnover < turnover < self.config.max_turnover
            conditions.append(cond)
            details.append(f"换手率({turnover:.2f}%): {'通过' if cond else '未通过'}")
        
        # 基本面指标条件（需要获取额外数据）
        if any([self.config.use_pe_ratio, self.config.use_pb_ratio, 
                self.config.use_roe, self.config.use_net_profit_margin]):
            fundamental_data = self._get_fundamental_data(df)
            
            if self.config.use_pe_ratio and fundamental_data.get('pe_ratio') is not None:
                pe = fundamental_data['pe_ratio']
                cond = pe < self.config.max_pe_ratio and pe > 0  # PE需要大于0（盈利）
                conditions.append(cond)
                details.append(f"市盈率(PE={pe:.1f}<{self.config.max_pe_ratio}): {'通过' if cond else '未通过'}")
            
            if self.config.use_pb_ratio and fundamental_data.get('pb_ratio') is not None:
                pb = fundamental_data['pb_ratio']
                cond = pb < self.config.max_pb_ratio and pb > 0
                conditions.append(cond)
                details.append(f"市净率(PB={pb:.1f}<{self.config.max_pb_ratio}): {'通过' if cond else '未通过'}")
            
            if self.config.use_roe and fundamental_data.get('roe') is not None:
                roe = fundamental_data['roe']
                cond = roe > self.config.min_roe
                conditions.append(cond)
                details.append(f"ROE({roe:.1f}%>{self.config.min_roe}%): {'通过' if cond else '未通过'}")
            
            if self.config.use_net_profit_margin and fundamental_data.get('net_profit_margin') is not None:
                npm = fundamental_data['net_profit_margin']
                cond = npm > self.config.min_net_profit_margin
                conditions.append(cond)
                details.append(f"净利率({npm:.1f}%>{self.config.min_net_profit_margin}%): {'通过' if cond else '未通过'}")
        
        # 如果没有启用任何条件,返回False
        if not conditions:
            return False, ["未启用任何筛选条件"]
        
        # 所有条件都满足才通过
        all_met = all(conditions)
        return all_met, details
    
    def _get_fundamental_data(self, df: pd.DataFrame) -> Dict:
        """获取基本面数据
        
        从数据框中提取或计算基本面指标
        注意：baostock的基本面数据可能需要额外API调用
        这里提供一个简化实现，实际可通过data_provider获取
        
        Returns:
            包含PE、PB、ROE等基本面数据的字典
        """
        result = {}
        
        # 如果数据框中包含这些列，直接使用
        if 'peTTM' in df.columns:
            try:
                result['pe_ratio'] = float(df['peTTM'].iloc[-1])
            except:
                pass
        
        if 'pbMRQ' in df.columns:
            try:
                result['pb_ratio'] = float(df['pbMRQ'].iloc[-1])
            except:
                pass
        
        if 'roeAvg' in df.columns:
            try:
                result['roe'] = float(df['roeAvg'].iloc[-1])
            except:
                pass
        
        if 'netProfitMargin' in df.columns:
            try:
                result['net_profit_margin'] = float(df['netProfitMargin'].iloc[-1])
            except:
                pass
        
        return result

