import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dquant2.stock.selector import StockSelector
from dquant2.stock.config import StockSelectorConfig
import time

# Clean the CSV cache so we can observe if it recreates it
import glob
print("Cleaning cache...")
for f in glob.glob('/Users/k02/PycharmProjects/lianghua2/d-quant2/dquant2/core/data/stock_lists/data/*.csv'):
    os.remove(f)

start_time = time.time()
print("Running with local_db...")
config = StockSelectorConfig(
    data_provider='local_db',
    market='all',
    max_stocks=3,
    use_macd=False,
    use_kdj=False,
    use_rsi=False,
    use_cci=False,
    use_wma=False,
    use_ema=False,
    use_sma=False,
    use_volume=False,
    use_boll=False,
    use_price_range=False,
    use_turnover=False
)

selector = StockSelector(config)
def callback(msg, curr, total):
    pass
selector.set_progress_callback(callback)
results = selector.select_stocks()
print(f"local_db selected {len(results)} stocks in {time.time()-start_time:.2f}s")
csv_files = glob.glob('/Users/k02/PycharmProjects/lianghua2/d-quant2/dquant2/core/data/stock_lists/data/*.csv')
print(f"CSV files created: {csv_files}")

