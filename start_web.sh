#!/bin/bash

# d-quant2 Web界面启动脚本

echo "🚀 启动 d-quant2 Web 界面..."
echo ""

# 检查依赖
if ! command -v streamlit &> /dev/null; then
    echo "⚠️  Streamlit 未安装，正在安装依赖..."
    pip install -q streamlit plotly
fi

# 启动Streamlit应用
echo "📊 正在启动 Streamlit 服务器..."
echo "🌐 访问地址: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

streamlit run app.py --server.port=8501 --server.address=localhost
