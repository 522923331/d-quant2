#!/bin/bash

# d-quant2 Web界面启动脚本

echo "🚀 启动 d-quant2 Web 界面..."
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装 Python3"
    exit 1
fi

# 检查依赖
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "⚠️  Streamlit 未安装，正在安装依赖..."
    pip3 install -q streamlit plotly pandas numpy baostock akshare
fi

# 启动Streamlit应用
echo "📊 正在启动 Streamlit 服务器..."
echo "🌐 访问地址: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

python3 -m streamlit run app.py --server.port=8501 --server.address=localhost
