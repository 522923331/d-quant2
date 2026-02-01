
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from dquant2.core.data.stock_lists import StockListManager
from dquant2.core.data.download import BatchDownloader
from dquant2.core.data.storage import DataFileManager

def test_stock_lists():
    print("\n=== Testing Stock List Manager ===")
    manager = StockListManager()
    lists = manager.get_available_lists()
    print(f"Available lists: {lists}")
    
    if '上证50成分股' in lists:
        stocks = manager.load_list('上证50成分股')
        print(f"Loaded {len(stocks)} stocks from 上证50成分股")
        print(f"Sample: {stocks[:3]}")
    else:
        print("上证50成分股 list not found!")

def test_batch_download():
    print("\n=== Testing Batch Download ===")
    
    # Test parameters
    # Download just 2 stocks for testing
    test_stocks = ['000001.SZ', '600519.SH'] 
    
    downloader = BatchDownloader()
    
    print("Testing AkShare download (Daily)...")
    downloader.download_bulk(
        stock_list=test_stocks,
        period='1d',
        start_date='20240101',
        end_date='20240110',
        data_provider='akshare',
        log_callback=lambda msg: print(f"[Log] {msg}")
    )
    
    print("\nTesting Baostock download (5m)...")
    downloader.download_bulk(
        stock_list=['000001', '600519'], 
        period='5m',
        start_date='20240101',
        end_date='20240105',
        data_provider='baostock',
        log_callback=lambda msg: print(f"[Log] {msg}")
    )

def verify_files():
    print("\n=== Verifying Files ===")
    fm = DataFileManager()
    files = fm.list_files()
    print(f"Found {len(files)} files.")
    for f in files:
        print(f" - {f['filename']} ({f['size']} bytes)")

if __name__ == "__main__":
    try:
        test_stock_lists()
        # Clean up code format for test
        test_batch_download()
        verify_files()
    except Exception as e:
        logger.exception("Test failed")
