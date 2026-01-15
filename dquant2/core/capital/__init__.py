"""资金管理模块"""

from dquant2.core.capital.base import BaseCapitalStrategy
from dquant2.core.capital.fixed_ratio import FixedRatioStrategy
from dquant2.core.capital.kelly import KellyStrategy

__all__ = ["BaseCapitalStrategy", "FixedRatioStrategy", "KellyStrategy"]
