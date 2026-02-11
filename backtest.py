#!/usr/bin/env python3
"""
SilkTrader v3 - Backtesting CLI
Validate trading strategies on historical data
"""
import sys
import os
import argparse
import json
from datetime import datetime, timedelta

sys.path.append('lib')

from pionex_api import PionexAPI
from backtest_engine import BacktestEngine


def get_top_pairs(limit=20):
    """Get top trading pairs by volume
    
    Args:
        limit: Number of pairs to return
        
    Returns:
        List of pair names
    """
    print(f"🔍 Finding top {limit} trading pairs...")
    api = PionexAPI()
    
    # Get all USDT pairs
    symbols = api.get_symbols(quote='USDT')
    print(f"   Found {len(symbols)} USDT pairs")
    
    # Get 24h volume for each
    pair_volumes = []
    for symbol in symbols[:100]:  # Check first 100 to save time
        try:
            ticker = api.get_24h_ticker(symbol)
            if ticker and 'volume' in ticker:
                volume = float(ticker.get('volume', 0))
                pair_volumes.append((symbol, volume))
        except:
            continue
    
    # Sort by volume and take top N
    pair_volumes.sort(key=lambda x: x[1], reverse=True)
    top_pairs = [pair for pair, _ in pair_volumes[:limit]]
    
    print(f"   ✓ Selected top {len(top_pairs)} pairs by volume\n")
    return top_pairs


def run_backtest(args):
    """Run backtest with given arguments"""
    
    # Initialize engine
    engine = BacktestEngine(
        config_path=args.config,
        initial_balance=args.balance,
        trading_fee_percent=args.fee,
        slippage_percent=args.slippage
    )
    
    # Get pairs to test
    if args.pairs:
        pairs = args.pairs.split(',')
    elif args.top:
        pairs = get_top_pairs(args.top)
    else:
        # Default: top 10 pairs
        pairs = get_top_pairs(10)
    
    print(f"🎯 Selected pairs: {', '.join(pairs)}\n")
    
    # Calculate date range
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        # Default: last 7 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Run backtest
    results = engine.run_backtest(
        pairs=pairs,
        start_date=start_date,
        end_date=end_date,
        scan_interval_hours=args.scan_interval
    )
    
    # Print results
    if results:
        engine.print_results(results)
        
        # Export to JSON if requested
        if args.output:
            export_data = {
                'backtest_config': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'pairs': pairs,
                    'initial_balance': args.balance,
                    'trading_fee': args.fee,
                    'slippage': args.slippage,
                    'scan_interval_hours': args.scan_interval
                },
                'results': results
            }
            
            os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
            with open(args.output, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"💾 Results exported to: {args.output}")
    else:
        print("❌ Backtest failed - no results generated")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='SilkTrader v3 Backtesting System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick 1-day test with top 10 pairs
  python backtest.py --quick-test 1d
  
  # Test specific date range with custom pairs
  python backtest.py --start 2026-01-01 --end 2026-01-31 --pairs BTC_USDT,ETH_USDT,BNB_USDT
  
  # Test top 20 pairs over 1 week with $500 balance
  python backtest.py --top 20 --balance 500 --quick-test 1w
  
  # Full test with custom parameters and export
  python backtest.py --start 2025-12-01 --end 2026-01-31 --balance 1000 --output results/backtest.json
        """
    )
    
    # Date range
    date_group = parser.add_argument_group('Date Range')
    date_group.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    date_group.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    date_group.add_argument('--quick-test', type=str, choices=['1d', '3d', '1w', '2w', '1m'],
                           help='Quick test period (1d=1 day, 1w=1 week, etc.)')
    
    # Pair selection
    pair_group = parser.add_argument_group('Pair Selection')
    pair_group.add_argument('--pairs', type=str, 
                           help='Comma-separated list of pairs (e.g., BTC_USDT,ETH_USDT)')
    pair_group.add_argument('--top', type=int, metavar='N',
                           help='Use top N pairs by 24h volume')
    
    # Trading parameters
    trading_group = parser.add_argument_group('Trading Parameters')
    trading_group.add_argument('--balance', type=float, default=1000.0,
                              help='Initial balance in USDT (default: 1000)')
    trading_group.add_argument('--fee', type=float, default=0.05,
                              help='Trading fee percent (default: 0.05)')
    trading_group.add_argument('--slippage', type=float, default=0.1,
                              help='Slippage percent (default: 0.1)')
    trading_group.add_argument('--scan-interval', type=int, default=1,
                              help='Hours between market scans (default: 1)')
    
    # Configuration
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('--config', type=str, default='credentials/pionex.json',
                             help='Path to config file (default: credentials/pionex.json)')
    config_group.add_argument('--output', type=str,
                             help='Export results to JSON file')
    
    args = parser.parse_args()
    
    # Handle quick test shortcuts
    if args.quick_test:
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        days_map = {
            '1d': 1,
            '3d': 3,
            '1w': 7,
            '2w': 14,
            '1m': 30
        }
        
        days = days_map.get(args.quick_test, 7)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        args.start = start_date
        args.end = end_date
        
        print(f"⚡ Quick Test Mode: Testing last {args.quick_test}\n")
    
    # Validate date range
    if args.start and args.end:
        try:
            start_dt = datetime.strptime(args.start, '%Y-%m-%d')
            end_dt = datetime.strptime(args.end, '%Y-%m-%d')
            
            if start_dt >= end_dt:
                print("❌ Error: Start date must be before end date")
                return 1
            
            if end_dt > datetime.now():
                print("⚠️  Warning: End date is in the future, using today instead")
                args.end = datetime.now().strftime('%Y-%m-%d')
                
        except ValueError as e:
            print(f"❌ Error: Invalid date format - {e}")
            return 1
    
    try:
        return run_backtest(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Backtest error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
