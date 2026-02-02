"""全局配置文件

统一管理项目中的各类配置参数
"""

import os
from pathlib import Path

# ==================== 项目路径配置 ====================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
CACHE_DIR = DATA_DIR / 'cache'
DB_DIR = DATA_DIR / 'db'
LOG_DIR = PROJECT_ROOT / 'logs'

# 确保目录存在
for dir_path in [DATA_DIR, CACHE_DIR, DB_DIR, LOG_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== Web服务配置 ====================
WEB_CONFIG = {
    'host': 'localhost',
    'port': 8501,
    'page_title': 'd-quant2 量化系统',
    'page_icon': '📈',
    'layout': 'wide',
}

# ==================== 数据源配置 ====================
DATA_SOURCE_CONFIG = {
    'default_provider': 'baostock',  # 默认数据源
    'available_providers': ['mock', 'akshare', 'baostock'],
    'cache_ttl_seconds': 3600,  # 缓存有效期（秒）
    'default_lookback_days': 100,  # 默认回溯天数
}

# ==================== 回测配置 ====================
BACKTEST_CONFIG = {
    'initial_cash': 1000000,  # 默认初始资金
    'commission_rate': 0.0003,  # 默认佣金费率（万3）
    'min_commission': 5.0,  # 最低佣金（元）
    'stamp_tax_rate': 0.001,  # 印花税率（千分之一，仅卖出）
    'transfer_fee_rate': 0.00002,  # 过户费率（沪市）
    'flow_fee': 0.0,  # 流量费
    'slippage_ratio': 0.001,  # 默认滑点比例
    'max_position_ratio': 0.5,  # 默认最大持仓比例
}

# ==================== 风控配置 ====================
RISK_CONFIG = {
    'var_confidence_level': 0.95,  # VaR置信水平
    'max_drawdown_threshold': 0.20,  # 最大回撤阈值（20%）
    'volatility_threshold': 0.30,  # 波动率阈值（30%）
    'risk_free_rate': 0.03,  # 无风险利率（3%）
}

# ==================== 选股配置 ====================
STOCK_SELECTION_CONFIG = {
    'default_market': 'all',  # 默认市场
    'max_stocks': 20,  # 默认最大选股数量
    'lookback_days': 100,  # 回溯天数
    'min_price': 5.0,  # 最低价格
    'max_price': 100.0,  # 最高价格
}

# ==================== 缓存配置 ====================
CACHE_CONFIG = {
    'cache_dir': str(CACHE_DIR),
    'cache_ttl': 3600,  # 缓存有效期（秒）
    'max_cache_size_mb': 1000,  # 最大缓存大小（MB）
    'enable_cache': True,  # 是否启用缓存
}

# ==================== 数据库配置 ====================
DATABASE_CONFIG = {
    'db_path': str(DB_DIR / 'dquant2.db'),
    'wal_mode': True,  # WAL模式
    'timeout': 30,  # 超时时间（秒）
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    'log_dir': str(LOG_DIR),
    'log_level': os.environ.get('LOG_LEVEL', 'INFO'),  # 支持环境变量配置
    'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_file': str(LOG_DIR / 'dquant2.log'),
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}

# ==================== 性能配置 ====================
PERFORMANCE_CONFIG = {
    'enable_parallel': True,  # 是否启用并行计算
    'max_workers': 4,  # 最大工作进程数
    'chunk_size': 100,  # 批量处理大小
}

# ==================== 通知配置 ====================
NOTIFICATION_CONFIG = {
    'enable_email': False,  # 是否启用邮件通知
    'email_host': '',
    'email_port': 587,
    'email_user': '',
    'email_password': '',
    'email_receivers': [],
}

# ==================== UI配置 ====================
UI_CONFIG = {
    'theme': 'light',  # 主题：light/dark
    'show_progress': True,  # 是否显示进度条
    'enable_cache': True,  # 是否启用UI缓存
    'refresh_interval': 1,  # 刷新间隔（秒）
}

# ==================== 策略配置 ====================
STRATEGY_CONFIG = {
    'default_strategy': 'ma_cross',  # 默认策略
    'custom_strategy_dir': str(PROJECT_ROOT / 'dquant2' / 'core' / 'strategy' / 'custom'),
}

# ==================== 导出所有配置 ====================
def get_all_config():
    """获取所有配置"""
    return {
        'project_root': str(PROJECT_ROOT),
        'data_dir': str(DATA_DIR),
        'cache_dir': str(CACHE_DIR),
        'db_dir': str(DB_DIR),
        'log_dir': str(LOG_DIR),
        'web': WEB_CONFIG,
        'data_source': DATA_SOURCE_CONFIG,
        'backtest': BACKTEST_CONFIG,
        'risk': RISK_CONFIG,
        'stock_selection': STOCK_SELECTION_CONFIG,
        'cache': CACHE_CONFIG,
        'database': DATABASE_CONFIG,
        'log': LOG_CONFIG,
        'performance': PERFORMANCE_CONFIG,
        'notification': NOTIFICATION_CONFIG,
        'ui': UI_CONFIG,
        'strategy': STRATEGY_CONFIG,
    }


def print_config():
    """打印所有配置"""
    import json
    config = get_all_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    print_config()
