# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# 配置文件
# """
#
# import os
# from pathlib import Path
#
# # 项目根目录
# BASE_DIR = Path(__file__).parent
#
# # 数据库配置
# DATABASE_CONFIG = {
#     'path': BASE_DIR /'data'/ 'db' / 'quant.db',
#     'timeout': 30
# }
#
# # Tushare配置（从环境变量或文件读取）
# TUSHARE_CONFIG = {
#     'token': os.getenv('TUSHARE_TOKEN', '7c8157eef2bc27a38af3711c83ee5ed1a244b8d6732caeb6a08fecd7'),  # 优先从环境变量读取
#     'timeout': 30,
#     'retry_count': 3,
#     'retry_delay': 5
# }
#
# # 下载配置
# DOWNLOAD_CONFIG = {
#     'batch_size': 1000,  # 分批下载的大小
#     'max_workers': 4,  # 最大并发数（如果需要并发下载）
#     'cache_dir': BASE_DIR / 'cache',
#     'log_dir': BASE_DIR / 'logs'
# }
#
# # 数据表配置
# TABLE_CONFIG = {
#     'stock_basic': {
#         'fields': 'ts_code,symbol,name,area,industry,market,list_date,is_hs,act_name,act_ent_type'
#     }
#     # 'index_basic': {
#     #     'fields': 'ts_code,name,fullname,market,publisher,index_type,category,base_date,base_point,list_date,weight_rule,desc,exp_date'
#     # },
#     # 'daily_quote': {
#     #     'fields': 'ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
#     # }
# }
#
#
# # 创建必要的目录
# def create_directories():
#     """创建必要的目录"""
#     dirs = [
#         DATABASE_CONFIG['path'].parent,
#         DOWNLOAD_CONFIG['cache_dir'],
#         DOWNLOAD_CONFIG['log_dir']
#     ]
#
#     for dir_path in dirs:
#         dir_path.mkdir(parents=True, exist_ok=True)
#         print(f"确保目录存在: {dir_path}")
#
#
# if __name__ == "__main__":
#     create_directories()