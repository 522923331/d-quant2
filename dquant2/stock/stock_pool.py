import tkinter as tk
from tkinter import IntVar
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import baostock as bs
import threading
import time

# 定义全局变量控制面板显示状态
# 修改初始值为 True，让面板默认展开
indicator_panel_expanded = True

# 定义全局样式
BUTTON_FONT = ('Microsoft YaHei', 10)
LABEL_FONT = ('Microsoft YaHei', 10)
TITLE_FONT = ('Microsoft YaHei', 12, 'bold')
FRAME_BG = "#f5f5f5"
BUTTON_BG = "#2196F3"
BUTTON_FG = "white"
ACTIVE_BG = "#1976D2"
LOG_BG = "#333333"
LOG_FG = "#FFFFFF"

# Define stock_name_map globally
stock_name_map = {}


def init_baostock():
    """初始化 Baostock 连接和股票名称映射"""
    global stock_name_map
    try:
        # Login to Baostock
        lg = bs.login()
        if lg.error_code != '0':
            print(f"Baostock login failed, error code: {lg.error_code}, error message: {lg.error_msg}")
            return False
        
        # Populate stock_name_map
        rs = bs.query_stock_basic(code_name="")
        if rs.error_code == '0':
            while rs.next():
                row = rs.get_row_data()
                code = row[0].split('.')[1]
                name = row[1]
                stock_name_map[code] = name
            return True
        else:
            print(f"Failed to query stock basic info: {rs.error_code}, {rs.error_msg}")
            return False
    except Exception as e:
        print(f"Error initializing baostock: {e}")
        return False

# Define global variables
log_text = None
stop_flag = threading.Event()  # Flag to control thread stopping
current_thread = None
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试间隔时间（秒）

# Add new indicator variables
fundamental_vars = []
financial_vars = []


def is_golden_cross(series1, series2):
    """判断是否出现金叉"""
    if len(series1) < 2 or len(series2) < 2:
        return False
    return series1.iloc[-2] <= series2.iloc[-2] and series1.iloc[-1] > series2.iloc[-1]


def get_today_date():
    """获取今天的日期，格式为 YYYY-MM-DD"""
    today = datetime.today()
    return today.strftime("%Y-%m-%d")


def calculate_cci(data, period=14):
    """计算 CCI 指标"""
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    mean_deviation = (typical_price - typical_price.rolling(window=period).mean()).abs().rolling(window=period).mean()
    cci = (typical_price - typical_price.rolling(window=period).mean()) / (0.015 * mean_deviation)
    data['CCI'] = cci
    return data


def calculate_ma_slope(data, period=5):
    """计算均线斜率"""
    ma = data['close'].rolling(window=period).mean()
    slopes = []
    for i in range(period, len(ma)):
        x = np.array(range(period))
        y = ma[i - period:i].values
        slope = np.polyfit(x, y, 1)[0]
        angle = np.degrees(np.arctan(slope))
        slopes.append(angle)
    return pd.Series(slopes, index=ma.index[period:])


def insert_colored_text(text, color):
    """向日志文本框插入带颜色的文本"""
    log_text.insert(tk.END, text)
    log_text.tag_add("color_tag", f"end-1c linestart", "end-1c lineend")
    log_text.tag_config("color_tag", foreground=color)


def restart_query(market, var_list, stock_count_entry):
    """重新查询功能"""
    stop_query()
    log_text.delete(1.0, tk.END)
    on_button_click(market, var_list, stock_count_entry)


