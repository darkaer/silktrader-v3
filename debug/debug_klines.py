#!/usr/bin/env python3
import sys
sys.path.append('lib')
from pionex_api import PionexAPI
import json

api = PionexAPI()

# Test with different symbol formats
test_symbols = ['BTC_USDT', 'BTCUSDT', 'BTC/USDT']

for symbol in test_symbols:
    print(f"\n=== Testing symbol: {symbol} ===")
    result = api._request('GET', '/api/v1/market/klines', params={
        'symbol': symbol,
        'interval': '15m',
        'limit': 10
    })
    print(json.dumps(result, indent=2)[:500])  # Print first 500 chars

# Also test ticker to see symbol format
print("\n=== Testing ticker endpoint ===")
ticker = api._request('GET', '/api/v1/market/ticker', params={'symbol': 'BTC_USDT'})
print(json.dumps(ticker, indent=2)[:500])
