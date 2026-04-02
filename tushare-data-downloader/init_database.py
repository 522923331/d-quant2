import sqlite3
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

from llvmlite.binding import initialize

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _default_db_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "data" / "db" / "quant.db")

class QuantDatabaseInitializer:
    def __init__(self, db_path: str = None, sql_file: str = "sql/db_init.sql"):
        self.sql_file = sql_file
        self.db_path = db_path or os.getenv("QUANT_DB_PATH") or _default_db_path()
        self.conn = None
        self.cursor = None

        #确保目录存在
        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)
        Path(os.path.dirname(self.sql_file)).mkdir(parents=True, exist_ok=True)


    def read_sql_file(self) -> str:
        if not os.path.exists(self.sql_file):
            logger.error(f"{self.sql_file} not exists")
            sys.exit(1)

        try:
            with open(self.sql_file, "r") as f:
                sql = f.read()
            logger.info(f"成功读取SQL文件: {self.sql_file}")
            return sql
        except Exception as e:
            logger.error(f"read {self.sql_file} error: {e}")
            sys.exit(1)


    def execute_sql_script(self, sql_script: str) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
            conn.execute("PRAGMA journal_mode = WAL")  # 启用WAL模式，提高并发性能
            conn.execute("PRAGMA synchronous = NORMAL")  # 平衡性能和数据安全
            cursor = conn.cursor()
            # 开始事务
            conn.execute("BEGIN TRANSACTION")
            # 执行整个SQL脚本
            cursor.executescript(sql_script)
            # 提交事务
            conn.commit()

            # 获取创建的表信息
            cursor.execute("""
                           SELECT name, type
                           FROM sqlite_master
                           WHERE type IN ('table', 'view', 'index')
                           ORDER BY type, name
                           """)
            objects = cursor.fetchall()

            # 统计各种对象数量
            tables = [obj for obj in objects if obj[1] == 'table']
            views = [obj for obj in objects if obj[1] == 'view']
            indexes = [obj for obj in objects if obj[1] == 'index']

            logger.info(f"数据库初始化完成！")
            logger.info(f"数据库文件: {self.db_path}")
            logger.info(f"创建的表: {len(tables)} 个")
            logger.info(f"创建的视图: {len(views)} 个")
            logger.info(f"创建的索引: {len(indexes)} 个")

            # 打印表名
            if tables:
                table_names = [table[0] for table in tables]
                logger.info(f"表列表: {', '.join(table_names)}")

            # 验证数据库完整性
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            logger.info(f"数据库完整性检查: {integrity_result[0]}")

            # 获取数据库大小
            db_size = os.path.getsize(self.db_path)
            logger.info(f"数据库大小: {db_size / 1024:.2f} KB")

            return True
        except Exception as e:
            logger.error(f"执行SQL脚本时发生错误: {e}")
            return False
        finally:
            if conn:
                conn.close()


    def initialize_database(self) -> bool:
        logger.info("开始初始化量化数据库...")
        logger.info(f"数据库路径: {self.db_path}")
        logger.info(f"SQL脚本路径: {self.sql_file}")
        try:
            sql_script = self.read_sql_file()
            success = self.execute_sql_script(sql_script)
            if success:
                logger.info("数据库初始化成功！")
            else:
                logger.error("数据库初始化失败！")

            return  success
        except Exception as e:
            logger.error(f"初始化数据库时发生错误: {e}")
            return False


if __name__ == "__main__":
    initializer = QuantDatabaseInitializer()
    success = initializer.initialize_database()
    sys.exit(0 if success else 1)
