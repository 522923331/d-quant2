"""数据提供者实现"""

from dquant2.core.data.providers.base import MockDataProvider
from dquant2.core.data.providers.akshare_provider import AkShareProvider
from dquant2.core.data.providers.baostock_provider import BaostockProvider

__all__ = ["MockDataProvider", "AkShareProvider", "BaostockProvider"]
