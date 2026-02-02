"""回测报告导出模块

支持HTML和PDF格式的专业回测报告导出
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import base64
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ReportExporter:
    """回测报告导出器"""
    
    def __init__(self, results: Dict, output_dir: str = None):
        """初始化
        
        Args:
            results: 回测结果字典
            output_dir: 输出目录，默认为当前目录下的reports文件夹
        """
        self.results = results
        self.output_dir = output_dir or os.path.join(os.getcwd(), 'reports')
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def export_html(self, filename: Optional[str] = None) -> str:
        """导出HTML格式报告
        
        Args:
            filename: 文件名，如果为None则自动生成
            
        Returns:
            输出文件路径
        """
        if filename is None:
            config = self.results.get('config', {})
            symbol = config.get('symbol', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_report_{symbol}_{timestamp}.html"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 生成HTML内容
        html_content = self._generate_html()
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    
    def export_pdf(self, filename: Optional[str] = None) -> str:
        """导出PDF格式报告
        
        Args:
            filename: 文件名，如果为None则自动生成
            
        Returns:
            输出文件路径
        
        Note:
            需要安装 pdfkit 和 wkhtmltopdf:
            pip install pdfkit
            brew install wkhtmltopdf  # macOS
        """
        # 先生成HTML
        html_content = self._generate_html()
        
        if filename is None:
            config = self.results.get('config', {})
            symbol = config.get('symbol', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_report_{symbol}_{timestamp}.pdf"
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            import pdfkit
            
            # PDF选项
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None
            }
            
            # 转换为PDF
            pdfkit.from_string(html_content, filepath, options=options)
            
            return filepath
        except ImportError:
            raise ImportError(
                "PDF导出需要安装 pdfkit 和 wkhtmltopdf:\n"
                "pip install pdfkit\n"
                "brew install wkhtmltopdf (macOS) 或访问 https://wkhtmltopdf.org/downloads.html"
            )
        except Exception as e:
            raise RuntimeError(f"PDF生成失败: {e}")
    
    def _generate_html(self) -> str:
        """生成HTML内容"""
        # 提取数据
        config = self.results.get('config', {})
        portfolio = self.results.get('portfolio', {})
        performance = self.results.get('performance', {})
        equity_curve = self.results.get('equity_curve', [])
        trades = self.results.get('trades', [])
        
        # 生成图表
        equity_chart = self._create_equity_chart(equity_curve)
        drawdown_chart = self._create_drawdown_chart(equity_curve)
        trades_chart = self._create_trades_chart(trades) if trades else ""
        
        # 生成HTML
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回测报告 - {config.get('symbol', 'N/A')}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #1f77b4;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            color: #1f77b4;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            color: #666;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: #1f77b4;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .metric-card.positive {{
            background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
        }}
        
        .metric-card.negative {{
            background: linear-gradient(135deg, #ff1744 0%, #ff5252 100%);
        }}
        
        .metric-label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
        }}
        
        .config-table, .performance-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        
        .config-table th, .config-table td,
        .performance-table th, .performance-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .config-table th, .performance-table th {{
            background: #f5f5f5;
            font-weight: bold;
            color: #333;
        }}
        
        .chart-container {{
            margin: 30px 0;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            color: #666;
            font-size: 0.9em;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 报告头部 -->
        <div class="header">
            <h1>📊 量化回测报告</h1>
            <div class="subtitle">
                {config.get('symbol', 'N/A')} | 
                {config.get('start_date', 'N/A')} ~ {config.get('end_date', 'N/A')}
            </div>
            <div class="subtitle">
                生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        
        <!-- 核心指标 -->
        <div class="section">
            <h2 class="section-title">核心指标</h2>
            <div class="metrics-grid">
                <div class="metric-card {self._get_card_class(portfolio.get('total_return_pct', 0))}">
                    <div class="metric-label">总收益率</div>
                    <div class="metric-value">{portfolio.get('total_return_pct', 0):.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">年化收益率</div>
                    <div class="metric-value">{performance.get('annual_return', 0):.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">最大回撤</div>
                    <div class="metric-value">{performance.get('max_drawdown', 0):.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">夏普比率</div>
                    <div class="metric-value">{performance.get('sharpe_ratio', 0):.2f}</div>
                </div>
            </div>
        </div>
        
        <!-- 回测配置 -->
        <div class="section">
            <h2 class="section-title">回测配置</h2>
            <table class="config-table">
                <tr>
                    <th>配置项</th>
                    <th>值</th>
                </tr>
                <tr>
                    <td>股票代码</td>
                    <td>{config.get('symbol', 'N/A')}</td>
                </tr>
                <tr>
                    <td>开始日期</td>
                    <td>{config.get('start_date', 'N/A')}</td>
                </tr>
                <tr>
                    <td>结束日期</td>
                    <td>{config.get('end_date', 'N/A')}</td>
                </tr>
                <tr>
                    <td>初始资金</td>
                    <td>¥{config.get('initial_cash', 0):,.0f}</td>
                </tr>
                <tr>
                    <td>策略</td>
                    <td>{config.get('strategy_name', 'N/A')}</td>
                </tr>
                <tr>
                    <td>策略参数</td>
                    <td>{json.dumps(config.get('strategy_params', {}), ensure_ascii=False)}</td>
                </tr>
            </table>
        </div>
        
        <!-- 性能指标 -->
        <div class="section">
            <h2 class="section-title">性能指标</h2>
            <table class="performance-table">
                <tr>
                    <th>指标</th>
                    <th>数值</th>
                </tr>
                <tr>
                    <td>总收益</td>
                    <td>¥{portfolio.get('total_return', 0):,.2f}</td>
                </tr>
                <tr>
                    <td>总收益率</td>
                    <td>{portfolio.get('total_return_pct', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>年化收益率</td>
                    <td>{performance.get('annual_return', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>最大回撤</td>
                    <td>{performance.get('max_drawdown', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>波动率</td>
                    <td>{performance.get('volatility', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>夏普比率</td>
                    <td>{performance.get('sharpe_ratio', 0):.2f}</td>
                </tr>
                <tr>
                    <td>索提诺比率</td>
                    <td>{performance.get('sortino_ratio', 0):.2f}</td>
                </tr>
                <tr>
                    <td>胜率</td>
                    <td>{performance.get('win_rate', 0) or 0:.2f}%</td>
                </tr>
                <tr>
                    <td>盈亏比</td>
                    <td>{performance.get('profit_loss_ratio', 0) or 0:.2f}</td>
                </tr>
                <tr>
                    <td>交易次数</td>
                    <td>{portfolio.get('num_trades', 0)}</td>
                </tr>
                <tr>
                    <td>总手续费</td>
                    <td>¥{portfolio.get('total_commission', 0):,.2f}</td>
                </tr>
            </table>
        </div>
        
        <!-- 权益曲线图 -->
        <div class="section">
            <h2 class="section-title">权益曲线</h2>
            <div class="chart-container">
                <div id="equity-chart"></div>
            </div>
        </div>
        
        <!-- 回撤分析图 -->
        <div class="section">
            <h2 class="section-title">回撤分析</h2>
            <div class="chart-container">
                <div id="drawdown-chart"></div>
            </div>
        </div>
        
        <!-- 交易记录图 -->
        {f'''
        <div class="section">
            <h2 class="section-title">交易记录</h2>
            <div class="chart-container">
                <div id="trades-chart"></div>
            </div>
        </div>
        ''' if trades else ''}
        
        <!-- 页脚 -->
        <div class="footer">
            <p>本报告由 d-quant2 量化回测系统生成</p>
            <p>报告仅供参考，不构成投资建议</p>
        </div>
    </div>
    
    <script>
        // 权益曲线图
        {equity_chart}
        
        // 回撤分析图
        {drawdown_chart}
        
        // 交易记录图
        {trades_chart}
    </script>
</body>
</html>
"""
        return html
    
    def _get_card_class(self, value: float) -> str:
        """获取指标卡片的CSS类"""
        if value > 0:
            return 'positive'
        elif value < 0:
            return 'negative'
        return ''
    
    def _create_equity_chart(self, equity_curve: List[Dict]) -> str:
        """创建权益曲线图的JavaScript代码"""
        if not equity_curve:
            return "console.log('No equity curve data');"
        
        df = pd.DataFrame(equity_curve)
        
        # 创建图表
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['equity'],
            mode='lines',
            name='总权益',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        fig.update_layout(
            title='权益曲线',
            xaxis_title='日期',
            yaxis_title='权益 (¥)',
            height=400,
            hovermode='x unified',
            template='plotly_white'
        )
        
        # 转换为JavaScript
        config = {'displayModeBar': False}
        return f"Plotly.newPlot('equity-chart', {fig.to_json()}, {json.dumps(config)});"
    
    def _create_drawdown_chart(self, equity_curve: List[Dict]) -> str:
        """创建回撤分析图的JavaScript代码"""
        if not equity_curve:
            return "console.log('No drawdown data');"
        
        df = pd.DataFrame(equity_curve)
        
        # 计算回撤
        cummax = df['equity'].cummax()
        drawdown = (df['equity'] - cummax) / cummax * 100
        
        # 创建图表
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=drawdown,
            mode='lines',
            name='回撤',
            line=dict(color='#d62728', width=2),
            fill='tozeroy',
            fillcolor='rgba(214, 39, 40, 0.3)'
        ))
        
        fig.update_layout(
            title='回撤曲线',
            xaxis_title='日期',
            yaxis_title='回撤 (%)',
            height=300,
            hovermode='x unified',
            template='plotly_white'
        )
        
        # 转换为JavaScript
        config = {'displayModeBar': False}
        return f"Plotly.newPlot('drawdown-chart', {fig.to_json()}, {json.dumps(config)});"
    
    def _create_trades_chart(self, trades: List[Dict]) -> str:
        """创建交易记录图的JavaScript代码"""
        if not trades:
            return "console.log('No trades data');"
        
        df = pd.DataFrame(trades)
        
        # 分离买卖
        buys = df[df['direction'] == 'BUY']
        sells = df[df['direction'] == 'SELL']
        
        # 创建图表
        fig = go.Figure()
        
        # 买入点
        fig.add_trace(go.Scatter(
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
        ))
        
        # 卖出点
        fig.add_trace(go.Scatter(
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
        ))
        
        fig.update_layout(
            title='交易记录',
            xaxis_title='日期',
            yaxis_title='价格 (¥)',
            height=300,
            hovermode='x unified',
            template='plotly_white'
        )
        
        # 转换为JavaScript
        config = {'displayModeBar': False}
        return f"Plotly.newPlot('trades-chart', {fig.to_json()}, {json.dumps(config)});"


# 便捷函数
def export_report(results: Dict, format: str = 'html', output_dir: str = None, filename: str = None) -> str:
    """导出回测报告
    
    Args:
        results: 回测结果字典
        format: 导出格式 ('html' 或 'pdf')
        output_dir: 输出目录
        filename: 文件名
        
    Returns:
        输出文件路径
    """
    exporter = ReportExporter(results, output_dir)
    
    if format.lower() == 'pdf':
        return exporter.export_pdf(filename)
    else:
        return exporter.export_html(filename)
