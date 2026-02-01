
from dquant2.stock.selector import StockSelector, StockSelectorConfig
from dquant2.core.data.stock_lists import StockListManager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

def test_selector_with_list():
    print("\n=== Testing Selector with Stock List ===")
    
    # 1. Loading a small list
    sl_manager = StockListManager()
    stock_list = sl_manager.load_list("上证50成分股")
    print(f"Loaded list: {len(stock_list)} stocks")
    
    # Extract codes (simulate what app.py does)
    candidate_codes = [s['code'] for s in stock_list[:5]] # Test with first 5 for speed
    print(f"Candidates (first 5): {candidate_codes}")
    
    # 2. Config with candidates
    config = StockSelectorConfig()
    config.candidate_codes = candidate_codes
    config.max_stocks = 5
    # Disable most filters to ensure we get results fast if checks pass
    config.use_macd = False
    config.use_kdj = False
    config.use_rsi = False
    config.use_cci = False
    config.use_wma = False
    config.use_ema = False
    config.use_sma = False
    config.use_volume = False
    config.use_boll = False
    config.use_price_range = False 
    
    # 3. Run Selector
    selector = StockSelector(config)
    
    def progress_cb(msg, current, total):
        print(f"[Progress] {msg} ({current}/{total})")
        
    selector.set_progress_callback(progress_cb)
    
    results = selector.select_stocks()
    print(f"\nSelection Results: {len(results)}")
    for r in results:
        print(f" - {r['name']} ({r['code']})")
        
    print("=== Test Complete ===")

if __name__ == "__main__":
    test_selector_with_list()
