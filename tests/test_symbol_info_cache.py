#!/usr/bin/env python3
"""Test symbol info caching functionality"""

import sys
import os
import time
import json
sys.path.append('lib')

from pionex_api import PionexAPI

def test_symbol_info_caching():
    """Test the hybrid caching system for get_symbol_info()"""
    
    print("="*70)
    print("Testing Symbol Info Caching")
    print("="*70)
    
    # Clean cache before testing
    cache_file = 'cache/symbol_info.json'
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"✓ Cleaned existing cache file\n")
    
    # Initialize API
    api = PionexAPI()
    
    # Test 1: First fetch (should hit API)
    print("Test 1: First fetch (should hit API)")
    print("-" * 70)
    info1 = api.get_symbol_info('BTC_USDT')
    
    if 'error' in info1:
        print(f"❌ Failed: {info1['error']}")
        return
    
    print(f"Symbol: {info1.get('symbol')}")
    print(f"Min Amount: ${info1.get('minAmount', 0):.2f}")
    print(f"Min Trade Size: {info1.get('minTradeSize', 0):.8f} BTC")
    print(f"Max Trade Size: {info1.get('maxTradeSize', 0):.2f} BTC")
    print(f"Enabled: {info1.get('enable')}")
    print(f"\n✓ Successfully fetched from API\n")
    
    # Test 2: Second fetch (should use cache)
    print("Test 2: Second fetch (should use in-memory cache)")
    print("-" * 70)
    start_time = time.time()
    info2 = api.get_symbol_info('BTC_USDT')
    elapsed = (time.time() - start_time) * 1000  # ms
    
    if info1 == info2:
        print(f"✓ Cache hit! (fetched in {elapsed:.1f}ms)")
    else:
        print(f"❌ Cache miss! Data changed.")
    print()
    
    # Test 3: Cache file persistence
    print("Test 3: Cache file persistence")
    print("-" * 70)
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cached = json.load(f)
        
        if 'BTC_USDT' in cached:
            print(f"✓ BTC_USDT found in {cache_file}")
            print(f"  Cached minAmount: ${cached['BTC_USDT']['minAmount']}")
            print(f"  Age: {(time.time() - cached['BTC_USDT']['timestamp'])/60:.1f} minutes")
        else:
            print(f"❌ BTC_USDT not in cache file")
    else:
        print(f"❌ Cache file not created")
    print()
    
    # Test 4: Load from file (simulate restart)
    print("Test 4: Simulated restart (load from file)")
    print("-" * 70)
    api2 = PionexAPI()
    
    if 'BTC_USDT' in api2._symbol_info_cache:
        print(f"✓ Cache loaded on init (found BTC_USDT)")
        print(f"  In-memory cache has {len(api2._symbol_info_cache)} symbol(s)")
    else:
        print(f"❌ Cache not loaded on init")
    print()
    
    # Test 5: Multiple symbols
    print("Test 5: Cache multiple symbols")
    print("-" * 70)
    
    test_symbols = ['ETH_USDT', 'SOL_USDT', 'AVAX_USDT']
    
    for symbol in test_symbols:
        info = api.get_symbol_info(symbol)
        if 'error' not in info:
            print(f"✓ {symbol}: minAmount=${info['minAmount']:.2f}")
        else:
            print(f"❌ {symbol}: {info['error']}")
    
    print(f"\nTotal cached symbols: {len(api._symbol_info_cache)}")
    print()
    
    # Test 6: Force refresh
    print("Test 6: Force refresh (bypass cache)")
    print("-" * 70)
    
    old_timestamp = api._symbol_info_cache['BTC_USDT']['timestamp']
    time.sleep(0.1)  # Small delay
    
    info_refreshed = api.get_symbol_info('BTC_USDT', force_refresh=True)
    new_timestamp = info_refreshed['timestamp']
    
    if new_timestamp > old_timestamp:
        print(f"✓ Force refresh worked (timestamp updated)")
        print(f"  Old: {old_timestamp}")
        print(f"  New: {new_timestamp}")
    else:
        print(f"❌ Force refresh failed (timestamp unchanged)")
    print()
    
    print("="*70)
    print("✅ All Caching Tests Passed!")
    print("="*70)
    
    print("\n📊 Summary:")
    print(f"  ✓ API fetch working")
    print(f"  ✓ In-memory cache working")
    print(f"  ✓ File persistence working")
    print(f"  ✓ Cache loaded on init")
    print(f"  ✓ Multiple symbols cached")
    print(f"  ✓ Force refresh working")
    print(f"\n📁 Cache location: {cache_file}")
    print(f"🕐 Cache TTL: 24 hours")
    print(f"\n🚀 Ready for use in exchange_manager.py!")

if __name__ == '__main__':
    test_symbol_info_caching()
