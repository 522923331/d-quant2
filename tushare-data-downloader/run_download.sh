#!/bin/bash
# run_download.sh

# 设置环境变量
export TUSHARE_TOKEN="7c8157eef2bc27a38af3711c83ee5ed1a244b8d6732caeb6a08fecd7"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${REPO_ROOT}"
export QUANT_DB_PATH="${REPO_ROOT}/data/db/quant.db"

# 创建虚拟环境（如果需要）
if [ ! -d "${SCRIPT_DIR}/venv" ]; then
    python3 -m venv "${SCRIPT_DIR}/venv"
fi

# 激活虚拟环境
source "${SCRIPT_DIR}/venv/bin/activate"

# 安装依赖
pip install -r "${SCRIPT_DIR}/requirements.txt"

# 运行下载器
echo "开始下载数据..."
python "${SCRIPT_DIR}/tushare_downloader.py" --task daily

echo "数据下载完成！"