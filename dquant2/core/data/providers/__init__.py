"""数据提供者实现"""

from dquant2.core.data.providers.base import MockDataProvider
from dquant2.core.data.providers.akshare_provider import AkShareProvider
from dquant2.core.data.providers.baostock_provider import BaostockProvider
from dquant2.core.data.providers.local_db_provider import LocalDBProvider

__all__ = ["MockDataProvider", "AkShareProvider", "BaostockProvider", "LocalDBProvider"]
