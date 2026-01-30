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
        
        # 基本设置
        st.subheader("基本设置")
        market = st.selectbox("市场", ["上证(sh)", "深证(sz)"])
        market_code = 'sh' if '上证' in market else 'sz'
        max_stocks = st.number_input("股票数量上限", min_value=1, max_value=100, value=10)
        
        # 技术指标
        st.subheader("技术指标")
        use_macd = st.checkbox("MACD金叉", value=True)
        use_kdj = st.checkbox("KDJ可买入", value=True)
        use_rsi = st.checkbox("RSI超卖(<30)", value=True)
        use_cci = st.checkbox("CCI超卖(<-100)", value=True)
        use_wma = st.checkbox("价格 > 加权均线", value=True)
        use_ema = st.checkbox("价格 > 指数均线", value=True)
        use_sma = st.checkbox("价格 > 简单均线", value=True)
        use_volume = st.checkbox("成交量放大", value=True)
        use_boll = st.checkbox("布林带下轨", value=True)
        
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
        
        # 基本面指标(可选)
        with st.expander("📊 基本面指标(可选)"):
            use_pe_ratio = st.checkbox("市盈率 < 20", value=False)
            use_pb_ratio = st.checkbox("市净率 < 2", value=False)
            use_roe = st.checkbox("ROE > 15%", value=False)
            use_net_profit_margin = st.checkbox("净利率 > 10%", value=False)
        
        # 开始选股按钮
        run_selection = st.button("🚀 开始选股", type="primary", use_container_width=True)
    
    # 主区域
    if run_selection:
        # 清除之前的结果
        if 'selection_results' in st.session_state:
            del st.session_state['selection_results']
        
        # 创建配置
        config = StockSelectorConfig(
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
            use_pe_ratio=use_pe_ratio,
            use_pb_ratio=use_pb_ratio,
            use_roe=use_roe,
            use_net_profit_margin=use_net_profit_margin
        )
        
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
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            
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
            csv = results_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载选股结果 (CSV)",
                data=csv,
                file_name=f"selected_stocks_{datetime.today().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("未找到符合条件的股票,请尝试调整筛选条件")
    else:
        # 初始提示
        st.info("👈 请在左侧设置选股条件,然后点击「开始选股」按钮")
        
        st.markdown("""
        ### 🎯 使用说明
        
        1. **选择市场**: 上证或深证
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
        from datetime import date, datetime
        col1, col2 = st.columns(2)
        with col1:
            start_date_input = st.date_input(
                "开始日期",
                value=date(2020, 1, 1),
                min_value=date(2010, 1, 1),
                max_value=date.today()
            )
        with col2:
            end_date_input = st.date_input(
                "结束日期",
                value=date(2023, 12, 31),
                min_value=date(2010, 1, 1),
                max_value=date.today()
            )
        
        # 转换日期格式为 YYYYMMDD
        start_date = start_date_input.strftime("%Y%m%d")
        end_date = end_date_input.strftime("%Y%m%d")
        
        initial_cash = st.number_input("初始资金 (¥)", min_value=10000, value=1000000, step=10000)
        
        # 数据源
        st.subheader("数据设置")
        
        # 数据源映射：中文显示 -> 英文value
        data_provider_map = {
            "模拟数据": "mock",
            "真实数据(AkShare)": "akshare"
        }
        data_provider_display = st.selectbox("数据源", list(data_provider_map.keys()))
        data_provider = data_provider_map[data_provider_display]
        
        # 策略设置
        st.subheader("策略设置")
        
        # 策略映射：中文显示 -> 英文value
        strategy_map = {
            "双均线交叉": "ma_cross"
        }
        strategy_display = st.selectbox("策略", list(strategy_map.keys()))
        strategy_name = strategy_map[strategy_display]
        
        if strategy_name == "ma_cross":
            fast_period = st.slider("快线周期", 3, 30, current_preset["fast"])
            slow_period = st.slider("慢线周期", 10, 60, current_preset["slow"])
            strategy_params = {
                'fast_period': fast_period,
                'slow_period': slow_period
            }
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
        run_backtest = st.button("🚀 运行回测", type="primary", use_container_width=True)
    
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
                    slippage=slippage,
                    max_position_ratio=max_position_ratio,
                )
                
                # 运行回测
                engine = BacktestEngine(config)
                results = engine.run()
                
                # 保存结果到session state
                st.session_state['results'] = results
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
            st.dataframe(metrics_df, hide_index=True, use_container_width=True)
        
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
            st.dataframe(metrics_df, hide_index=True, use_container_width=True)
        
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
        st.plotly_chart(equity_fig, use_container_width=True)
        
        # 回撤曲线
        st.subheader("📉 回撤分析")
        drawdown_fig = create_drawdown_chart(results['equity_curve'])
        st.plotly_chart(drawdown_fig, use_container_width=True)
        
        # 交易记录
        if results['trades']:
            st.subheader("💱 交易记录")
            trades_fig = create_trades_chart(results['trades'])
            if trades_fig:
                st.plotly_chart(trades_fig, use_container_width=True)
            
            # 交易明细表
            with st.expander("📋 查看交易明细"):
                trades_df = pd.DataFrame(results['trades'])
                trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
                st.dataframe(
                    trades_df[['timestamp', 'direction', 'quantity', 'price', 'commission']],
                    hide_index=True,
                    use_container_width=True
                )
        
        # 权益曲线数据
        with st.expander("📊 权益曲线数据"):
            equity_df = pd.DataFrame(results['equity_curve'])
            equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
            st.dataframe(equity_df, hide_index=True, use_container_width=True)
        
        # 导出结果
        st.subheader("💾 导出结果")
        col1, col2 = st.columns(2)
        
        with col1:
            # 导出配置
            config_json = json.dumps(results['config'], indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 下载配置 (JSON)",
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
                    label="📥 下载交易记录 (CSV)",
                    data=csv,
                    file_name="trades.csv",
                    mime="text/csv"
                )
    
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


def main():
    """主函数 - 页面路由"""
    
    # 侧边栏页面选择
    with st.sidebar:
        st.title("d-quant2 量化系统")
        page = st.radio(
            "选择功能",
            ["📈 回测分析", "🔍 智能选股"],
            label_visibility="collapsed"
        )
        st.divider()
    
    # 根据选择显示对应页面
    if page == "📈 回测分析":
        backtest_page()
    else:
        stock_selection_page()


if __name__ == '__main__':
    main()
