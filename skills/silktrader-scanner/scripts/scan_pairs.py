#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../lib'))

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup, format_indicators_for_llm
import argparse
from datetime import datetime
import time

def scan_market(min_score=5, limit=5, timeframe='15M'):
    """Scan all pairs and return top opportunities"""
    print(f"🔍 SilkTrader v3 Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Settings: min_score={min_score}, limit={limit}, timeframe={timeframe}\n")
    
    # Initialize API
    api = PionexAPI()
    
    # Get all USDT pairs
    print("📊 Fetching trading pairs...")
    symbols = api.get_symbols(quote='USDT')
    print(f"✓ Found {len(symbols)} USDT pairs\n")
    
    # Scan all pairs
    print("🔬 Analyzing pairs...")
    results = []
    errors = 0
    
    for i, symbol in enumerate(symbols, 1):
        try:
            # Progress indicator
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(symbols)} pairs analyzed...")
            
            # Get candles
            klines = api.get_klines(symbol, timeframe, 100)
            
            if len(klines) < 50:  # Need enough data for indicators
                continue
            
            # Calculate indicators
            indicators = calc_all_indicators(klines)
            score = score_setup(indicators)
            
            # Store if meets minimum score
            if score >= min_score:
                results.append({
                    'pair': symbol,
                    'score': score,
                    'indicators': indicators
                })
            
            # Rate limiting - don't hammer the API
            time.sleep(0.1)
            
        except Exception as e:
            errors += 1
            if errors < 5:  # Only show first few errors
                print(f"   ⚠️  Error with {symbol}: {e}")
            continue
    
    print(f"\n✓ Scan complete: {len(results)} opportunities found")
    if errors > 0:
        print(f"⚠️  {errors} pairs skipped due to errors\n")
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    top_results = results[:limit]
    
    # Output formatted results
    print("=" * 70)
    print(f"🎯 TOP {len(top_results)} TRADING OPPORTUNITIES")
    print("=" * 70)
    print()
    
    for i, result in enumerate(top_results, 1):
        formatted = format_indicators_for_llm(
            result['pair'], 
            result['indicators'], 
            result['score']
        )
        print(f"{i}. {formatted}")
        print()
    
    return top_results

def main():
    parser = argparse.ArgumentParser(description='SilkTrader v3 Market Scanner')
    parser.add_argument('--min-score', type=int, default=5, help='Minimum setup score (0-7)')
    parser.add_argument('--limit', type=int, default=5, help='Number of top pairs to return')
    parser.add_argument('--timeframe', default='15M', help='Candle interval (1M, 5M, 15M, 30M, 60M, 4H, 1D)')
    
    args = parser.parse_args()
    
    try:
        results = scan_market(
            min_score=args.min_score,
            limit=args.limit,
            timeframe=args.timeframe
        )
        
        print("=" * 70)
        print("✅ Scanner completed successfully")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scanner interrupted by user")
    except Exception as e:
        print(f"\n❌ Scanner error: {e}")
        raise

if __name__ == '__main__':
    main()
