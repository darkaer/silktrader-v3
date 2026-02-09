#!/usr/bin/env python3
import sys
sys.path.append('lib')

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup, format_indicators_for_llm

def test_api_connection():
    print("Testing Pionex API connection...")
    api = PionexAPI()
    
    # Test 1: Get symbols
    symbols = api.get_symbols(quote='USDT', min_volume=1000000)
    print(f"✓ Found {len(symbols)} USDT trading pairs")
    
    # Test 2: Get klines for BTC
    if 'BTC_USDT' in symbols:
        klines = api.get_klines('BTC_USDT', '15m', 100)
        print(f"✓ Retrieved {len(klines)} candles for BTC_USDT")
        
        # Test 3: Calculate indicators
        indicators = calc_all_indicators(klines)
        score = score_setup(indicators)
        print(f"✓ Calculated indicators, setup score: {score}/7")
        
        # Test 4: Format for LLM
        formatted = format_indicators_for_llm('BTC_USDT', indicators, score)
        print("\n--- LLM Format Test ---")
        print(formatted)
        print("--- End ---\n")
    
    print("✓ Foundation tests complete!")

if __name__ == '__main__':
    test_api_connection()
