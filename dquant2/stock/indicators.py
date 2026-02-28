"""技术指标计算模块

从原stock_pool.py提取的指标计算函数,去除GUI依赖
"""

import pandas as pd
import numpy as np
from typing import Tuple


def is_golden_cross(series1: pd.Series, series2: pd.Series) -> bool:
    """判断是否出现金叉
    
    Args:
        series1: 快线
        series2: 慢线
        
    Returns:
        是否金叉
    """
    if len(series1) < 2 or len(series2) < 2:
        return False
    return series1.iloc[-2] <= series2.iloc[-2] and series1.iloc[-1] > series2.iloc[-1]


def calculate_bollinger_bands(
    data: pd.DataFrame, 
    period: int = 15, 
    std_dev: float = 1.5
) -> Tuple[pd.Series, pd.Series]:
    """计算布林带
    
    Args:
        data: 包含'close'列的DataFrame
        period: 周期
        std_dev: 标准差倍数
        
    Returns:
        上轨和下轨的Series
    """
    sma = data['close'].rolling(window=period).mean()
    std = data['close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, lower_band


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算RSI指标（标准 Wilder's Smoothing）

    使用 Wilder 平滑方法（EMA，alpha=1/period），与主流行情软件一致。

    Args:
        data: 包含'close'列的DataFrame
        period: 周期

    Returns:
        添加了'RSI'列的DataFrame
    """
    delta = data['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing: EMA with alpha = 1/period (com = period - 1)
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    data['RSI'] = rsi
    return data


def calculate_kdj(
    data: pd.DataFrame, 
    period: int = 9, 
    k_smooth: int = 3, 
    d_smooth: int = 3
) -> pd.DataFrame:
    """计算KDJ指标
    
    Args:
        data: 包含'high', 'low', 'close'列的DataFrame
        period: 周期
        k_smooth: K值平滑周期
        d_smooth: D值平滑周期
        
    Returns:
        添加了'K', 'D', 'J'列的DataFrame
    """
    low_min = data['low'].rolling(window=period).min()
    high_max = data['high'].rolling(window=period).max()
    denominator = (high_max - low_min).replace(0, float('nan'))
    rsv = (data['close'] - low_min) / denominator * 100
    # 标准 KDJ：用 EMA 平滑（Wilder 方式），com = smooth_period - 1
    data['K'] = rsv.ewm(com=k_smooth - 1, min_periods=1, adjust=False).mean()
    data['D'] = data['K'].ewm(com=d_smooth - 1, min_periods=1, adjust=False).mean()
    data['J'] = 3 * data['K'] - 2 * data['D']
    return data


def calculate_macd(
    data: pd.DataFrame, 
    short_window: int = 12, 
    long_window: int = 26, 
    signal_window: int = 9
) -> pd.DataFrame:
    """计算MACD指标
    
    Args:
        data: 包含'close'列的DataFrame
        short_window: 快线周期
        long_window: 慢线周期
        signal_window: 信号线周期
        
    Returns:
        添加了'MACD', 'Signal_Line', 'Histogram'列的DataFrame
    """
    short_ema = data['close'].ewm(span=short_window, adjust=False).mean()
    long_ema = data['close'].ewm(span=long_window, adjust=False).mean()
    data['MACD'] = short_ema - long_ema
    data['Signal_Line'] = data['MACD'].ewm(span=signal_window, adjust=False).mean()
    data['Histogram'] = data['MACD'] - data['Signal_Line']
    return data


def calculate_cci(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算CCI指标
    
    Args:
        data: 包含'high', 'low', 'close'列的DataFrame
        period: 周期
        
    Returns:
        添加了'CCI'列的DataFrame
    """
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    mean_deviation = (typical_price - typical_price.rolling(window=period).mean()).abs().rolling(window=period).mean()
    cci = (typical_price - typical_price.rolling(window=period).mean()) / (0.015 * mean_deviation)
    data['CCI'] = cci
    return data


def calculate_wma(data: pd.DataFrame, period: int = 5) -> pd.Series:
    """计算加权移动平均线(WMA)
    
    Args:
        data: 包含'close'列的DataFrame
        period: 周期
        
    Returns:
        WMA的Series
    """
    weights = np.arange(1, period + 1)
    wma = data['close'].rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
    return wma


def calculate_ema(data: pd.DataFrame, period: int = 5) -> pd.Series:
    """计算指数移动平均线(EMA)
    
    Args:
        data: 包含'close'列的DataFrame
        period: 周期
        
    Returns:
        EMA的Series
    """
    ema = data['close'].ewm(span=period, adjust=False).mean()
    return ema


def calculate_sma(data: pd.DataFrame, period: int = 5) -> pd.Series:
    """计算简单移动平均线(SMA)
    
    Args:
        data: 包含'close'列的DataFrame
        period: 周期
        
    Returns:
        SMA的Series
    """
    sma = data['close'].rolling(window=period).mean()
    return sma


def calculate_ma_slope(data: pd.DataFrame, period: int = 5) -> pd.Series:
    """计算均线斜率
    
    Args:
        data: 包含'close'列的DataFrame
        period: 周期
        
    Returns:
        斜率角度的Series
    """
    ma = data['close'].rolling(window=period).mean()
    slopes = []
    for i in range(period, len(ma)):
        x = np.array(range(period))
        y = ma[i - period:i].values
        slope = np.polyfit(x, y, 1)[0]
        angle = np.degrees(np.arctan(slope))
        slopes.append(angle)
    return pd.Series(slopes, index=ma.index[period:])
