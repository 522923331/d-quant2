"""d-quant2 Web 界面

使用 Streamlit 创建交互式回测结果展示界面
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
import os
import threading
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dquant2 import BacktestEngine, BacktestConfig
from dquant2.stock import StockSelector, StockSelectorConfig
from dquant2.core.strategy.custom import get_custom_strategy_list, get_custom_strategy_params, reload_custom_strategies

def setup_page():
    # 页面配置
    st.set_page_config(
        page_title="d-quant2 量化系统",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 自定义CSS
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1f77b4;
            margin-bottom: 1rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            text-align: center;
        }
        .positive {
            color: #00c853;
            font-weight: bold;
        }
        .negative {
            color: #ff1744;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)


def create_equity_curve_chart(equity_curve):
    """创建权益曲线图"""
    df = pd.DataFrame(equity_curve)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=('权益曲线', '现金与持仓'),
        row_heights=[0.7, 0.3]
    )
    
    # 权益曲线
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['equity'],
            mode='lines',
            name='总权益',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ),
        row=1, col=1
    )
    
    # 现金和持仓
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['cash'],
            mode='lines',
            name='现金',
            line=dict(color='#2ca02c', width=1.5)
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['positions_value'],
            mode='lines',
            name='持仓市值',
            line=dict(color='#ff7f0e', width=1.5)
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        showlegend=True,
        hovermode='x unified',
        template='plotly_white'
    )
    
    fig.update_xaxes(title_text="日期", row=2, col=1)
    fig.update_yaxes(title_text="权益 (¥)", row=1, col=1)
    fig.update_yaxes(title_text="金额 (¥)", row=2, col=1)
    
    return fig

def create_drawdown_chart(equity_curve):
    """创建回撤曲线图"""
    df = pd.DataFrame(equity_curve)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 计算回撤
    cummax = df['equity'].cummax()
    drawdown = (df['equity'] - cummax) / cummax * 100
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=drawdown,
            mode='lines',
            name='回撤',
            line=dict(color='#d62728', width=2),
            fill='tozeroy',
            fillcolor='rgba(214, 39, 40, 0.3)'
        )
    )
    
    fig.update_layout(
        title='回撤曲线',
        xaxis_title='日期',
        yaxis_title='回撤 (%)',
        height=300,
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig

def create_trades_chart(trades):
    """创建交易记录图"""
    if not trades:
        return None
    
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 分离买卖
    buys = df[df['direction'] == 'BUY']
    sells = df[df['direction'] == 'SELL']
    
    fig = go.Figure()
    
    # 买入点
    fig.add_trace(
        go.Scatter(
            x=buys['timestamp'],
            y=buys['price'],
            mode='markers',
            name='买入',
            marker=dict(
                symbol='triangle-up',
                size=12,
                color='#2ca02c',
                line=dict(width=1, color='white')
            )
        )
    )
    
    # 卖出点
    fig.add_trace(
        go.Scatter(
            x=sells['timestamp'],
            y=sells['price'],
            mode='markers',
            name='卖出',
            marker=dict(
                symbol='triangle-down',
                size=12,
                color='#d62728',
                line=dict(width=1, color='white')
            )
        )
    )
    
    fig.update_layout(
        title='交易记录',
        xaxis_title='日期',
        yaxis_title='价格 (¥)',
        height=300,
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig

def stock_selection_page():
    """选股页面"""
    st.markdown('<h1 class="main-header">🔍 智能选股系统</h1>', unsafe_allow_html=True)
    
    # 侧边栏 - 选股配置
    with st.sidebar:
        st.header("⚙️ 选股配置")
        
        # 数据源设置
        st.subheader("数据源设置")
        stock_data_provider_map = {
            "本地数据库 (quant.db)": "local_db",
            "Baostock (推荐)": "baostock",
            "AkShare": "akshare"
        }
        
        # 从session state获取默认值（用于同步）
        default_idx = 0  # 默认Baostock
        if 'stock_data_provider' in st.session_state:
            current = st.session_state.stock_data_provider
            for i, (_, v) in enumerate(stock_data_provider_map.items()):
                if v == current:
                    default_idx = i
                    break
        
        stock_data_provider_display = st.selectbox(
            "数据源", 
            list(stock_data_provider_map.keys()),
            index=default_idx,
            help="建议选择与回测相同的数据源以保持数据一致性"
        )
        stock_data_provider = stock_data_provider_map[stock_data_provider_display]
        
        # 保存到session state
        st.session_state.stock_data_provider = stock_data_provider
        
        # 检查与回测模块数据源是否一致
        backtest_provider = st.session_state.get('backtest_data_provider', 'akshare')
        if backtest_provider != 'mock' and stock_data_provider != backtest_provider:
            st.warning(f"⚠️ 选股数据源({stock_data_provider})与回测数据源({backtest_provider})不一致")
            if st.button("🔄 同步到回测模块", key="sync_to_backtest"):
                st.session_state.backtest_data_provider = stock_data_provider
                st.success(f"✅ 已同步！回测模块现在也使用 {stock_data_provider}")
                st.rerun()
        
        # 基本设置
        st.subheader("基本设置")
        
        # 股票范围选择
        from dquant2.core.data.stock_lists import StockListManager
        sl_manager_sidebar = StockListManager()
        avail_lists = sl_manager_sidebar.get_available_lists()
        
        # 选项: 实时获取 + 现有列表
        realtime_lists = ["全市场"]
        scope_options = realtime_lists + avail_lists
        stock_scope = st.selectbox("股票范围", scope_options, index=0, help="选择'全市场'等选项将获取当日最新列表(自动缓存)；选择特定列表将在列表范围内筛选")
        
        # market = st.selectbox("市场", ["上证(sh)", "深证(sz)"]) # 已合并到股票范围
        market_code = 'all' # 默认all，具体由candidate_codes决定
        max_stocks = st.number_input("股票数量上限", min_value=1, max_value=100, value=10)
        
        # 技术指标
        st.subheader("技术指标")
        use_macd = st.checkbox("MACD金叉", value=False)
        use_kdj = st.checkbox("KDJ可买入", value=False)
        use_rsi = st.checkbox("RSI超卖(<30)", value=False)
        use_cci = st.checkbox("CCI超卖(<-100)", value=False)
        use_wma = st.checkbox("价格 > 加权均线", value=False)
        use_ema = st.checkbox("价格 > 指数均线", value=False)
        use_sma = st.checkbox("价格 > 简单均线", value=False)
        use_volume = st.checkbox("成交量放大", value=False)
        use_boll = st.checkbox("布林带下轨", value=False)
        
        # 价格和换手率
        st.subheader("价格与换手率")
        use_price_range = st.checkbox("价格区间", value=True)
        if use_price_range:
            col1, col2 = st.columns(2)
            with col1:
                min_price = st.number_input("最低价", value=5.0, step=1.0)
            with col2:
                max_price = st.number_input("最高价", value=40.0, step=1.0)
        else:
            min_price, max_price = 5.0, 40.0
        
        use_turnover = st.checkbox("换手率", value=True)
        if use_turnover:
            col1, col2 = st.columns(2)
            with col1:
                min_turnover = st.number_input("最小换手率%", value=3.0, step=0.5)
            with col2:
                max_turnover = st.number_input("最大换手率%", value=12.0, step=0.5)
        else:
            min_turnover, max_turnover = 3.0, 12.0
        
        # 市值与成交量
        st.subheader("市值与成交量")
        use_market_cap = st.checkbox("市值范围 (亿)", value=False)
        if use_market_cap:
            col1, col2 = st.columns(2)
            with col1:
                min_mcap = st.number_input("最小市值", value=0.0, step=10.0)
            with col2:
                max_mcap = st.number_input("最大市值", value=1000.0, step=100.0)
        else:
            min_mcap, max_mcap = 0.0, 1000.0
            
        use_volume_absolute = st.checkbox("成交量范围 (万手)", value=False)
        if use_volume_absolute:
            col1, col2 = st.columns(2)
            with col1:
                min_vol = st.number_input("最小成交量", value=1.0, step=1.0) # 1万手
            with col2:
                max_vol = st.number_input("最大成交量", value=1000.0, step=100.0) # 1000万手
            
            # 转换为手
            min_volume = min_vol * 10000
            max_volume = max_vol * 10000
        else:
            min_volume, max_volume = 10000.0, 10000000.0
        
        # 基本面指标(可选)
        with st.expander("📊 基本面指标(可选)"):
            use_pe_ratio = st.checkbox("市盈率 < 20", value=False)
            use_pb_ratio = st.checkbox("市净率 < 2", value=False)
            
            # LocalDB 不包含 roe 和 净利率 字段
            is_local = (stock_data_provider == 'local_db')
            roe_help = "本地数据库暂时未包含 ROE 数据" if is_local else ""
            npm_help = "本地数据库暂时未包含净利率数据" if is_local else ""
            
            use_roe = st.checkbox("ROE > 15%", value=False, disabled=is_local, help=roe_help)
            use_net_profit_margin = st.checkbox("净利率 > 10%", value=False, disabled=is_local, help=npm_help)
            
            if is_local and (use_roe or use_net_profit_margin):
                st.warning("所选的数据源不支持 ROE 或 净利率，这部分过滤将被忽略")
        
        # 开始选股按钮
        run_selection = st.button("🚀 开始选股", type="primary", width="stretch")
    
    # 主区域
    if run_selection:
        # 清除之前的结果
        if 'selection_results' in st.session_state:
            del st.session_state['selection_results']
        
        # 创建配置
        config = StockSelectorConfig(
            data_provider=stock_data_provider,
            market=market_code,
            max_stocks=max_stocks,
            use_macd=use_macd,
            use_kdj=use_kdj,
            use_rsi=use_rsi,
            use_cci=use_cci,
            use_wma=use_wma,
            use_ema=use_ema,
            use_sma=use_sma,
            use_volume=use_volume,
            use_boll=use_boll,
            use_price_range=use_price_range,
            min_price=min_price,
            max_price=max_price,
            use_turnover=use_turnover,
            min_turnover=min_turnover,
            max_turnover=max_turnover,
            # 新增参数
            use_market_cap=use_market_cap,
            min_market_cap=min_mcap,
            max_market_cap=max_mcap,
            use_volume_absolute=use_volume_absolute,
            min_volume=min_volume,
            max_volume=max_volume,
            # 基本面
            use_pe_ratio=use_pe_ratio,
            use_pb_ratio=use_pb_ratio,
            use_roe=use_roe,
            use_net_profit_margin=use_net_profit_margin
        )
        

        # 加载股票列表 logic
        with st.spinner(f"正在加载 '{stock_scope}' 列表..."):
            selected_scope_stocks = []
            
            if stock_scope in realtime_lists:
                # 使用每日缓存获取最新列表，通过传入用户选择的数据源
                selected_scope_stocks = sl_manager_sidebar.get_or_update_daily_list(stock_scope, data_provider=stock_data_provider)
            else:
                # 加载静态列表
                selected_scope_stocks = sl_manager_sidebar.load_list(stock_scope)
                
            if selected_scope_stocks:
                config.candidate_codes = [s['code'] for s in selected_scope_stocks]
                st.info(f"已加载 '{stock_scope}' 中的 {len(config.candidate_codes)} 只股票作为候选池")
            else:
                st.warning(f"加载列表 '{stock_scope}' 失败或列表为空")
        
        # 显示选股条件
        st.subheader("📋 筛选条件")
        conditions = config.get_enabled_conditions()
        if conditions:
            cols = st.columns(3)
            for i, cond in enumerate(conditions):
                cols[i % 3].markdown(f"✓ {cond}")
        else:
            st.warning("⚠️ 未启用任何筛选条件")
        
        # 执行选股
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        selector = StockSelector(config)
        
        # 定义进度回调
        def progress_callback(message, current, total):
            if total > 0:
                progress = min(current / total, 1.0)
                progress_bar.progress(progress)
            status_text.text(message)
        
        selector.set_progress_callback(progress_callback)
        
        with st.spinner("🔄 正在筛选股票..."):
            try:
                results = selector.select_stocks()
                st.session_state['selection_results'] = results
                st.session_state['selection_config'] = config.to_dict()
                progress_bar.progress(1.0)
                status_text.text("✅ 筛选完成!")
            except Exception as e:
                st.error(f"❌ 选股失败: {str(e)}")
                st.exception(e)
    
    # 显示结果
    if 'selection_results' in st.session_state:
        results = st.session_state['selection_results']
        
        st.subheader(f"📊 筛选结果 ({len(results)} 只股票)")
        
        if results:
            # 创建结果表格
            df_data = []
            for stock in results:
                df_data.append({
                    '股票代码': stock['code'],
                    '股票名称': stock['name'],
                    '最新价格': f"¥{stock['price']:.2f}",
                    '日期': stock['date']
                })
            
            results_df = pd.DataFrame(df_data)
            st.dataframe(results_df, width="stretch", hide_index=True)
            
            # 展开显示详细条件
            with st.expander("📋 查看详细筛选条件"):
                for stock in results:
                    st.markdown(f"**{stock['name']} ({stock['code']})**")
                    for cond in stock['conditions']:
                        if '通过' in cond:
                            st.markdown(f"- ✅ {cond}")
                        else:
                            st.markdown(f"- ❌ {cond}")
                    st.divider()
            
            # 导出功能
            st.subheader("💾 导出结果")
            col1, col2 = st.columns(2)
            
            with col1:
                csv = results_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载选股结果 (CSV)",
                    data=csv,
                    file_name=f"selected_stocks_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("🔄 传入批量回测"):
                    # 保存到session state供联动页面使用
                    st.session_state.selected_stocks = results
                    st.success(f"✅ 已将 {len(results)} 只股票传入批量回测！请切换到'选股回测联动'页面")
                    
            # 保存为自定义列表
            st.divider()
            with st.expander("💾 保存为自定义股票列表", expanded=True):
                 col_s1, col_s2 = st.columns([3, 1])
                 with col_s1:
                     new_list_name = st.text_input("列表名称", placeholder="例如: 优质成长股_20250201")
                 with col_s2:
                     save_btn = st.button("保存列表", width="stretch")
                     
                 if save_btn and new_list_name:
                     try:
                         # 提取代码和名称
                         stock_items = [{'code': r['code'], 'name': r['name']} for r in results]
                         sl_manager_sidebar.create_custom_list(new_list_name, stock_items)
                         st.success(f"✅ 已成功保存列表: {new_list_name} ({len(stock_items)}只股票)")
                     except Exception as e:
                         st.error(f"保存失败: {str(e)}")
        else:
            st.info("未找到符合条件的股票,请尝试调整筛选条件")
    else:
        # 初始提示
        st.info("👈 请在左侧设置选股条件,然后点击「开始选股」按钮")
        
        st.markdown("""
        ### 🎯 使用说明
        
        1. **选择范围**: 选择"全市场"或特定板块/指数
        2. **设置数量**: 限制筛选股票的数量
        3. **勾选指标**: 选择要使用的技术指标
        4. **设置参数**: 配置价格区间、换手率等
        5. **开始选股**: 点击按钮开始筛选
        6. **查看结果**: 分析筛选出的股票
        7. **导出数据**: 下载选股结果
        
        ### ✨ 特点
        
        - 🔍 **多维度筛选** - 技术指标 + 基本面 + 财务指标
        - 🎨 **灵活配置** - 自由组合筛选条件
        - 📊 **实时进度** - 显示筛选进度和当前状态
        - 💾 **结果导出** - 支持CSV格式导出
        """)


def backtest_page():
    """回测页面 - 原main函数内容"""
    st.markdown('<h1 class="main-header">📈 量化回测系统</h1>', unsafe_allow_html=True)
    
    # 侧边栏 - 回测配置
    with st.sidebar:
        st.header("⚙️ 回测配置")
        
        # 快速配置预设
        preset = st.selectbox(
            "快速配置",
            ["自定义", "稳健型", "均衡型", "进取型"],
            help="选择预设配置快速开始，或选择'自定义'手动调整参数"
        )
        
        # 根据预设设置默认值
        presets = {
            "稳健型": {"fast": 10, "slow": 30, "ratio": 0.15, "stop_loss": 0.03, "take_profit": 0.10},
            "均衡型": {"fast": 5, "slow": 20, "ratio": 0.25, "stop_loss": 0.05, "take_profit": 0.15},
            "进取型": {"fast": 3, "slow": 10, "ratio": 0.40, "stop_loss": 0.08, "take_profit": 0.25},
            "自定义": {"fast": 5, "slow": 20, "ratio": 0.20, "stop_loss": 0.05, "take_profit": 0.15}
        }
        current_preset = presets[preset]
        
        # 基本参数
        st.subheader("基本设置")
        symbol = st.text_input("股票代码", "000001")
        
        # 使用日期选择器替代文本输入
        from datetime import date, datetime, timedelta
        
        # 定义日期回调
        def update_dates():
            preset = st.session_state.date_range_preset
            today = date.today()
            if preset == "近1年":
                st.session_state.start_date = today - timedelta(days=365)
                st.session_state.end_date = today
            elif preset == "近3年":
                st.session_state.start_date = today - timedelta(days=365*3)
                st.session_state.end_date = today
            elif preset == "近5年":
                st.session_state.start_date = today - timedelta(days=365*5)
                st.session_state.end_date = today
            elif preset == "今年以来":
                st.session_state.start_date = date(today.year, 1, 1)
                st.session_state.end_date = today
        
        # 初始化日期session state
        if 'start_date' not in st.session_state:
            st.session_state.start_date = date(2020, 1, 1)
        if 'end_date' not in st.session_state:
            st.session_state.end_date = date(2023, 12, 31)

        # 日期范围预设
        st.selectbox(
            "时间范围预设",
            ["自定义", "近1年", "近3年", "近5年", "今年以来"],
            key="date_range_preset",
            on_change=update_dates,
            help="选择预设时间段会自动更新下方的开始和结束日期"
        )

        col1, col2 = st.columns(2)
        with col1:
            start_date_input = st.date_input(
                "开始日期",
                value=st.session_state.start_date,
                min_value=date(2010, 1, 1),
                max_value=date.today(),
                key="start_date"
            )
        with col2:
            end_date_input = st.date_input(
                "结束日期",
                value=st.session_state.end_date,
                min_value=date(2010, 1, 1),
                max_value=date.today(),
                key="end_date"
            )
        
        # 转换日期格式为 YYYYMMDD
        start_date = start_date_input.strftime("%Y%m%d")
        end_date = end_date_input.strftime("%Y%m%d")
        
        initial_cash = st.number_input("初始资金 (¥)", min_value=10000, value=1000000, step=10000)
        
        # 数据源
        st.subheader("数据设置")
        
        # 数据源映射：中文显示 -> 英文value
        data_provider_map = {
            "本地数据库 (quant.db)": "local_db",
            "模拟数据": "mock",
            "AkShare (真实数据)": "akshare",
            "Baostock (真实数据)": "baostock"
        }
        
        # 从session state获取默认值（用于同步）
        default_idx = 1  # 默认AkShare
        if 'backtest_data_provider' in st.session_state:
            current = st.session_state.backtest_data_provider
            for i, (_, v) in enumerate(data_provider_map.items()):
                if v == current:
                    default_idx = i
                    break
        
        data_provider_display = st.selectbox("数据源", list(data_provider_map.keys()), index=default_idx)
        data_provider = data_provider_map[data_provider_display]
        
        # 保存到session state
        st.session_state.backtest_data_provider = data_provider
        
        # 检查与选股模块数据源是否一致
        stock_provider = st.session_state.get('stock_data_provider', 'baostock')
        if data_provider != 'mock' and data_provider != stock_provider:
            st.warning(f"⚠️ 回测数据源({data_provider})与选股数据源({stock_provider})不一致")
            if st.button("🔄 同步到选股模块", key="sync_to_stock"):
                st.session_state.stock_data_provider = data_provider
                st.success(f"✅ 已同步！选股模块现在也使用 {data_provider}")
                st.rerun()
        
        # 策略设置
        st.subheader("策略设置")
        
        # 内置策略映射
        builtin_strategy_map = {
            "双均线交叉": "ma_cross",
            "RSI策略": "rsi",
            "MACD策略": "macd",
            "布林带策略": "bollinger",
            "网格交易策略": "grid_trading",
            "动量策略": "momentum",
            "均值回归策略": "mean_reversion"
        }
        
        # 加载自定义策略
        custom_strategies = get_custom_strategy_list()
        custom_strategy_map = {
            f"🔧 {s['display_name']}": s['name'] 
            for s in custom_strategies
        }
        
        # 合并策略列表
        all_strategy_map = {**builtin_strategy_map, **custom_strategy_map}
        
        # 刷新自定义策略按钮
        col_strat1, col_strat2 = st.columns([3, 1])
        with col_strat1:
            strategy_display = st.selectbox("策略", list(all_strategy_map.keys()))
        with col_strat2:
            if st.button("🔄", help="刷新自定义策略列表"):
                reload_custom_strategies()
                st.rerun()
        
        strategy_name = all_strategy_map[strategy_display]
        
        # 检查是否为自定义策略
        is_custom_strategy = strategy_name in [s['name'] for s in custom_strategies]
        
        # 根据策略显示不同参数
        if strategy_name == "ma_cross":
            fast_period = st.slider("快线周期", 3, 30, current_preset["fast"])
            slow_period = st.slider("慢线周期", 10, 60, current_preset["slow"])
            strategy_params = {
                'fast_period': fast_period,
                'slow_period': slow_period
            }
        elif strategy_name == "rsi":
            rsi_period = st.slider("RSI周期", 7, 21, 14)
            oversold = st.slider("超卖线", 20, 40, 30)
            overbought = st.slider("超买线", 60, 80, 70)
            strategy_params = {
                'period': rsi_period,
                'oversold': oversold,
                'overbought': overbought
            }
        elif strategy_name == "macd":
            macd_fast = st.slider("MACD快线", 8, 16, 12)
            macd_slow = st.slider("MACD慢线", 20, 32, 26)
            macd_signal = st.slider("信号线", 6, 12, 9)
            strategy_params = {
                'fast_period': macd_fast,
                'slow_period': macd_slow,
                'signal_period': macd_signal
            }
        elif strategy_name == "bollinger":
            boll_period = st.slider("布林带周期", 15, 30, 20)
            std_dev = st.slider("标准差倍数", 1.5, 3.0, 2.0, 0.1)
            strategy_params = {
                'period': boll_period,
                'std_dev': std_dev
            }
        elif strategy_name == "grid_trading":
            base_price = st.number_input("基准价格", value=10.0, step=0.5)
            grid_num = st.slider("网格数量", 3, 10, 5)
            grid_spacing = st.slider("网格间距(%)", 1.0, 5.0, 2.0, 0.5) / 100
            strategy_params = {
                'base_price': base_price,
                'grid_num': grid_num,
                'grid_spacing': grid_spacing
            }
        elif strategy_name == "momentum":
            momentum_period = st.slider("动量周期", 10, 60, 20)
            buy_threshold = st.slider("买入阈值(%)", 1.0, 15.0, 5.0, 1.0)
            sell_threshold = st.slider("卖出阈值(%)", -10.0, -1.0, -3.0, 1.0)
            volume_confirm = st.checkbox("成交量确认", value=True)
            strategy_params = {
                'momentum_period': momentum_period,
                'buy_threshold': buy_threshold,
                'sell_threshold': sell_threshold,
                'volume_confirm': volume_confirm,
                'volume_ratio': 1.5
            }
        elif strategy_name == "mean_reversion":
            ma_period = st.slider("均线周期", 10, 60, 20)
            entry_std = st.slider("入场标准差倍数", 1.0, 3.0, 2.0, 0.5)
            exit_std = st.slider("出场标准差倍数", 0.1, 1.5, 0.5, 0.1)
            strategy_params = {
                'ma_period': ma_period,
                'std_period': ma_period,
                'entry_std': entry_std,
                'exit_std': exit_std
            }
        elif is_custom_strategy:
            # 动态渲染自定义策略参数
            custom_params = get_custom_strategy_params(strategy_name)
            strategy_params = {}
            
            if custom_params:
                st.caption("📝 自定义策略参数")
                for param_key, param_def in custom_params.items():
                    param_name = param_def.get('name', param_key)
                    param_type = param_def.get('type', 'int')
                    param_default = param_def.get('default', 0)
                    param_min = param_def.get('min', 0)
                    param_max = param_def.get('max', 100)
                    param_step = param_def.get('step', 1)
                    param_help = param_def.get('help', '')
                    
                    if param_type == 'int':
                        value = st.slider(
                            param_name, 
                            int(param_min), int(param_max), int(param_default), int(param_step),
                            help=param_help
                        )
                    elif param_type == 'float':
                        value = st.slider(
                            param_name,
                            float(param_min), float(param_max), float(param_default), float(param_step),
                            help=param_help
                        )
                    elif param_type == 'bool':
                        value = st.checkbox(param_name, value=param_default, help=param_help)
                    else:
                        value = param_default
                    
                    strategy_params[param_key] = value
        else:
            strategy_params = {}
        
        # 资金管理
        st.subheader("资金管理")
        
        # 资金策略映射：中文显示 -> 英文value
        capital_map = {
            "固定比例": "fixed_ratio",
            "凯利公式": "kelly"
        }
        capital_display = st.selectbox("资金策略", list(capital_map.keys()))
        capital_strategy = capital_map[capital_display]
        
        if capital_strategy == "fixed_ratio":
            ratio = st.slider("投资比例", 0.05, 1.0, current_preset["ratio"], 0.05)
            capital_params = {'ratio': ratio}
        else:  # kelly
            win_rate = st.slider("胜率", 0.3, 0.8, 0.55, 0.05)
            profit_loss_ratio = st.slider("盈亏比", 1.0, 3.0, 1.5, 0.1)
            capital_params = {
                'win_rate': win_rate,
                'profit_loss_ratio': profit_loss_ratio
            }
        
        # 交易成本
        st.subheader("交易成本")
        commission_rate = st.number_input("佣金费率", 0.0001, 0.01, 0.0003, 0.0001, format="%.4f")
        slippage = st.number_input("滑点", 0.0, 0.01, 0.001, 0.001, format="%.3f")
        
        # 风控
        st.subheader("风控设置")
        max_position_ratio = st.slider("最大持仓比例", 0.1, 1.0, 0.5, 0.1)
        
        # 新增止损止盈设置
        with st.expander("🛡️ 止损止盈设置"):
            stop_loss_pct = st.slider(
                "止损比例", 
                0.01, 0.20, 
                current_preset["stop_loss"], 
                0.01,
                help="当持仓亏损达到此比例时禁止加仓"
            )
            take_profit_pct = st.slider(
                "止盈比例", 
                0.05, 0.50, 
                current_preset["take_profit"], 
                0.05,
                help="当持仓盈利达到此比例时考虑卖出"
            )
        
        # 运行按钮
        run_backtest = st.button("🚀 运行回测", type="primary", width="stretch")
    
    # 主区域
    if run_backtest:
        with st.spinner("🔄 正在运行回测..."):
            try:
                # 创建配置
                config = BacktestConfig(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    data_provider=data_provider,
                    strategy_name=strategy_name,
                    strategy_params=strategy_params,
                    capital_strategy=capital_strategy,
                    capital_params=capital_params,
                    commission_rate=commission_rate,
                    slippage_type='ratio',
                    slippage_ratio=slippage,
                    max_position_ratio=max_position_ratio,
                )
                
                # 运行回测
                engine = BacktestEngine(config)
                results = engine.run()
                
                # 保存结果到session state
                st.session_state['results'] = results
                st.session_state['last_config'] = {
                    'symbol': symbol,
                    'strategy_name': strategy_name,
                    'start_date': start_date,
                    'end_date': end_date
                }
                st.success("✅ 回测完成！")
                
            except Exception as e:
                st.error(f"❌ 回测失败: {str(e)}")
                st.exception(e)
    
    # 显示结果
    if 'results' in st.session_state:
        results = st.session_state['results']
        portfolio = results['portfolio']
        performance = results['performance']
        
        # 核心指标卡片
        st.subheader("📊 核心指标")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_return_pct = portfolio['total_return_pct']
            color_class = 'positive' if total_return_pct > 0 else 'negative'
            st.metric(
                "总收益率",
                f"{total_return_pct:.2f}%",
                delta=f"{portfolio['total_return']:,.0f} ¥"
            )
        
        with col2:
            st.metric(
                "年化收益率",
                f"{performance['annual_return']:.2f}%"
            )
        
        with col3:
            st.metric(
                "最大回撤",
                f"{performance['max_drawdown']:.2f}%",
                delta=None,
                delta_color="inverse"
            )
        
        with col4:
            st.metric(
                "夏普比率",
                f"{performance['sharpe_ratio']:.2f}"
            )
        
        # 添加到对比按钮
        if 'comparison_results' not in st.session_state:
            st.session_state.comparison_results = []
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("📊 添加到对比"):
                # 保存到对比列表
                config = st.session_state.get('last_config', {})
                comparison_item = {
                    'config': config,
                    'metrics': {
                        'total_return_pct': portfolio['total_return_pct'],
                        'annual_return': performance['annual_return'] / 100,
                        'max_drawdown': performance['max_drawdown'] / 100,
                        'sharpe_ratio': performance['sharpe_ratio'],
                        'win_rate': performance.get('win_rate', 0) / 100,
                        'total_trades': portfolio.get('num_trades', 0)
                    },
                    'equity_curve': results.get('equity_curve', [])
                }
                st.session_state.comparison_results.append(comparison_item)
                st.success(f"✅ 已添加到对比列表 (共{len(st.session_state.comparison_results)}个)")
        with col_btn2:
            if st.session_state.comparison_results:
                st.caption(f"当前对比列表有 {len(st.session_state.comparison_results)} 个回测结果")
        
        # 详细指标
        st.subheader("📈 详细指标")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**收益与风险**")
            metrics_df = pd.DataFrame({
                '指标': ['总收益率', '年化收益率', '最大回撤', '波动率', '夏普比率', '索提诺比率'],
                '数值': [
                    f"{portfolio['total_return_pct']:.2f}%",
                    f"{performance['annual_return']:.2f}%",
                    f"{performance['max_drawdown']:.2f}%",
                    f"{performance['volatility']:.2f}%",
                    f"{performance['sharpe_ratio']:.2f}",
                    f"{performance['sortino_ratio']:.2f}"
                ]
            })
            st.dataframe(metrics_df, hide_index=True, width="stretch")
        
        with col2:
            st.markdown("**资金与交易**")
            metrics_df = pd.DataFrame({
                '指标': ['初始资金', '最终权益', '现金余额', '持仓市值', '交易次数', '总手续费'],
                '数值': [
                    f"¥{portfolio['initial_cash']:,.0f}",
                    f"¥{portfolio['total_value']:,.0f}",
                    f"¥{portfolio['current_cash']:,.0f}",
                    f"¥{portfolio['positions_value']:,.0f}",
                    f"{portfolio['num_trades']}",
                    f"¥{portfolio['total_commission']:,.2f}"
                ]
            })
            st.dataframe(metrics_df, hide_index=True, width="stretch")
        
        # 交易统计
        if performance.get('win_rate') is not None:
            st.markdown("**交易统计**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("胜率", f"{performance['win_rate']:.2f}%")
            with col2:
                st.metric("盈亏比", f"{performance['profit_loss_ratio']:.2f}")
            with col3:
                st.metric("完整交易次数", f"{performance.get('num_complete_trades', 0)}")
        
        # 图表
        st.subheader("📉 权益曲线")
        equity_fig = create_equity_curve_chart(results['equity_curve'])
        st.plotly_chart(equity_fig, width="stretch")
        
        # 回撤曲线
        st.subheader("📉 回撤分析")
        drawdown_fig = create_drawdown_chart(results['equity_curve'])
        st.plotly_chart(drawdown_fig, width="stretch")
        
        # 交易记录
        if results['trades']:
            st.subheader("💱 交易记录")
            trades_fig = create_trades_chart(results['trades'])
            if trades_fig:
                st.plotly_chart(trades_fig, width="stretch")
            
            # 交易明细表
            with st.expander("📋 查看交易明细"):
                trades_df = pd.DataFrame(results['trades'])
                trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
                st.dataframe(
                    trades_df[['timestamp', 'direction', 'quantity', 'price', 'commission']],
                    hide_index=True,
                    width="stretch"
                )
        
        # 权益曲线数据
        with st.expander("📊 权益曲线数据"):
            equity_df = pd.DataFrame(results['equity_curve'])
            equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
            st.dataframe(equity_df, hide_index=True, width="stretch")
        
        # 导出结果
        st.subheader("💾 导出结果")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # 导出配置
            config_json = json.dumps(results['config'], indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 配置 (JSON)",
                data=config_json,
                file_name="backtest_config.json",
                mime="application/json"
            )
        
        with col2:
            # 导出交易记录
            if results['trades']:
                trades_df = pd.DataFrame(results['trades'])
                csv = trades_df.to_csv(index=False)
                st.download_button(
                    label="📥 交易记录 (CSV)",
                    data=csv,
                    file_name="trades.csv",
                    mime="text/csv"
                )
        
        with col3:
            # 导出HTML报告
            if st.button("📄 导出HTML报告"):
                try:
                    from dquant2.backtest.report_exporter import ReportExporter
                    exporter = ReportExporter(results)
                    html_path = exporter.export_html()
                    st.success(f"✅ HTML报告已生成: {html_path}")
                except Exception as e:
                    st.error(f"❌ 导出失败: {e}")
        
        with col4:
            # 保存到历史记录
            if st.button("💾 保存到历史"):
                try:
                    from dquant2.backtest.history_manager import BacktestHistoryManager
                    manager = BacktestHistoryManager()
                    
                    # 保存记录
                    record_id = manager.save_backtest(
                        results,
                        notes=f"Web界面回测 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        tags=['web', config.get('strategy_name', 'unknown')]
                    )
                    st.success(f"✅ 已保存到历史记录 (ID: {record_id})")
                except Exception as e:
                    st.error(f"❌ 保存失败: {e}")
    
    else:
        # 初始提示
        st.info("👈 请在左侧设置回测参数，然后点击「运行回测」按钮开始分析")
        
        st.markdown("""
        ### 🎯 使用说明
        
        1. **配置参数**: 在左侧面板设置股票代码、日期范围、初始资金等
        2. **选择策略**: 目前支持双均线策略，可调整快慢线周期
        3. **资金管理**: 选择固定比例或凯利公式
        4. **运行回测**: 点击按钮开始回测
        5. **查看结果**: 分析收益率、夏普比率、最大回撤等指标
        6. **导出数据**: 下载配置和交易记录
        
        ### ✨ 特点
        
        - 📊 **实时可视化** - 权益曲线、回撤分析、交易记录
        - 🎨 **交互式配置** - 动态调整参数立即看到效果
        - 📈 **专业指标** - 夏普比率、索提诺比率、胜率、盈亏比
        - 💾 **结果导出** - 支持JSON和CSV格式
        """)


def backtest_comparison_page():
    """回测对比页面"""
    st.markdown('<h1 class="main-header">📊 回测结果对比</h1>', unsafe_allow_html=True)
    
    # 初始化session state
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = []
    
    st.info("💡 在回测页面运行多个回测后，可以在这里对比结果")
    
    if not st.session_state.comparison_results:
        st.warning("暂无回测结果可对比。请先在回测页面运行回测。")
        return
    
    # 显示对比表格
    st.subheader("📈 绩效指标对比")
    
    comparison_data = []
    for result in st.session_state.comparison_results:
        metrics = result.get('metrics', {})
        config = result.get('config', {})
        comparison_data.append({
            '策略': config.get('strategy_name', 'N/A'),
            '股票': config.get('symbol', 'N/A'),
            '总收益率': f"{metrics.get('total_return_pct', 0):.2f}%",
            '年化收益': f"{metrics.get('annual_return', 0) * 100:.2f}%",
            '夏普比率': f"{metrics.get('sharpe_ratio', 0):.2f}",
            '最大回撤': f"{metrics.get('max_drawdown', 0) * 100:.2f}%",
            '胜率': f"{metrics.get('win_rate', 0) * 100:.1f}%",
            '交易次数': metrics.get('total_trades', 0)
        })
    
    df = pd.DataFrame(comparison_data)
    st.dataframe(df, width="stretch")
    
    # 权益曲线对比图
    if len(st.session_state.comparison_results) >= 2:
        st.subheader("📉 权益曲线对比")
        
        fig = go.Figure()
        for i, result in enumerate(st.session_state.comparison_results):
            config = result.get('config', {})
            equity_curve = result.get('equity_curve', [])
            if equity_curve:
                dates = [item['date'] for item in equity_curve]
                values = [item['equity'] for item in equity_curve]
                name = f"{config.get('strategy_name', 'N/A')} - {config.get('symbol', 'N/A')}"
                fig.add_trace(go.Scatter(x=dates, y=values, mode='lines', name=name))
        
        fig.update_layout(
            title='权益曲线对比',
            xaxis_title='日期',
            yaxis_title='权益',
            height=400
        )
        st.plotly_chart(fig, width="stretch")
    
    # 清除对比结果
    if st.button("🗑️ 清除所有对比结果"):
        st.session_state.comparison_results = []
        st.rerun()


def stock_backtest_workflow_page():
    """选股回测联动页面"""
    st.markdown('<h1 class="main-header">🔄 选股回测联动</h1>', unsafe_allow_html=True)
    
    # 初始化session state
    if 'selected_stocks' not in st.session_state:
        st.session_state.selected_stocks = []
    if 'workflow_results' not in st.session_state:
        st.session_state.workflow_results = []
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📋 已选股票")
        
        if st.session_state.selected_stocks:
            for i, stock in enumerate(st.session_state.selected_stocks):
                st.write(f"{i+1}. **{stock['name']}** ({stock['code']}) - ¥{stock.get('price', 'N/A')}")
            
            if st.button("🗑️ 清除选股结果"):
                st.session_state.selected_stocks = []
                st.rerun()
        else:
            st.info("请先在'智能选股'页面筛选股票，结果将自动显示在这里")
    
    with col2:
        st.subheader("⚙️ 批量回测设置")
        
        # 使用日期选择器
        from datetime import date
        start_date = st.date_input("开始日期", value=date(2023, 1, 1))
        end_date = st.date_input("结束日期", value=date(2023, 12, 31))
        
        strategy_map = {
            "双均线交叉": "ma_cross",
            "RSI策略": "rsi",
            "MACD策略": "macd",
            "布林带策略": "bollinger",
            "网格交易": "grid_trading",
            "动量策略": "momentum",
            "均值回归": "mean_reversion"
        }
        strategy = st.selectbox("回测策略", list(strategy_map.keys()))
        initial_cash = st.number_input("初始资金", value=100000, step=10000)
        
        # 数据源选择
        workflow_provider_map = {
            "本地数据库 (quant.db)": "local_db",
            "AkShare (真实)": "akshare",
            "Baostock (真实)": "baostock",
            "模拟数据": "mock",
        }
        # 默认与回测页面同步
        _wf_default = st.session_state.get('backtest_data_provider', 'local_db')
        _wf_default_idx = 0
        for _i, (_k, _v) in enumerate(workflow_provider_map.items()):
            if _v == _wf_default:
                _wf_default_idx = _i
                break
        workflow_provider_display = st.selectbox(
            "数据源", list(workflow_provider_map.keys()), index=_wf_default_idx,
            help="选择联动回测使用的行情数据源"
        )
        workflow_data_provider = workflow_provider_map[workflow_provider_display]
        
        # 并行回测选项
        enable_parallel = st.checkbox(
            "启用并行回测",
            value=True,
            help="使用多进程加速批量回测（推荐）"
        )
        
        if st.button("🚀 批量回测", type="primary", disabled=not st.session_state.selected_stocks):
            st.session_state.workflow_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            if enable_parallel:
                # 使用并行回测
                from dquant2.backtest.parallel_backtest import ParallelBacktest
                
                # 准备基础配置
                base_config = {
                    'start_date': start_date.strftime('%Y%m%d'),
                    'end_date': end_date.strftime('%Y%m%d'),
                    'initial_cash': initial_cash,
                    'strategy_name': strategy_map[strategy],
                    'data_provider': workflow_data_provider
                }
                
                # 提取股票代码
                symbols = [
                    stock['code'].split('.')[1] if '.' in stock['code'] else stock['code']
                    for stock in st.session_state.selected_stocks
                ]
                
                # 进度回调
                def progress_callback(message, current, total):
                    progress_bar.progress(current / total)
                    status_text.text(message)
                
                # 并行执行
                parallel = ParallelBacktest()
                results = parallel.run_batch_for_symbols(
                    symbols,
                    base_config,
                    progress_callback
                )
                
                # 转换结果格式
                for i, result in enumerate(results):
                    st.session_state.workflow_results.append({
                        'stock': st.session_state.selected_stocks[i],
                        'result': result if result['success'] else None,
                        'error': result.get('error') if not result['success'] else None,
                        'success': result['success']
                    })
                
                status_text.text("✅ 并行回测完成!")
            else:
                # 使用串行回测
                for i, stock in enumerate(st.session_state.selected_stocks):
                    status_text.text(f"正在回测: {stock['name']} ({stock['code']})")
                    progress_bar.progress((i + 1) / len(st.session_state.selected_stocks))
                    
                    try:
                        config = BacktestConfig(
                            symbol=stock['code'].split('.')[1] if '.' in stock['code'] else stock['code'],
                            start_date=start_date.strftime('%Y%m%d'),
                            end_date=end_date.strftime('%Y%m%d'),
                            initial_cash=initial_cash,
                            strategy_name=strategy_map[strategy],
                            data_provider=workflow_data_provider
                        )
                        
                        engine = BacktestEngine(config)
                        result = engine.run()
                        
                        st.session_state.workflow_results.append({
                            'stock': stock,
                            'result': result,
                            'success': True
                        })
                    except Exception as e:
                        st.session_state.workflow_results.append({
                            'stock': stock,
                            'error': str(e),
                            'success': False
                        })
                
                status_text.text("✅ 批量回测完成!")
    
    # 显示批量回测结果
    if st.session_state.workflow_results:
        st.divider()
        st.subheader("📊 批量回测结果")
        
        results_data = []
        for item in st.session_state.workflow_results:
            stock = item['stock']
            if item['success']:
                result = item['result']
                portfolio = result.get('portfolio', {})
                results_data.append({
                    '股票代码': stock['code'],
                    '股票名称': stock['name'],
                    '状态': '✅ 成功',
                    '总收益率': f"{portfolio.get('total_return_pct', 0):.2f}%",
                    '最大回撤': f"{portfolio.get('max_drawdown', 0) * 100:.2f}%",
                    '交易次数': portfolio.get('num_trades', 0)
                })
            else:
                results_data.append({
                    '股票代码': stock['code'],
                    '股票名称': stock['name'],
                    '状态': '❌ 失败',
                    '总收益率': 'N/A',
                    '最大回撤': 'N/A',
                    '交易次数': 'N/A'
                })
        
        df = pd.DataFrame(results_data)
        st.dataframe(df, width="stretch")
        
        # 按收益排序
        successful = [r for r in st.session_state.workflow_results if r['success']]
        if successful:
            sorted_results = sorted(
                successful,
                key=lambda x: x['result'].get('portfolio', {}).get('total_return_pct', 0),
                reverse=True
            )
            
            st.subheader("🏆 收益排行榜")
            for i, item in enumerate(sorted_results[:5]):
                stock = item['stock']
                ret = item['result'].get('portfolio', {}).get('total_return_pct', 0)
                medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
                st.write(f"{medal} **{stock['name']}** ({stock['code']}): {ret:.2f}%")


def data_management_page():
    """数据管理页面 - 统一的数据管理中心"""
    st.markdown('<h1 class="main-header">💾 数据管理中心</h1>', unsafe_allow_html=True)
    
    st.info("💡 统一管理股票数据：下载、缓存、清理 - 一站式解决方案")
    
    from dquant2.core.data.downloader import DataDownloader
    from dquant2.core.data.cache import ParquetCache
    from dquant2.stock.data_provider import create_data_provider
    from datetime import date, timedelta
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 配置")
        
        # 数据源选择
        st.subheader("数据源")
        provider_map = {
            "Baostock (推荐)": "baostock",
            "AkShare": "akshare"
        }
        provider_display = st.selectbox("选择数据源", list(provider_map.keys()))
        provider_name = provider_map[provider_display]
        
        # 时间范围
        st.subheader("时间范围")
        
        # 预设选项
        preset = st.selectbox(
            "快速选择",
            ["自定义", "近1年", "近3年", "近5年", "所有数据(2010至今)"]
        )
        
        today = date.today()
        if preset == "近1年":
            default_start = today - timedelta(days=365)
            default_end = today
        elif preset == "近3年":
            default_start = today - timedelta(days=365*3)
            default_end = today
        elif preset == "近5年":
            default_start = today - timedelta(days=365*5)
            default_end = today
        elif preset == "所有数据(2010至今)":
            default_start = date(2010, 1, 1)
            default_end = today
        else:
            default_start = today - timedelta(days=365)
            default_end = today
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=default_start)
        with col2:
            end_date = st.date_input("结束日期", value=default_end)
        
        # 下载选项
        st.subheader("下载选项")
        force_download = st.checkbox("强制重新下载", value=False, help="忽略缓存，强制重新下载")
        incremental_update = st.checkbox("智能增量更新", value=True, help="只下载缺失的新数据，自动合并到现有缓存")
    
    # 主区域 - 5个标签页（合并了两个版本的功能）
    tabs = st.tabs(["📄 单只股票", "📋 批量下载", "🌐 整市场", "📂 数据浏览", "🗂️ 缓存管理"])
    
    # Tab 1: 单只股票
    with tabs[0]:
        st.subheader("下载单只股票")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            single_symbol = st.text_input("股票代码", placeholder="例如: 600000", key="single_symbol")
        with col2:
            st.write("")  # 占位
            st.write("")  # 占位
            download_single = st.button("⬇️ 下载", type="primary", key="btn_single")
        
        if download_single and single_symbol:
            with st.spinner("正在下载..."):
                provider = create_data_provider(provider_name)
                downloader = DataDownloader(provider, ParquetCache())
                
                result = downloader.download_single(
                    single_symbol,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    force=force_download,
                    incremental=incremental_update
                )
                
                if result['success']:
                    st.success(f"✅ {single_symbol} 下载成功！共 {result['rows']} 条数据")
                else:
                    st.error(f"❌ {single_symbol} 下载失败: {result['message']}")
    
    # Tab 2: 批量下载
    with tabs[1]:
        st.subheader("批量下载股票")
        
        batch_mode = st.radio(
            "输入方式",
            ["文本输入", "CSV文件上传", "股票列表"],
            horizontal=True
        )
        
        symbols = []
        
        if batch_mode == "文本输入":
            batch_text = st.text_area(
                "股票代码列表",
                placeholder="每行一个股票代码，例如:\n600000\n000001\n600519",
                height=200
            )
            if batch_text:
                symbols = [s.strip() for s in batch_text.split('\n') if s.strip()]
        elif batch_mode == "CSV文件上传":
            uploaded_file = st.file_uploader("上传CSV文件", type=['csv'])
            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file)
                    # 假设第一列是股票代码
                    symbols = df.iloc[:, 0].astype(str).tolist()
                    st.success(f"✅ 已读取 {len(symbols)} 只股票")
                except Exception as e:
                    st.error(f"❌ 读取文件失败: {e}")
        else:  # 股票列表
            from dquant2.core.data.stock_lists import StockListManager
            sl_manager = StockListManager()
            lists = sl_manager.get_available_lists()
            
            col1, col2 = st.columns(2)
            with col1:
                selected_list = st.selectbox("选择股票列表", lists, index=lists.index('沪深300成分股') if '沪深300成分股' in lists else 0)
            with col2:
                stocks = sl_manager.load_list(selected_list)
                st.metric("包含股票数", f"{len(stocks)} 只")
                
            with st.expander("查看列表详情"):
                st.write([f"{s['code']} {s['name']}" for s in stocks[:50]])
                if len(stocks) > 50:
                    st.write(f"... 等共 {len(stocks)} 只")
            
            if stocks:
                symbols = [s['code'] for s in stocks]
        
        if symbols:
            st.write(f"**共 {len(symbols)} 只股票待下载**")
            
            if st.button("⬇️ 开始批量下载", type="primary", key="btn_batch"):
                provider = create_data_provider(provider_name)
                downloader = DataDownloader(provider, ParquetCache())
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def progress_callback(message, current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"{message} ({current}/{total})")
                
                with st.spinner("批量下载中..."):
                    summary = downloader.download_batch(
                        symbols,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d"),
                        progress_callback=progress_callback,
                        force=force_download,
                        incremental=incremental_update
                    )
                
                # 清除进度显示
                progress_bar.empty()
                status_text.success(f"✅ 下载完成！成功 {summary['success']} 个，缓存 {summary['cached']} 个，失败 {summary['failed']} 个")
                
                # 显示结果
                st.divider()
                st.subheader("📊 下载结果")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("总数", summary['total'])
                col2.metric("✅ 成功", summary['success'], delta_color="normal")
                col3.metric("💾 缓存", summary['cached'], delta_color="off")
                col4.metric("❌ 失败", summary['failed'], delta_color="inverse")
                
                # 失败详情
                if summary['failed'] > 0:
                    with st.expander("查看失败详情"):
                        failed_list = [r for r in summary['results'] if not r['success']]
                        for item in failed_list:
                            st.write(f"- {item['symbol']}: {item['message']}")
    
    # Tab 3: 整市场下载
    with tabs[2]:
        st.subheader("下载整个市场数据")
        
        st.warning("⚠️ 整市场下载会占用较长时间，建议选择较短的时间范围进行测试")
        
        col1, col2 = st.columns(2)
        with col1:
            market = st.selectbox("选择市场", ["上证 (sh)", "深证 (sz)"])
            market_code = 'sh' if '上证' in market else 'sz'
        
        with col2:
            max_stocks = st.number_input(
                "限制数量（0=不限制）",
                min_value=0,
                max_value=5000,
                value=50,
                help="用于测试，建议先下载少量股票"
            )
        
        if st.button("⬇️ 开始下载整市场", type="primary", key="btn_market"):
            provider = create_data_provider(provider_name)
            downloader = DataDownloader(provider, ParquetCache())
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(message, current, total):
                progress = current / total
                progress_bar.progress(progress)
                status_text.text(f"{message} ({current}/{total})")
            
            with st.spinner("下载中..."):
                summary = downloader.download_market(
                    market_code,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    progress_callback=progress_callback,
                    force=force_download,
                    incremental=incremental_update,
                    max_stocks=max_stocks if max_stocks > 0 else None
                )
            
            # 清除进度显示
            progress_bar.empty()
            status_text.success(f"✅ 下载完成！成功 {summary['success']} 个，缓存 {summary['cached']} 个，失败 {summary['failed']} 个")
            
            # 显示结果
            st.divider()
            st.subheader("📊 下载结果")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总数", summary['total'])
            col2.metric("✅ 成功", summary['success'])
            col3.metric("💾 缓存", summary['cached'])
            col4.metric("❌ 失败", summary['failed'])
            
            if summary['failed'] > 0:
                with st.expander("查看失败详情"):
                    failed_list = [r for r in summary['results'] if not r['success']]
                    for item in failed_list[:20]:  # 最多显示20个
                        st.write(f"- {item['symbol']}: {item['message']}")
    
    # Tab 4: 数据浏览（从第二个版本合并）
    with tabs[3]:
        st.subheader("本地数据文件")
        from dquant2.core.data.storage import DataFileManager
        fm = DataFileManager()
        
        # 刷新按钮
        if st.button("🔄 刷新文件列表"):
            st.rerun()
            
        files = fm.list_files()
        
        if files:
            # 统计
            total_size = sum(f['size'] for f in files) / (1024 * 1024)
            st.info(f"共发现 {len(files)} 个数据文件，总占用 {total_size:.2f} MB")
            
            # 筛选
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filter_code = st.text_input("按代码筛选", placeholder="如: 000001")
            with col_f2:
                filter_period = st.selectbox("按周期筛选", ["全部"] + list(set(f['period'] for f in files)))
            
            display_files = files
            if filter_code:
                display_files = [f for f in display_files if filter_code in f['code']]
            if filter_period != "全部":
                display_files = [f for f in display_files if f['period'] == filter_period]
            
            # 显示表格
            if display_files:
                df_files = pd.DataFrame(display_files)
                # 格式化显示
                df_show = df_files[['filename', 'period', 'start_date', 'end_date', 'dividend_type', 'size', 'modified_time']].copy()
                df_show['size'] = df_show['size'].apply(lambda x: f"{x/1024:.1f} KB")
                df_show['modified_time'] = df_show['modified_time'].dt.strftime('%Y-%m-%d %H:%M')
                
                st.dataframe(df_show, width="stretch", hide_index=True)
                
                # 删除功能
                with st.expander("🗑️ 删除文件"):
                     file_to_del = st.selectbox("选择要删除的文件", [f['filename'] for f in display_files])
                     if st.button("确认删除"):
                         # 找到对应的文件信息
                         target = next((f for f in display_files if f['filename'] == file_to_del), None)
                         if target:
                             if fm.delete_file(
                                 target['code'], target['period'], target['start_date'], 
                                 target['end_date'], target['time_range'], target['dividend_type']
                             ):
                                 st.success(f"已删除 {file_to_del}")
                                 time.sleep(1)
                                 st.rerun()
                             else:
                                 st.error("删除失败")
            else:
                st.warning("未找到匹配的文件")
        else:
            st.info("暂无本地数据文件，请前往'批量下载'标签页下载数据。")
    
    # Tab 5: 缓存管理
    with tabs[4]:
        st.subheader("📦 Parquet 缓存管理")
        st.caption("选股和回测模块使用的临时高速缓存")
        
        cache = ParquetCache()
        
        # 获取缓存统计
        stats = cache.get_cache_stats()
        
        # 显示统计信息
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("缓存文件数", f"{stats['total_files']} 个")
        with col2:
            st.metric("总大小", f"{stats['total_size_mb']:.2f} MB")
        with col3:
            st.metric("缓存目录", stats['cache_dir'])
        
        st.divider()
        
        # 显示缓存文件列表
        if stats['total_files'] > 0:
            st.subheader("📋 缓存文件列表")
            
            # 获取每个文件的详细信息
            cache_data = []
            for symbol in stats['files']:
                info = cache.get_cache_info(symbol)
                if info:
                    cache_data.append({
                        '股票代码': symbol,
                        '数据条数': info['rows'],
                        '开始日期': info['start_date'].strftime('%Y-%m-%d'),
                        '结束日期': info['end_date'].strftime('%Y-%m-%d'),
                        '天数': info['days_span'],
                        '文件大小': f"{info['file_size_mb']:.2f} MB"
                    })
            
            if cache_data:
                df = pd.DataFrame(cache_data)
                st.dataframe(df, width="stretch", hide_index=True)
                
                st.divider()
                
                # 单个文件详情
                st.subheader("🔍 详情与操作")
                selected_symbol = st.selectbox("选择股票代码", stats['files'])
                
                if selected_symbol:
                    info = cache.get_cache_info(selected_symbol)
                    if info:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**股票代码:** {info['symbol']}")
                            st.write(f"**数据条数:** {info['rows']}")
                            st.write(f"**列名:** {', '.join(info['columns'])}")
                        with col2:
                            st.write(f"**开始日期:** {info['start_date']}")
                            st.write(f"**结束日期:** {info['end_date']}")
                            st.write(f"**时间跨度:** {info['days_span']} 天")
                        
                        # 清除单个缓存
                        if st.button(f"🗑️ 清除 {selected_symbol} 的缓存", key=f"clear_{selected_symbol}"):
                            cache.clear(selected_symbol)
                            st.success(f"✅ 已清除 {selected_symbol} 的缓存")
                            st.rerun()
            
            st.divider()
            
            # 清除所有缓存
            st.subheader("⚠️ 危险操作")
            if st.button("🗑️ 清除所有缓存", type="primary"):
                cache.clear()
                st.success("✅ 已清除所有缓存")
                st.rerun()
        else:
            st.info("暂无缓存文件")
            st.write("当您运行选股或回测时，系统会自动将下载的数据保存到缓存。")


# 注意：原有重复的data_management_page函数已被合并到上面的统一版本中


def risk_dashboard_page():
    """风控仪表盘页面"""
    st.markdown('<h1 class="main-header">🛡️ 风控仪表盘</h1>', unsafe_allow_html=True)
    
    if 'results' not in st.session_state:
        st.info("💡 请先在回测页面运行回测，然后返回此页面查看详细风控分析")
        return
    
    results = st.session_state['results']
    
    # 从权益曲线计算风险指标
    from dquant2.core.risk.metrics import RiskMetrics
    
    risk_metrics = RiskMetrics()
    
    # 加载权益历史
    for record in results['equity_curve']:
        risk_metrics.update_equity(record['equity'])
    
    # 计算风险摘要
    risk_summary = risk_metrics.get_risk_summary()
    
    # 风险等级
    risk_level = risk_metrics.assess_risk_level()
    risk_color = {
        '低': 'green',
        '中': 'orange',
        '高': 'red',
        '极高': 'darkred'
    }.get(risk_level, 'gray')
    
    st.markdown(f"### 风险等级: <span style='color:{risk_color};font-weight:bold;font-size:1.5em'>{risk_level}</span>", unsafe_allow_html=True)
    
    # 核心风险指标
    st.subheader("📊 核心风险指标")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "VaR (95%)",
            f"{risk_summary['var_95']:.2f}%",
            help="在95%置信水平下的最大损失"
        )
    
    with col2:
        st.metric(
            "CVaR (95%)",
            f"{risk_summary['cvar_95']:.2f}%",
            help="超过VaR的平均损失"
        )
    
    with col3:
        st.metric(
            "最大回撤",
            f"{risk_summary['max_drawdown']:.2f}%",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            "Beta",
            f"{risk_summary['beta']:.2f}",
            help="市场相关性"
        )
    
    st.divider()
    
    # 收益风险比率
    st.subheader("📈 收益风险比率")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "夏普比率",
            f"{risk_summary['sharpe_ratio']:.2f}",
            help="每单位风险的超额收益"
        )
    
    with col2:
        st.metric(
            "索提诺比率",
            f"{risk_summary['sortino_ratio']:.2f}",
            help="每单位下行风险的超额收益"
        )
    
    with col3:
        st.metric(
            "卡玛比率",
            f"{risk_summary['calmar_ratio']:.2f}",
            help="年化收益率 / 最大回撤"
        )
    
    st.divider()
    
    # 风险预警
    st.subheader("⚠️ 风险预警")
    
    alerts = risk_metrics.get_risk_alerts()
    
    if alerts:
        for alert in alerts:
            alert_color = {
                'HIGH': '🔴',
                'MEDIUM': '🟡',
                'LOW': '🟢'
            }.get(alert['level'], '⚪')
            
            st.warning(f"{alert_color} **{alert['type']}**: {alert['message']}")
    else:
        st.success("✅ 当前无风险预警")
    
    st.divider()
    
    # 回撤分析
    st.subheader("📉 回撤分析")
    
    equity_df = pd.DataFrame(results['equity_curve'])
    equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
    
    # 计算回撤序列
    cummax = equity_df['equity'].cummax()
    drawdown = (equity_df['equity'] - cummax) / cummax * 100
    
    # 创建回撤图表
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=equity_df['timestamp'],
        y=drawdown,
        mode='lines',
        name='回撤',
        line=dict(color='#d62728', width=2),
        fill='tozeroy',
        fillcolor='rgba(214, 39, 40, 0.3)'
    ))
    
    # 标记最大回撤点
    max_dd_idx = risk_summary['drawdown_end_idx']
    if max_dd_idx < len(equity_df):
        fig.add_trace(go.Scatter(
            x=[equity_df['timestamp'].iloc[max_dd_idx]],
            y=[drawdown.iloc[max_dd_idx]],
            mode='markers',
            name='最大回撤点',
            marker=dict(size=15, color='red', symbol='x')
        ))
    
    fig.update_layout(
        title='回撤曲线',
        xaxis_title='日期',
        yaxis_title='回撤 (%)',
        height=400,
        template='plotly_white',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def advanced_analysis_page():
    """高级分析页面 - 持仓分析、参数优化等"""
    st.markdown('<h1 class="main-header">🔬 高级分析</h1>', unsafe_allow_html=True)
    
    tabs = st.tabs(["📊 持仓分析", "🔧 参数优化", "💾 数据质量"])
    
    # Tab 1: 持仓分析
    with tabs[0]:
        st.subheader("持仓分析")
        
        if 'results' not in st.session_state:
            st.info("请先运行回测")
        else:
            st.info("持仓分析功能开发中...")
            st.write("将展示：持仓集中度、行业分布、盈利排行等")
    
    # Tab 2: 参数优化
    with tabs[1]:
        st.subheader("策略参数优化")
        
        st.markdown("""
        ### 🎯 参数优化工具
        
        支持的优化方法：
        - **网格搜索**: 遍历所有参数组合
        - **随机搜索**: 随机采样参数空间
        
        优化目标：
        - 夏普比率
        - 总收益率
        - 卡玛比率
        """)
        
        # 优化配置
        col1, col2 = st.columns(2)
        
        with col1:
            opt_method = st.selectbox(
                "优化方法",
                ["网格搜索", "随机搜索"]
            )
        
        with col2:
            opt_objective = st.selectbox(
                "优化目标",
                ["夏普比率", "总收益率", "卡玛比率"]
            )
        
        # 参数范围设置
        st.subheader("参数范围")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fast_period_min = st.number_input("快线周期 - 最小", value=3, min_value=1)
            fast_period_max = st.number_input("快线周期 - 最大", value=15, min_value=1)
            fast_period_step = st.number_input("快线周期 - 步长", value=2, min_value=1)
        
        with col2:
            slow_period_min = st.number_input("慢线周期 - 最小", value=10, min_value=1)
            slow_period_max = st.number_input("慢线周期 - 最大", value=40, min_value=1)
            slow_period_step = st.number_input("慢线周期 - 步长", value=5, min_value=1)
        
        if st.button("🚀 开始优化", type="primary"):
            st.info("参数优化功能开发中...")
            st.write("将遍历参数组合，找出最优参数")
    
    # Tab 3: 数据质量
    with tabs[2]:
        st.subheader("数据质量检查")
        
        from dquant2.core.data.quality_checker import DataQualityChecker
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            check_symbol = st.text_input("股票代码", value="000001", key="quality_check_symbol")
        
        with col2:
            st.write("")
            st.write("")
            run_check = st.button("🔍 检查", type="primary")
        
        if run_check and check_symbol:
            with st.spinner(f"正在检查 {check_symbol} 的数据质量..."):
                try:
                    # 加载数据（从缓存）
                    from dquant2.core.data.cache import ParquetCache
                    cache = ParquetCache()
                    
                    df = cache.load(check_symbol)
                    
                    if df is not None and not df.empty:
                        # 执行质量检查
                        checker = DataQualityChecker()
                        check_results = checker.run_full_check(df, check_symbol)
                        
                        # 显示质量评分
                        score = check_results['summary']['quality_score']
                        score_color = 'green' if score >= 80 else 'orange' if score >= 60 else 'red'
                        
                        st.markdown(
                            f"### 质量评分: <span style='color:{score_color};font-weight:bold;font-size:2em'>{score:.0f}/100</span>",
                            unsafe_allow_html=True
                        )
                        
                        # 显示检查结果
                        for check in check_results['checks']:
                            with st.expander(f"📋 {check['check_type']}", expanded=True):
                                for issue in check['issues']:
                                    severity_icon = {
                                        'ERROR': '❌',
                                        'WARNING': '⚠️',
                                        'INFO': 'ℹ️'
                                    }.get(issue['severity'], '•')
                                    
                                    st.write(f"{severity_icon} {issue['message']}")
                    else:
                        st.warning(f"未找到 {check_symbol} 的缓存数据，请先运行回测或选股")
                        
                except Exception as e:
                    st.error(f"检查失败: {e}")


def backtest_history_page():
    """回测历史记录页面"""
    st.markdown('<h1 class="main-header">📚 回测历史</h1>', unsafe_allow_html=True)
    
    from dquant2.backtest.history_manager import BacktestHistoryManager
    
    manager = BacktestHistoryManager()
    
    # 获取统计信息
    stats = manager.get_statistics()
    
    # 显示统计卡片
    st.subheader("📊 统计概览")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总回测次数", stats['total_count'])
    
    with col2:
        avg_return = stats['avg_performance']['avg_return']
        st.metric("平均收益率", f"{avg_return:.2f}%")
    
    with col3:
        avg_sharpe = stats['avg_performance']['avg_sharpe']
        st.metric("平均夏普比率", f"{avg_sharpe:.2f}")
    
    with col4:
        avg_drawdown = stats['avg_performance']['avg_drawdown']
        st.metric("平均最大回撤", f"{avg_drawdown:.2f}%")
    
    st.divider()
    
    # 筛选选项
    st.subheader("🔍 筛选与搜索")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_symbol = st.text_input("股票代码", placeholder="留空显示全部")
    
    with col2:
        strategy_options = ["全部"] + list(stats['strategy_stats'].keys())
        filter_strategy = st.selectbox("策略", strategy_options)
        if filter_strategy == "全部":
            filter_strategy = None
    
    with col3:
        sort_by = st.selectbox("排序方式", ["最新", "收益率最高", "夏普最高"])
    
    # 高级筛选
    with st.expander("🔧 高级筛选"):
        col_adv1, col_adv2, col_adv3 = st.columns(3)
        
        with col_adv1:
            use_min_return = st.checkbox("最小收益率")
            if use_min_return:
                min_return = st.number_input("最小收益率(%)", value=0.0, step=1.0)
            else:
                min_return = None
        
        with col_adv2:
            use_max_dd = st.checkbox("最大回撤限制")
            if use_max_dd:
                max_drawdown = st.number_input("最大回撤(%)", value=20.0, step=1.0)
            else:
                max_drawdown = None
        
        with col_adv3:
            use_min_sharpe = st.checkbox("最小夏普比率")
            if use_min_sharpe:
                min_sharpe = st.number_input("最小夏普", value=0.0, step=0.1)
            else:
                min_sharpe = None
    
    # 查询记录
    if any([use_min_return, use_max_dd, use_min_sharpe]):
        # 使用高级搜索
        records = manager.search_backtests(
            min_return=min_return,
            max_drawdown=max_drawdown,
            min_sharpe=min_sharpe,
            limit=50
        )
    else:
        # 使用基本列表
        records = manager.list_backtests(
            symbol=filter_symbol if filter_symbol else None,
            strategy_name=filter_strategy,
            limit=50
        )
    
    # 显示记录列表
    st.divider()
    st.subheader(f"📋 历史记录 (共 {len(records)} 条)")
    
    if records:
        # 创建表格数据
        table_data = []
        for record in records:
            table_data.append({
                'ID': record['id'],
                '股票': record['symbol'],
                '策略': record['strategy_name'],
                '时间范围': f"{record['start_date']}-{record['end_date']}",
                '收益率(%)': f"{record['total_return_pct']:.2f}" if record['total_return_pct'] else 'N/A',
                '夏普比率': f"{record['sharpe_ratio']:.2f}" if record['sharpe_ratio'] else 'N/A',
                '最大回撤(%)': f"{record['max_drawdown']:.2f}" if record['max_drawdown'] else 'N/A',
                '交易次数': record['num_trades'] or 'N/A',
                '创建时间': record['created_at'][:19] if record['created_at'] else 'N/A'
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, width="stretch", hide_index=True)
        
        # 详细查看
        st.divider()
        st.subheader("🔎 详细查看")
        
        selected_id = st.selectbox(
            "选择记录",
            [r['id'] for r in records],
            format_func=lambda x: f"ID {x} - {next(r['symbol'] for r in records if r['id'] == x)}"
        )
        
        if selected_id:
            record = manager.get_backtest(selected_id)
            
            # 显示详细信息
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**基本信息**")
                st.write(f"- ID: {record['id']}")
                st.write(f"- 股票: {record['symbol']}")
                st.write(f"- 策略: {record['strategy_name']}")
                st.write(f"- 时间: {record['start_date']} ~ {record['end_date']}")
                st.write(f"- 初始资金: ¥{record['initial_cash']:,.0f}")
                
                if record.get('notes'):
                    st.write(f"- 备注: {record['notes']}")
                
                if record.get('tags'):
                    st.write(f"- 标签: {', '.join(record['tags'])}")
            
            with col2:
                st.markdown("**性能指标**")
                
                def safe_fmt(val, suffix="", is_pct=False):
                    if val is None:
                        return "暂无数据"
                    return f"{val:.2f}{suffix}"

                st.write(f"- 总收益率: {safe_fmt(record.get('total_return_pct'), '%')}")
                st.write(f"- 年化收益率: {safe_fmt(record.get('annual_return'), '%')}")
                st.write(f"- 最大回撤: {safe_fmt(record.get('max_drawdown'), '%')}")
                st.write(f"- 夏普比率: {safe_fmt(record.get('sharpe_ratio'))}")
                st.write(f"- 胜率: {safe_fmt(record.get('win_rate'), '%')}")
                st.write(f"- 交易次数: {record.get('num_trades', 0)}")
            
            # 操作按钮
            st.divider()
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("📊 查看完整结果"):
                    # 加载完整结果到session_state
                    st.session_state['results'] = record['results']
                    st.success("✅ 已加载结果，可在回测分析页面查看详情")
            
            with col_btn2:
                if st.button("📄 导出报告"):
                    try:
                        from dquant2.backtest.report_exporter import ReportExporter
                        exporter = ReportExporter(record['results'])
                        html_path = exporter.export_html()
                        st.success(f"✅ 报告已生成: {html_path}")
                    except Exception as e:
                        st.error(f"❌ 导出失败: {e}")
            
            with col_btn3:
                if st.button("🗑️ 删除记录", type="primary"):
                    if manager.delete_backtest(selected_id):
                        st.success("✅ 已删除")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("暂无历史记录")


def cross_sectional_page():
    """横截面多因子轮动选股页面"""
    st.markdown('<h1 class="main-header">🌊 多因子轮动选股 (横截面 Alpha)</h1>', unsafe_allow_html=True)
    
    st.info("基于日终数据的多因子打分轮动策略。目前逻辑为调取本地 quant.db 数据库最新截面行情数据，根据市值、流动性过滤后，用均额、换手率、振幅计算截面得分 (Z-Score) 并选取 Top N 标的。")
    
    with st.form("cross_sectional_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            target_stock_num = st.number_input("目标持仓股数", min_value=1, max_value=20, value=5)
        with col2:
            capital = st.number_input("模拟总资金 (元)", min_value=10000, max_value=100000000, value=1000000, step=10000)
        with col3:
            max_position_ratio = st.slider("单股最大仓位", min_value=0.1, max_value=1.0, value=0.2, step=0.05)
            
        submit_btn = st.form_submit_button("🚀 运行横截面打分选股", use_container_width=True)
        
    if submit_btn:
        with st.spinner("正在拉取全市场实时数据并计算因子打分，请稍候..."):
            try:
                # 延迟引入以防止启动慢
                from dquant2.core.strategy.custom.daily_volatility_selector import DailyRotationStrategy
                
                strategy = DailyRotationStrategy(
                    target_stock_num=target_stock_num,
                    capital=capital,
                    max_position_ratio=max_position_ratio
                )
                
                selected = strategy.select_stocks()
                
                if selected.empty:
                    st.warning("未能选出符合条件的股票。可能是当前市场数据为空或过滤条件过于严格。")
                else:
                    positions = strategy.allocate_positions(selected)
                    st.success(f"成功筛选出综合评分排名前 {len(positions)} 的标的！")
                    
                    st.subheader("📊 今日选股与仓位分配")
                    st.dataframe(
                        positions[['symbol', 'name', 'price', 'market_cap', 'turnover', 'amount', 'amplitude', 'score', 'shares']],
                        use_container_width=True,
                        hide_index=True
                    )
            except Exception as e:
                st.error(f"发生错误: {e}")

def main():
    """主函数 - 页面路由"""
    setup_page()
    
    # 侧边栏页面选择
    with st.sidebar:
        st.title("d-quant2 量化系统")
        page = st.radio(
            "选择功能",
            ["📈 回测分析", "🔍 智能选股", "🌊 多因子轮动选股", "📊 回测对比", "🔄 选股回测联动", 
             "💾 数据管理", "🛡️ 风控仪表盘", "🔬 高级分析", "📚 回测历史"],
            label_visibility="collapsed"
        )
        st.divider()
    
    # 根据选择显示对应页面
    if page == "📈 回测分析":
        backtest_page()
    elif page == "🔍 智能选股":
        stock_selection_page()
    elif page == "🌊 多因子轮动选股":
        cross_sectional_page()
    elif page == "📊 回测对比":
        backtest_comparison_page()
    elif page == "🔄 选股回测联动":
        stock_backtest_workflow_page()
    elif page == "💾 数据管理":
        data_management_page()
    elif page == "🛡️ 风控仪表盘":
        risk_dashboard_page()
    elif page == "📚 回测历史":
        backtest_history_page()
    else:  # 🔬 高级分析
        advanced_analysis_page()


if __name__ == '__main__':
    try:
        from streamlit import runtime
        from streamlit.web import cli as stcli
    except ImportError:
        # Fallback for very old versions or if import structure differs
        import streamlit as st
        # If runtime not found, assume we need to restart or valid context not found? 
        # Actually safer to just try standard import
        sys.exit("Error: Streamlit runtime not found. Please run with `streamlit run app.py`")

    import sys
    
    if runtime.exists():
        main()
    else:
        # Re-run with streamlit
        sys.argv = ["streamlit", "run", sys.argv[0], "--server.port=8501", "--server.address=localhost"]
        sys.exit(stcli.main())
