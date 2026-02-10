#!/usr/bin/env python3
"""Test indicator calculations to debug failures"""
import sys
sys.path.insert(0, '.')

from lib.pionex_api import PionexAPI
from lib.indicators import calc_all_indicators

print("Testing indicator calculations...\n")

# Initialize API
api = PionexAPI('credentials/pionex.json')

# Get symbols
symbols = api.get_symbols(quote='USDT')
print(f"Found {len(symbols)} USDT pairs\n")

# Test first 10 pairs that return klines
tested = 0
success = 0
failed = 0
errors = {}

for symbol in symbols:
    if tested >= 10:
        break
        
    # Get klines
    klines = api.get_klines(symbol, '15M', 100)
    
    if not klines:
        continue
        
    tested += 1
    print(f"\n[{tested}] {symbol}: {len(klines)} candles")
    
    # Try indicators
    try:
        indicators = calc_all_indicators(klines)
        success += 1
        print(f"  ✅ Success! Price={indicators['price']:.6f}, RSI={indicators['rsi']:.1f}")
    except Exception as e:
        failed += 1
        error_msg = str(e)
        errors[error_msg] = errors.get(error_msg, 0) + 1
        print(f"  ❌ Failed: {error_msg}")

print(f"\n{'='*60}")
print(f"RESULTS: {success}/{tested} successful, {failed}/{tested} failed")
print(f"{'='*60}")

if errors:
    print("\nError breakdown:")
    for error, count in sorted(errors.items(), key=lambda x: -x[1]):
        print(f"  [{count}x] {error}")