def calculate_bollinger_bands(data, period=15, std_dev=1.5):
    """计算布林带"""
    sma = data['close'].rolling(window=period).mean()
    std = data['close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, lower_band


def calculate_rsi(data, period=14):
    """计算 RSI"""
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    data['RSI'] = rsi
    return data


def calculate_kdj(data, period=9, k_smooth=3, d_smooth=3):
    """计算 KDJ"""
    low_min = data['low'].rolling(window=period).min()
    high_max = data['high'].rolling(window=period).max()
    rs_v = (data['close'] - low_min) / (high_max - low_min) * 100
    data['K'] = rs_v.rolling(window=k_smooth).mean()
    data['D'] = data['K'].rolling(window=d_smooth).mean()
    data['J'] = 3 * data['K'] - 2 * data['D']
    return data


def calculate_macd(data, short_window=12, long_window=26, signal_window=9):
    """计算 MACD"""
    short_ema = data['close'].ewm(span=short_window, adjust=False).mean()
    long_ema = data['close'].ewm(span=long_window, adjust=False).mean()
    data['MACD'] = short_ema - long_ema
    data['Signal_Line'] = data['MACD'].ewm(span=signal_window, adjust=False).mean()
    data['Histogram'] = data['MACD'] - data['Signal_Line']
    return data


def calculate_wma(data, period=5):
    """计算加权移动平均线 (WMA)"""
    weights = np.arange(1, period + 1)
    wma = data['close'].rolling(window=period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    return wma


def calculate_ema(data, period=5):
    """计算指数移动平均线 (EMA)"""
    ema = data['close'].ewm(span=period, adjust=False).mean()
    return ema


def calculate_sma(data, period=5):
    """计算简单移动平均线 (SMA)"""
    sma = data['close'].rolling(window=period).mean()
    return sma


def stop_query():
    """停止查询功能"""
    global stop_flag, current_thread
    stop_flag.set()  # 设置停止标志
    if current_thread and current_thread.is_alive():
        try:
            # 等待线程结束，设置足够长的超时时间
            current_thread.join(timeout=10)
            log_text.insert(tk.END, "线程已成功停止\n")
            if hasattr(current_thread, 'qualified_stocks'):
                root.after(0, update_log, current_thread.qualified_stocks, stock_name_map)
        except Exception as e:
            log_text.insert(tk.END, f"停止线程时出错: {str(e)}\n")
    else:
        log_text.insert(tk.END, "没有正在运行的线程\n")
    # 不清除标志，避免其他线程误操作
    # stop_flag.clear()


def get_stock_data(stock_code, today, start_date):
    """
    尝试从数据中心 获取股票数据
    :param stock_code: 股票代码
    :param today: 结束日期，格式为 YYYY-MM-DD
    :param start_date: 开始日期，格式为 YYYY-MM-DD
    :return: 股票数据 DataFrame
    """
    retries = 0
    while retries < MAX_RETRIES:
        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止获取股票数据\n")
            return pd.DataFrame()
        try:
            if stock_code.startswith('6'):
                baostock_code = f"sh.{stock_code}"
            else:
                baostock_code = f"sz.{stock_code}"
            # Remove unsupported fields
            rs = bs.query_history_k_data_plus(baostock_code,
                                              "date,open,high,low,close,volume,turn",
                                              start_date=start_date, end_date=today,
                                              frequency="d", adjustflag="2")
            if rs.error_code != '0':
                log_text.insert(tk.END,
                               f"查询股票 {stock_code} 数据时出错，错误码: {rs.error_code}，错误信息: {rs.error_msg}\n")
                if retries < MAX_RETRIES - 1:
                    log_text.insert(tk.END, f"即将在 {RETRY_DELAY} 秒后重试...\n")
                    for _ in range(RETRY_DELAY):
                        if stop_flag.is_set():
                            log_text.insert(tk.END, "收到停止信号，停止获取股票数据\n")
                            return pd.DataFrame()
                        time.sleep(1)
                retries += 1
                continue
            data_list = []
            while rs.next():
                if stop_flag.is_set():
                    log_text.insert(tk.END, "收到停止信号，停止获取股票数据\n")
                    return pd.DataFrame()
                data_list.append(rs.get_row_data())
            stock_df = pd.DataFrame(data_list, columns=rs.fields)
            if not stock_df.empty:
                stock_df.rename(columns={
                    'date': '日期',
                    'open': '开盘',
                    'high': '最高',
                    'low': '最低',
                    'close': '收盘',
                    'volume': '成交量',
                    'turn': '换手率'
                }, inplace=True)
                log_text.insert(tk.END, f"股票 {stock_code} 数据从数据中心 获取成功\n")
                return stock_df
            else:
                log_text.insert(tk.END, f"从数据中心 获取股票 {stock_code} 数据为空\n")
                break
        except Exception as e:
            log_text.insert(tk.END, f"从数据中心 获取股票 {stock_code} 数据时出错: {str(e)}\n")
            if retries < MAX_RETRIES - 1:
                log_text.insert(tk.END, f"即将在 {RETRY_DELAY} 秒后重试...\n")
                for _ in range(RETRY_DELAY):
                    if stop_flag.is_set():
                        log_text.insert(tk.END, "收到停止信号，停止获取股票数据\n")
                        return pd.DataFrame()
                    time.sleep(1)
            retries += 1
    return pd.DataFrame()


def get_fundamental_data(stock_code, date):
    """
    获取股票的基本面数据
    :param stock_code: 股票代码
    :param date: 日期，格式为 YYYY-MM-DD
    :return: 基本面数据 DataFrame
    """
    retries = 0
    while retries < MAX_RETRIES:
        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止获取基本面数据\n")
            return pd.DataFrame()
        try:
            if stock_code.startswith('6'):
                baostock_code = f"sh.{stock_code}"
            else:
                baostock_code = f"sz.{stock_code}"
            rs = bs.query_profit_data(code=baostock_code, year=date[:4], quarter=4)
            if rs.error_code != '0':
                log_text.insert(tk.END,
                               f"查询股票 {stock_code} 基本面数据时出错，错误码: {rs.error_code}，错误信息: {rs.error_msg}\n")
                if retries < MAX_RETRIES - 1:
                    log_text.insert(tk.END, f"即将在 {RETRY_DELAY} 秒后重试...\n")
                    for _ in range(RETRY_DELAY):
                        if stop_flag.is_set():
                            log_text.insert(tk.END, "收到停止信号，停止获取基本面数据\n")
                            return pd.DataFrame()
                        time.sleep(1)
                retries += 1
                continue
            data_list = []
            while rs.next():
                if stop_flag.is_set():
                    log_text.insert(tk.END, "收到停止信号，停止获取基本面数据\n")
                    return pd.DataFrame()
                data_list.append(rs.get_row_data())
            fundamental_df = pd.DataFrame(data_list, columns=rs.fields)
            if not fundamental_df.empty:
                log_text.insert(tk.END, f"股票 {stock_code} 基本面数据获取成功\n")
                return fundamental_df
            else:
                log_text.insert(tk.END, f"获取股票 {stock_code} 基本面数据为空\n")
                break
        except Exception as e:
            log_text.insert(tk.END, f"获取股票 {stock_code} 基本面数据时出错: {str(e)}\n")
            if retries < MAX_RETRIES - 1:
                log_text.insert(tk.END, f"即将在 {RETRY_DELAY} 秒后重试...\n")
                for _ in range(RETRY_DELAY):
                    if stop_flag.is_set():
                        log_text.insert(tk.END, "收到停止信号，停止获取基本面数据\n")
                        return pd.DataFrame()
                    time.sleep(1)
            retries += 1
    return pd.DataFrame()


def check_stock_conditions(stock_code, var_list, stock_name_map):
    """检查股票是否满足条件"""
    global log_text
    stock_name = stock_name_map.get(stock_code, stock_code)
    try:
        today = get_today_date()
        start_date = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=300)).strftime("%Y-%m-%d")
        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止检查股票条件\n")
            return False
        stock_df = get_stock_data(stock_code, today, start_date)
        if stock_df.empty:
            log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) 无有效数据\n")
            return False

        stock_df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '换手率': 'turnover'
        }, inplace=True)

        # Get fundamental data
        fundamental_df = get_fundamental_data(stock_code, today)
        if not fundamental_df.empty:
            # Merge fundamental data into stock_df
            stock_df = pd.merge(stock_df, fundamental_df, on='date', how='left')

        stock_df[['open', 'high', 'low', 'close', 'volume', 'turnover']] = stock_df[
            ['open', 'high', 'low', 'close', 'volume', 'turnover']].astype(float)

        stock_df = stock_df.dropna()

        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止计算指标\n")
            return False

        # 计算指标时添加 stop_flag 检查
        def calculate_with_stop_check(calculate_func, *args, **kwargs):
            if stop_flag.is_set():
                log_text.insert(tk.END, "收到停止信号，停止计算指标\n")
                return None
            return calculate_func(*args, **kwargs)

        upper_band, lower_band = calculate_with_stop_check(calculate_bollinger_bands, stock_df)
        if upper_band is None or lower_band is None:
            return False

        stock_df = calculate_with_stop_check(calculate_macd, stock_df)
        if stock_df is None:
            return False

        stock_df = calculate_with_stop_check(calculate_kdj, stock_df)
        if stock_df is None:
            return False

        stock_df = calculate_with_stop_check(calculate_rsi, stock_df)
        if stock_df is None:
            return False

        stock_df = calculate_with_stop_check(calculate_cci, stock_df)
        if stock_df is None:
            return False

        stock_df['WMA'] = calculate_with_stop_check(calculate_wma, stock_df)
        if stock_df['WMA'] is None:
            return False

        stock_df['EMA'] = calculate_with_stop_check(calculate_ema, stock_df)
        if stock_df['EMA'] is None:
            return False

        stock_df['SMA'] = calculate_with_stop_check(calculate_sma, stock_df)
        if stock_df['SMA'] is None:
            return False

        last_close = stock_df['close'].iloc[-1]

        conditions = []
        condition_results = []

        original_var_count = 11
        fundamental_var_count = 8  # Update to 8 because we added 4 new fundamental conditions
        financial_var_count = 8  # Update to 8 because we added 4 new financial conditions

        for i in range(original_var_count):
            if var_list[i].get():
                if i == 0:
                    cond1 = is_golden_cross(stock_df['MACD'], stock_df['Signal_Line'])
                    conditions.append(cond1)
                    condition_results.append(f"条件 1 (MACD 显示可买入): {'通过' if cond1 else '未通过'}")
                elif i == 1:
                    k = stock_df['K'].iloc[-1]
                    d = stock_df['D'].iloc[-1]
                    j = stock_df['J'].iloc[-1]
                    cond2 = k > d and j < 30
                    conditions.append(cond2)
                    condition_results.append(f"条件 2 (KDJ 显示可买入): {'通过' if cond2 else '未通过'}")
                elif i == 2:
                    cond3 = stock_df['RSI'].iloc[-1] < 30
                    conditions.append(cond3)
                    condition_results.append(f"条件 3 (RSI 显示可买入): {'通过' if cond3 else '未通过'}")
                elif i == 3:
                    if len(stock_df['CCI']) > 0:
                        cond4 = stock_df['CCI'].iloc[-1] < -100
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) CCI 数据不足，无法判断 CCI 条件\n")
                        cond4 = False
                    conditions.append(cond4)
                    condition_results.append(f"条件 4 (CCI 显示可买入): {'通过' if cond4 else '未通过'}")
                elif i == 4:
                    if len(stock_df['WMA']) > 0:
                        cond5 = stock_df['close'].iloc[-1] > stock_df['WMA'].iloc[-1]
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) WMA 数据不足，无法判断 WMA 条件\n")
                        cond5 = False
                    conditions.append(cond5)
                    condition_results.append(f"条件 5 (WMA 显示可买入): {'通过' if cond5 else '未通过'}")
                elif i == 5:
                    if len(stock_df['EMA']) > 0:
                        cond6 = stock_df['close'].iloc[-1] > stock_df['EMA'].iloc[-1]
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) EMA 数据不足，无法判断 EMA 条件\n")
                        cond6 = False
                    conditions.append(cond6)
                    condition_results.append(f"条件 6 (EMA 显示可买入): {'通过' if cond6 else '未通过'}")
                elif i == 6:
                    if len(stock_df['SMA']) > 0:
                        cond7 = stock_df['close'].iloc[-1] > stock_df['SMA'].iloc[-1]
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) SMA 数据不足，无法判断 SMA 条件\n")
                        cond7 = False
                    conditions.append(cond7)
                    condition_results.append(f"条件 7 (SMA 显示可买入): {'通过' if cond7 else '未通过'}")
                elif i == 7:
                    if len(stock_df['volume']) >= 5:
                        avg_volume = stock_df['volume'].rolling(window=5).mean().iloc[-1]
                        last_volume = stock_df['volume'].iloc[-1]
                        cond8 = last_volume > 1.5 * avg_volume
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) 成交量数据不足，无法判断成交量条件\n")
                        cond8 = False
                    conditions.append(cond8)
                    condition_results.append(f"条件 8 (成交量显示可买入): {'通过' if cond8 else '未通过'}")
                elif i == 8:
                    cond9 = 5 <= last_close <= 40
                    conditions.append(cond9)
                    condition_results.append(f"条件 9 (股价在 5 元 - 40 元之间): {'通过' if cond9 else '未通过'}")
                elif i == 9:
                    tolerance = 0.05
                    cond10 = last_close <= lower_band.iloc[-1] * (1 + tolerance)
                    conditions.append(cond10)
                    condition_results.append(f"条件 10 (BOLL 显示可买入): {'通过' if cond10 else '未通过'}")
                elif i == 10:
                    if 'turnover' in stock_df.columns:
                        last_turnover = stock_df['turnover'].iloc[-1]
                        cond11 = 3 < last_turnover < 12
                    else:
                        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) 无换手率数据，无法判断换手率条件\n")
                        cond11 = False
                    conditions.append(cond11)
                    condition_results.append(f"条件 11 (换手率显示可买入): {'通过' if cond11 else '未通过'}")

        # Fundamental indicators
        for i in range(original_var_count, original_var_count + fundamental_var_count):
            if var_list[i].get():
                if i == original_var_count:
                    cond_f1 = stock_df['peTTM'].iloc[-1] < 20
                    conditions.append(cond_f1)
                    condition_results.append(f"条件 F1 (滚动市盈率 < 20): {'通过' if cond_f1 else '未通过'}")
                elif i == original_var_count + 1:
                    cond_f2 = stock_df['pbMRQ'].iloc[-1] < 2
                    conditions.append(cond_f2)
                    condition_results.append(f"条件 F2 (市净率 < 2): {'通过' if cond_f2 else '未通过'}")
                elif i == original_var_count + 2:
                    cond_f3 = stock_df['roeAvg'].iloc[-1] > 15
                    conditions.append(cond_f3)
                    condition_results.append(f"条件 F3 (平均净资产收益率 > 15%): {'通过' if cond_f3 else '未通过'}")
                elif i == original_var_count + 3:
                    cond_f4 = stock_df['netProfitMargins'].iloc[-1] > 10
                    conditions.append(cond_f4)
                    condition_results.append(f"条件 F4 (净利率 > 10%): {'通过' if cond_f4 else '未通过'}")
                elif i == original_var_count + 4:
                    # Replace with actual condition 12 logic
                    # Note: These columns don't exist, so we'll skip them for now
                    cond_f5 = False
                    conditions.append(cond_f5)
                    condition_results.append(f"条件 F5 (条件 12): {'通过' if cond_f5 else '未通过'}")
                elif i == original_var_count + 5:
                    # Replace with actual condition 13 logic
                    cond_f6 = False
                    conditions.append(cond_f6)
                    condition_results.append(f"条件 F6 (条件 13): {'通过' if cond_f6 else '未通过'}")
                elif i == original_var_count + 6:
                    # Replace with actual condition 14 logic
                    cond_f7 = False
                    conditions.append(cond_f7)
                    condition_results.append(f"条件 F7 (条件 14): {'通过' if cond_f7 else '未通过'}")
                elif i == original_var_count + 7:
                    # Replace with actual condition 15 logic
                    cond_f8 = False
                    conditions.append(cond_f8)
                    condition_results.append(f"条件 F8 (条件 15): {'通过' if cond_f8 else '未通过'}")

        # Financial indicators
        for i in range(original_var_count + fundamental_var_count, original_var_count + fundamental_var_count + financial_var_count):
            if var_list[i].get():
                if i == original_var_count + fundamental_var_count:
                    cond_fin1 = stock_df['grossProfitRate'].iloc[-1] > 30
                    conditions.append(cond_fin1)
                    condition_results.append(f"条件 Fin1 (毛利率 > 30%): {'通过' if cond_fin1 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 1:
                    cond_fin2 = stock_df['operatingProfitRate'].iloc[-1] > 15
                    conditions.append(cond_fin2)
                    condition_results.append(f"条件 Fin2 (营业利润率 > 15%): {'通过' if cond_fin2 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 2:
                    cond_fin3 = stock_df['currentRatio'].iloc[-1] > 1.5
                    conditions.append(cond_fin3)
                    condition_results.append(f"条件 Fin3 (流动比率 > 1.5): {'通过' if cond_fin3 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 3:
                    cond_fin4 = stock_df['quickRatio'].iloc[-1] > 1
                    conditions.append(cond_fin4)
                    condition_results.append(f"条件 Fin4 (速动比率 > 1): {'通过' if cond_fin4 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 4:
                    # Replace with actual condition 16 logic
                    cond_fin5 = False
                    conditions.append(cond_fin5)
                    condition_results.append(f"条件 Fin5 (条件 16): {'通过' if cond_fin5 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 5:
                    # Replace with actual condition 17 logic
                    cond_fin6 = False
                    conditions.append(cond_fin6)
                    condition_results.append(f"条件 Fin6 (条件 17): {'通过' if cond_fin6 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 6:
                    # Replace with actual condition 18 logic
                    cond_fin7 = False
                    conditions.append(cond_fin7)
                    condition_results.append(f"条件 Fin7 (条件 18): {'通过' if cond_fin7 else '未通过'}")
                elif i == original_var_count + fundamental_var_count + 7:
                    # Replace with actual condition 19 logic
                    cond_fin8 = False
                    conditions.append(cond_fin8)
                    condition_results.append(f"条件 Fin8 (条件 19): {'通过' if cond_fin8 else '未通过'}")

        result = all(conditions) if conditions else True
        if result:
            insert_colored_text(f"股票 {stock_name}({stock_code}) 最新价格: {last_close} 筛选结果: {'通过'}\n", "red")
        else:
            log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) 最新价格: {last_close} 筛选结果: {'未通过'}\n")
        for res in condition_results:
            if "通过" in res:
                insert_colored_text(f"  {res}\n", "red")
            else:
                log_text.insert(tk.END, f"  {res}\n")
        log_text.see(tk.END)  # 自动滚动到最新日志
        return result
    except Exception as e:
        log_text.insert(tk.END, f"处理股票 {stock_name}({stock_code}) 时出错: {str(e)}\n")
        log_text.see(tk.END)
        return False


def get_stocks(market, var_list, stock_count, stock_name_map):
    """获取符合条件的股票"""
    all_stocks = get_all_stocks(market)
    qualified_stocks = []
    for stock_code in all_stocks:
        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止筛选股票\n")
            break
        if check_stock_conditions(stock_code, var_list, stock_name_map):
            qualified_stocks.append(stock_code)
        if len(qualified_stocks) >= stock_count:
            break
    return qualified_stocks


def update_log(stocks, stock_name_map):
    """更新日志文本框"""
    global log_text
    log_text.delete(1.0, tk.END)  # 清空日志
    if stocks:
        log_text.insert(tk.END, "符合条件的股票如下：\n")
        all_stock_data = []
        for stock in stocks:
            if stop_flag.is_set():
                log_text.insert(tk.END, "收到停止信号，停止更新日志\n")
                break
            stock_name = stock_name_map.get(stock, stock)
            today = get_today_date()
            start_date = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=300)).strftime("%Y-%m-%d")
            stock_df = get_stock_data(stock, today, start_date)
            if not stock_df.empty:
                # 保留原始中文列名，添加股票代码和名称列
                stock_df['股票代码'] = stock
                stock_df['股票名称'] = stock_name
                all_stock_data.append(stock_df)
                last_close = stock_df['收盘'].iloc[-1]
                insert_colored_text(f"{stock_name}({stock}) 最新价格: {last_close}\n", "red")
            else:
                log_text.insert(tk.END, f"{stock_name}({stock}) 无有效价格数据\n")

        if all_stock_data and not stop_flag.is_set():
            combined_df = pd.concat(all_stock_data, ignore_index=True)
            csv_filename = 'selected_stocks.csv'
            try:
                # 指定编码为 utf-8-sig
                combined_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
                log_text.insert(tk.END, f"筛选出的股票信息已导出到 {csv_filename}\n")
            except Exception as e:
                log_text.insert(tk.END, f"导出 CSV 文件时出错: {str(e)}\n")
    else:
        log_text.insert(tk.END, "未找到符合条件的股票。请尝试调整筛选条件或日期范围。\n")
    log_text.see(tk.END)


def get_all_stocks(market):
    """
    Get all stock codes from a specific market.
    :param market: Market type, 'sh' for Shanghai Stock Exchange, 'sz' for Shenzhen Stock Exchange
    :return: List of stock codes
    """
    all_stocks = []
    rs = bs.query_stock_basic(code_name="")
    if rs.error_code == '0':
        while rs.next():
            row = rs.get_row_data()
            code = row[0]
            if code.startswith(market):
                stock_code = code.split('.')[1]
                all_stocks.append(stock_code)
    return all_stocks


def threaded_get_stocks(market, var_list, stock_count_entry):
    """在后台线程中执行股票筛选操作"""
    global current_thread, stop_flag
    try:
        stock_count = int(stock_count_entry.get())
    except ValueError:
        root.after(0, log_text.insert, tk.END, "请输入有效的整数作为股票数量\n")
        return

    # Call the get_all_stocks function
    all_stocks = get_all_stocks(market)
    qualified_stocks = []
    current_thread = threading.current_thread()
    current_thread.qualified_stocks = qualified_stocks  # 将合格股票列表存储在线程对象中

    for index, stock_code in enumerate(all_stocks):
        if stop_flag.is_set():
            log_text.insert(tk.END, "收到停止信号，停止后台股票筛选\n")
            break
        # 每检查 10 只股票后，主动让出 CPU 时间片，提升 stop_flag 响应速度
        if index % 10 == 0:
            time.sleep(0.1)
        if check_stock_conditions(stock_code, var_list, stock_name_map):
            qualified_stocks.append(stock_code)
            current_thread.qualified_stocks = qualified_stocks  # 更新合格股票列表
        if len(qualified_stocks) >= stock_count:
            break
    root.after(0, update_log, qualified_stocks, stock_name_map)
    stop_flag.clear()


def on_button_click(market, var_list, stock_count_entry):
    """按钮点击事件处理函数"""
    global stop_flag, current_thread
    stop_query()
    stop_flag.clear()  # 确保标志位被清除
    log_text.insert(tk.END, "正在连接证券市场数据中心......\n")
    # 启动新线程执行耗时操作
    thread = threading.Thread(target=threaded_get_stocks, args=(market, var_list + fundamental_vars + financial_vars, stock_count_entry))
    current_thread = thread
    thread.start()


def select_all():
    for var in var_list + fundamental_vars + financial_vars:
        var.set(1)


def deselect_all():
    for var in var_list + fundamental_vars + financial_vars:
        var.set(0)


def get_trading_days(start_date, end_date):
    """
    获取指定日期范围内的所有交易日
    :param start_date: 开始日期，格式为 YYYY-MM-DD
    :param end_date: 结束日期，格式为 YYYY-MM-DD
    :return: 交易日列表
    """
    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    trading_days = []
    if rs.error_code == '0':
        while rs.next():
            row = rs.get_row_data()
            if row[1] == '1':  # 1 表示交易日
                trading_days.append(row[0])
    return trading_days


def check_stock_future_performance(stock_code, var_list, stock_name_map, days_entry, future_days_entry):
    global log_text
    stock_name = stock_name_map.get(stock_code, stock_code)
    today = get_today_date()
    try:
        days = int(days_entry.get())
    except ValueError:
        log_text.insert(tk.END, "请输入有效的整数作为查看时长天数\n")
        return
    try:
        future_days = int(future_days_entry.get())
    except ValueError:
        log_text.insert(tk.END, "请输入有效的整数作为未来天数\n")
        return

    # 获取交易日历
    trading_days = get_trading_days('2000-01-01', today)
    if not trading_days:
        log_text.insert(tk.END, "获取交易日历失败\n")
        return

    today_index = trading_days.index(today)
    start_index = max(0, today_index - days)
    start_date = trading_days[start_index]

    stock_df = get_stock_data(stock_code, today, start_date)

    if stock_df.empty:
        log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) 无有效数据\n")
        return

    stock_df.rename(columns={
        '日期': 'date',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume',
        '换手率': 'turnover',
        '滚动市盈率': 'peTTM',
        '市净率': 'pbMRQ',
        '平均净资产收益率': 'roeAvg',
        '净利率': 'netProfitMargins',
        '毛利率': 'grossProfitRate',
        '营业利润率': 'operatingProfitRate',
        '流动比率': 'currentRatio',
        '速动比率': 'quickRatio'
    }, inplace=True)
    stock_df[['open', 'high', 'low', 'close', 'volume', 'turnover', 'peTTM', 'pbMRQ', 'roeAvg', 'netProfitMargins', 'grossProfitRate', 'operatingProfitRate', 'currentRatio', 'quickRatio']] = stock_df[
        ['open', 'high', 'low', 'close', 'volume', 'turnover', 'peTTM', 'pbMRQ', 'roeAvg', 'netProfitMargins', 'grossProfitRate', 'operatingProfitRate', 'currentRatio', 'quickRatio']].astype(float)
    stock_df = stock_df.dropna()

    upper_band, lower_band = calculate_bollinger_bands(stock_df)
    stock_df = calculate_macd(stock_df)
    stock_df = calculate_kdj(stock_df)
    stock_df = calculate_rsi(stock_df)
    stock_df = calculate_cci(stock_df)
    stock_df['WMA'] = calculate_wma(stock_df)
    stock_df['EMA'] = calculate_ema(stock_df)
    stock_df['SMA'] = calculate_sma(stock_df)

    buy_count = 0
    not_buy_count = 0
    data_records = []

    original_var_count = 11
    fundamental_var_count = 4
    financial_var_count = 4

    for i in range(len(stock_df) - future_days):
        sub_df = stock_df.iloc[:i + 1]
        conditions = []

        for j in range(original_var_count):
            if var_list[j].get():
                if j == 0:
                    conditions.append(is_golden_cross(sub_df['MACD'], sub_df['Signal_Line']))
                elif j == 1:
                    k, d, j_val = sub_df['K'].iloc[-1], sub_df['D'].iloc[-1], sub_df['J'].iloc[-1]
                    conditions.append(k > d and j_val < 30)
                elif j == 2:
                    conditions.append(sub_df['RSI'].iloc[-1] < 30)
                elif j == 3:
                    conditions.append(len(sub_df['CCI']) > 0 and sub_df['CCI'].iloc[-1] < -100)
                elif j == 4:
                    conditions.append(len(sub_df['WMA']) > 0 and sub_df['close'].iloc[-1] > sub_df['WMA'].iloc[-1])
                elif j == 5:
                    conditions.append(len(sub_df['EMA']) > 0 and sub_df['close'].iloc[-1] > sub_df['EMA'].iloc[-1])
                elif j == 6:
                    conditions.append(len(sub_df['SMA']) > 0 and sub_df['close'].iloc[-1] > sub_df['SMA'].iloc[-1])
                elif j == 7:
                    if len(sub_df['volume']) >= 5:
                        avg_volume = sub_df['volume'].rolling(window=5).mean().iloc[-1]
                        last_volume = sub_df['volume'].iloc[-1]
                        conditions.append(last_volume > 1.5 * avg_volume)
                    else:
                        conditions.append(False)
                elif j == 8:
                    conditions.append(5 <= sub_df['close'].iloc[-1] <= 40)
                elif j == 9:
                    tolerance = 0.05
                    conditions.append(sub_df['close'].iloc[-1] <= lower_band.iloc[-1] * (1 + tolerance))
                elif j == 10:
                    conditions.append('turnover' in sub_df.columns and 3 < sub_df['turnover'].iloc[-1] < 12)

        # Fundamental indicators
        for j in range(original_var_count, original_var_count + fundamental_var_count):
            if var_list[j].get():
                if j == original_var_count:
                    conditions.append(sub_df['peTTM'].iloc[-1] < 20)
                elif j == original_var_count + 1:
                    conditions.append(sub_df['pbMRQ'].iloc[-1] < 2)
                elif j == original_var_count + 2:
                    conditions.append(sub_df['roeAvg'].iloc[-1] > 15)
                elif j == original_var_count + 3:
                    conditions.append(sub_df['netProfitMargins'].iloc[-1] > 10)

        # Financial indicators
        for j in range(original_var_count + fundamental_var_count, original_var_count + fundamental_var_count + financial_var_count):
            if var_list[j].get():
                if j == original_var_count + fundamental_var_count:
                    conditions.append(sub_df['grossProfitRate'].iloc[-1] > 30)
                elif j == original_var_count + fundamental_var_count + 1:
                    conditions.append(sub_df['operatingProfitRate'].iloc[-1] > 15)
                elif j == original_var_count + fundamental_var_count + 2:
                    conditions.append(sub_df['currentRatio'].iloc[-1] > 1.5)
                elif j == original_var_count + fundamental_var_count + 3:
                    conditions.append(sub_df['quickRatio'].iloc[-1] > 1)

        if all(conditions):
            current_date = sub_df['date'].iloc[-1]
            current_close = sub_df['close'].iloc[-1]
            future_close = stock_df['close'].iloc[i + future_days]
            increase = (future_close - current_close) / current_close * 100
            buy_decision = "可买入" if future_close > current_close else "不可买入"

            log_text.insert(tk.END,
                           f"日期: {current_date}, 当前收盘价: {current_close}, {future_days} 天后收盘价: {future_close}, 涨跌幅: {increase:.2f}%, 决策: {buy_decision}\n")

            if buy_decision == "可买入":
                buy_count += 1
            else:
                not_buy_count += 1

            data_records.append({
                '日期': current_date,
                '当前收盘价': current_close,
                f'{future_days}天后收盘价': future_close,
                '涨跌幅': increase,
                '决策': buy_decision
            })

    summary = "可入手" if buy_count > not_buy_count else "不可入手"
    log_text.insert(tk.END, f"股票 {stock_name}({stock_code}) {days} 天内总结: {summary}\n")

    data_records.append(
        {'日期': '总结', '当前收盘价': '', f'{future_days}天后收盘价': '', '涨跌幅': '', '决策': summary})

    df = pd.DataFrame(data_records)
    csv_filename = f'{stock_code}_analysis.csv'
    try:
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        log_text.insert(tk.END, f"分析数据已导出到 {csv_filename}\n")
    except Exception as e:
        log_text.insert(tk.END, f"导出 CSV 文件时出错: {str(e)}\n")


def threaded_check_stock_future_performance(stock_code, var_list, stock_name_map, days_entry, future_days_entry):
    """在后台线程中执行股票未来表现检查操作"""
    global current_thread

    def run_check():
        check_stock_future_performance(stock_code, var_list + fundamental_vars + financial_vars, stock_name_map, days_entry, future_days_entry)

    thread = threading.Thread(target=run_check)
    current_thread = thread
    thread.start()


def toggle_indicator_panel():
    global indicator_panel_expanded
    if indicator_panel_expanded:
        # Modify to use indicator_main_frame
        indicator_main_frame.grid_remove()
        toggle_indicators_button.config(text="▶ 指标筛选")
    else:
        # Modify to use indicator_main_frame
        indicator_main_frame.grid(row=3, column=0, sticky='nsew', padx=10, pady=10)
        toggle_indicators_button.config(text="▼ 指标筛选")
    indicator_panel_expanded = not indicator_panel_expanded


# 新增导出按钮功能函数
def export_stock_data():
    global log_text
    stock_code = stock_code_entry.get()
    try:
        days = int(days_entry.get())
    except ValueError:
        log_text.insert(tk.END, "请输入有效的整数作为查看时长天数\n")
        return

    today = get_today_date()
    # 获取交易日历
    trading_days = get_trading_days('2000-01-01', today)
    if not trading_days:
        log_text.insert(tk.END, "获取交易日历失败\n")
        return

    today_index = trading_days.index(today)
    start_index = max(0, today_index - days)
    start_date = trading_days[start_index]

    stock_df = get_stock_data(stock_code, today, start_date)

    if not stock_df.empty:
        csv_filename = f'{stock_code}_last_{days}_days.csv'
        try:
            stock_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            log_text.insert(tk.END, f"{stock_code} 过去 {days} 天的数据已导出到 {csv_filename}\n")
        except Exception as e:
            log_text.insert(tk.END, f"导出 {csv_filename} 时出错: {str(e)}\n")
    else:
        log_text.insert(tk.END, f"未获取到 {stock_code} 的有效数据，无法导出。\n")


root = tk.Tk()
root.title("量化选股工具V5.0 - by Davis")
root.geometry("1400x800")
root.configure(bg=FRAME_BG)

# Configure grid layout
root.columnconfigure(0, weight=3)
root.columnconfigure(1, weight=7)
root.rowconfigure(0, weight=1)

# 创建 Canvas 用于包含左侧面板和滚动条
left_canvas = tk.Canvas(root, bg=FRAME_BG)
left_canvas.grid(row=0, column=0, sticky='nsew')

# 创建滚动条
left_scrollbar = tk.Scrollbar(root, orient="vertical", command=left_canvas.yview)
left_scrollbar.grid(row=0, column=0, sticky='ens')

# 配置 Canvas 的滚动命令
left_canvas.configure(yscrollcommand=left_scrollbar.set)

# 创建一个 Frame 用于放置左侧面板内容
left_main_frame = tk.Frame(left_canvas, bg=FRAME_BG, padx=10)  # 增加 left_main_frame 的左边距
# 将 left_main_frame 放入 Canvas
left_canvas.create_window((0, 0), window=left_main_frame, anchor='nw', tags="left_main_frame")

# 左侧筛选条件区
left_frame = tk.Frame(left_main_frame, bg=FRAME_BG, bd=2, relief=tk.GROOVE, padx=15, pady=15)
left_frame.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=10)  # 左侧留间距，右侧不留间距
left_frame.columnconfigure(0, weight=1)

# 标题
title_label = tk.Label(left_frame, text="股票筛选条件", font=('Microsoft YaHei', 16, 'bold'), bg=FRAME_BG, fg="#2c3e50")
title_label.grid(row=0, column=0, pady=(10, 20), sticky='n')

# 股票数量输入组
stock_count_frame = tk.LabelFrame(left_frame, text="股票数量", font=TITLE_FONT, bg=FRAME_BG, fg="#2c3e50", padx=10,
                                   pady=10, bd=2, relief=tk.GROOVE)
stock_count_frame.grid(row=1, column=0, padx=10, pady=10, sticky='ew')
stock_count_frame.columnconfigure(0, weight=1)
stock_count_frame.columnconfigure(1, weight=2)

stock_count_label = tk.Label(stock_count_frame, text="需要得到的股票数量:", font=LABEL_FONT, bg=FRAME_BG, fg="#2c3e50")
stock_count_label.grid(row=0, column=0, padx=5, pady=8, sticky='w')
stock_count_entry = tk.Entry(stock_count_frame, font=LABEL_FONT, relief=tk.SOLID, bd=1)
stock_count_entry.insert(0, "10")  # Default value is 10
stock_count_entry.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 指标筛选隐藏按钮
toggle_indicators_button = tk.Button(left_frame, text="▼ 指标筛选", command=toggle_indicator_panel, font=BUTTON_FONT,
                                      bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
toggle_indicators_button.grid(row=2, column=0, padx=10, pady=10, sticky='ew')

# 指标复选框
indicator_frames = [
    ("趋势类指标", [
        "MACD 显示可买入",
        "KDJ 显示可买入",
        "RSI 显示可买入",
        "CCI 显示可买入"
    ]),
    ("均线类指标", [
        "WMA 显示可买入",
        "EMA 显示可买入",
        "SMA 显示可买入"
    ]),
    ("成交量和价格", [
        "成交量显示可买入",
        "股价在 5 元 - 40 元之间"
    ]),
    ("其他指标", [
        "BOLL 显示可买入",
        "换手率显示可买入"
    ]),
    ("基本面指标", [
        "滚动市盈率 < 20",
        "市净率 < 2",
        "平均净资产收益率 > 15%",
        "净利率 > 10%",
        "条件 12 (示例基本面条件)",
        "条件 13 (示例基本面条件)",
        "条件 14 (示例基本面条件)",
        "条件 15 (示例基本面条件)"
    ]),
    ("财务面指标", [
        "毛利率 > 30%",
        "营业利润率 > 15%",
        "流动比率 > 1.5",
        "速动比率 > 1",
        "条件 16 (示例财务条件)",
        "条件 17 (示例财务条件)",
        "条件 18 (示例财务条件)",
        "条件 19 (示例财务条件)"
    ])
]

var_list = []
# 创建一个 Frame 用于放置指标复选框
indicator_main_frame = tk.Frame(left_frame, bg=FRAME_BG)
indicator_main_frame.grid(row=3, column=0, sticky='nsew', padx=10, pady=10)
indicator_main_frame.columnconfigure(0, weight=1)
indicator_main_frame.columnconfigure(1, weight=1)

for i, (frame_title, indicators) in enumerate(indicator_frames):
    frame = tk.LabelFrame(indicator_main_frame, text=frame_title, font=TITLE_FONT, bg=FRAME_BG, fg="#2c3e50", padx=10,
                          pady=10, bd=2, relief=tk.GROOVE)
    frame.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky='ew')
    for j, label in enumerate(indicators):
        var = IntVar(value=1)
        if frame_title == "基本面指标":
            fundamental_vars.append(var)
        elif frame_title == "财务面指标":
            financial_vars.append(var)
        else:
            var_list.append(var)
        chk = tk.Checkbutton(frame, text=label, variable=var, font=LABEL_FONT, bg=FRAME_BG, fg="#2c3e50")
        chk.grid(row=j, column=0, padx=5, pady=5, sticky='w')

# 全选和全不选按钮组，移动到指标筛选区域内
select_button_frame = tk.LabelFrame(indicator_main_frame, text="全选/全不选", font=TITLE_FONT, bg=FRAME_BG,
                                     fg="#2c3e50", padx=10, pady=10, bd=2, relief=tk.GROOVE)
select_button_frame.grid(row=len(indicator_frames), column=0, columnspan=2, padx=10, pady=10, sticky='ew')
select_button_frame.columnconfigure(0, weight=1)
select_button_frame.columnconfigure(1, weight=1)

select_all_button = tk.Button(select_button_frame, text="全选", command=select_all, font=BUTTON_FONT,
                               bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
select_all_button.grid(row=0, column=0, padx=5, pady=8, sticky='ew')
deselect_all_button = tk.Button(select_button_frame, text="全不选", command=deselect_all, font=BUTTON_FONT,
                                 bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
deselect_all_button.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 市场筛选组
market_frame = tk.LabelFrame(left_frame, text="市场筛选", font=TITLE_FONT, bg=FRAME_BG, fg="#2c3e50", padx=10, pady=10,
                              bd=2, relief=tk.GROOVE)
market_frame.grid(row=4, column=0, padx=10, pady=10, sticky='ew')
market_frame.columnconfigure(0, weight=1)
market_frame.columnconfigure(1, weight=1)

sh_button = tk.Button(market_frame, text="上证股票筛选",
                      command=lambda: on_button_click('sh', var_list, stock_count_entry),
                      font=BUTTON_FONT, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
sh_button.grid(row=0, column=0, padx=5, pady=8, sticky='ew')
sz_button = tk.Button(market_frame, text="深证股票筛选",
                      command=lambda: on_button_click('sz', var_list, stock_count_entry),
                      font=BUTTON_FONT, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
sz_button.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 停止和重新筛选按钮组
control_button_frame = tk.LabelFrame(left_frame, text="控制操作", font=TITLE_FONT, bg=FRAME_BG, fg="#2c3e50", padx=10,
                                      pady=10, bd=2, relief=tk.GROOVE)
control_button_frame.grid(row=5, column=0, padx=10, pady=10, sticky='ew')
control_button_frame.columnconfigure(0, weight=1)
control_button_frame.columnconfigure(1, weight=1)

stop_button = tk.Button(control_button_frame, text="停止筛选", command=stop_query, font=BUTTON_FONT,
                         bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
stop_button.grid(row=0, column=0, padx=5, pady=8, sticky='ew')
restart_button = tk.Button(control_button_frame, text="重新筛选",
                           command=lambda: restart_query('sh', var_list, stock_count_entry), font=BUTTON_FONT,
                           bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
restart_button.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 股票代码输入和检查按钮组
stock_check_frame = tk.LabelFrame(left_frame, text="股票表现检查", font=TITLE_FONT, bg=FRAME_BG, fg="#2c3e50", padx=10,
                                   pady=10, bd=2, relief=tk.GROOVE)
stock_check_frame.grid(row=6, column=0, padx=10, pady=10, sticky='ew')
stock_check_frame.columnconfigure(0, weight=1)
stock_check_frame.columnconfigure(1, weight=2)

stock_code_label = tk.Label(stock_check_frame, text="股票代码:", font=LABEL_FONT, bg=FRAME_BG, fg="#2c3e50")
stock_code_label.grid(row=0, column=0, padx=5, pady=8, sticky='w')
stock_code_entry = tk.Entry(stock_check_frame, font=LABEL_FONT, relief=tk.SOLID, bd=1)
stock_code_entry.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 查看时长输入框
days_frame = tk.Frame(stock_check_frame, bg=FRAME_BG)
days_frame.grid(row=1, column=0, columnspan=2, pady=8, sticky='ew')
days_frame.columnconfigure(0, weight=1)
days_frame.columnconfigure(1, weight=2)

days_label = tk.Label(days_frame, text="查看股票表现的天数:", font=LABEL_FONT, bg=FRAME_BG, fg="#2c3e50")
days_label.grid(row=0, column=0, padx=5, pady=8, sticky='w')
days_entry = tk.Entry(days_frame, font=LABEL_FONT, relief=tk.SOLID, bd=1)
days_entry.insert(0, "180")  # 默认 180 天
days_entry.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

# 未来天数输入框
future_days_frame = tk.Frame(stock_check_frame, bg=FRAME_BG)
future_days_frame.grid(row=2, column=0, columnspan=2, pady=8, sticky='ew')
future_days_frame.columnconfigure(0, weight=1)
future_days_frame.columnconfigure(1, weight=2)

future_days_label = tk.Label(future_days_frame, text="符合筛选条件日后的天数:", font=LABEL_FONT, bg=FRAME_BG,
                              fg="#2c3e50")
future_days_label.grid(row=0, column=0, padx=5, pady=8, sticky='w')
future_days_entry = tk.Entry(future_days_frame, font=LABEL_FONT, relief=tk.SOLID, bd=1)
future_days_entry.insert(0, "5")  # 默认 5 天
future_days_entry.grid(row=0, column=1, padx=5, pady=8, sticky='ew')

check_button = tk.Button(stock_check_frame, text="检查股票表现",
                         command=lambda: threaded_check_stock_future_performance(
                             stock_code_entry.get(), var_list, stock_name_map, days_entry, future_days_entry),
                         font=BUTTON_FONT, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
check_button.grid(row=3, column=0, columnspan=2, pady=8, sticky='ew')

# 新增导出按钮
export_button = tk.Button(stock_check_frame, text="导出股票数据",
                           command=export_stock_data,
                           font=BUTTON_FONT, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=ACTIVE_BG, relief=tk.FLAT)
export_button.grid(row=4, column=0, columnspan=2, pady=8, sticky='ew')

# 右侧日志显示区
log_frame = tk.Frame(root, padx=20, pady=20, bg=FRAME_BG)
log_frame.grid(row=0, column=1, sticky='nsew', padx=20, pady=20)
log_text = tk.Text(log_frame, width=50, height=20, wrap=tk.WORD, bg=LOG_BG, fg=LOG_FG, font=('Microsoft YaHei', 10),
                   relief=tk.SOLID, bd=1)
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(log_frame, command=log_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
log_text.config(yscrollcommand=scrollbar.set)


# 绑定事件，当 left_main_frame 大小改变时，更新 Canvas 的滚动区域
def configure_canvas(event):
    left_canvas.configure(scrollregion=left_canvas.bbox("all"))
    left_canvas.itemconfigure("left_main_frame", width=left_canvas.winfo_width())


left_main_frame.bind("<Configure>", configure_canvas)
left_canvas.bind("<Configure>", configure_canvas)

# 调整 left_canvas 的列配置，让 Canvas 填充空间
root.columnconfigure(0, weight=3)

# 初始化 Baostock（在 GUI 显示后异步执行）
def init_after_gui():
    """在 GUI 显示后初始化 Baostock"""
    if log_text:
        log_text.insert(tk.END, "正在初始化 Baostock 连接...\n")
        log_text.see(tk.END)
    
    # 在后台线程中初始化，避免阻塞 GUI
    def init_thread():
        success = init_baostock()
        if log_text:
            if success:
                root.after(0, lambda: log_text.insert(tk.END, f"Baostock 初始化成功，已加载 {len(stock_name_map)} 只股票信息\n"))
            else:
                root.after(0, lambda: log_text.insert(tk.END, "Baostock 初始化失败，请检查网络连接\n"))
            root.after(0, lambda: log_text.see(tk.END))
    
    threading.Thread(target=init_thread, daemon=True).start()

# 延迟初始化，确保 GUI 先显示
root.after(100, init_after_gui)

# 显示窗口
root.update()
root.deiconify()

root.mainloop()

# Logout of Baostock
try:
    bs.logout()
except:
    pass
