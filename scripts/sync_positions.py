#!/usr/bin/env python3
"""
Sync open trades from database to position monitor
Loads all open trades and creates positions.json for monitoring
"""
import sys
import json
import os

sys.path.insert(0, 'lib')

from database import TradingDatabase

def sync_positions(db_path='data/silktrader.db', output_path='data/positions.json'):
    """Sync open trades from database to positions file
    
    Args:
        db_path: Path to database file
        output_path: Path to output positions.json
    """
    try:
        # Connect to database
        db = TradingDatabase(db_path)
        
        # Get all open trades
        trades = db.get_trades(status='OPEN')
        
        if not trades:
            print('ℹ️  No open trades found in database')
            db.close()
            return
        
        print(f'\n🔄 Syncing {len(trades)} open trades from database...')
        print('='*70)
        
        # Convert to position monitor format
        positions = []
        for trade in trades:
            # Calculate fallback stop/TP if not set (2% risk, 3% reward)
            entry = trade['entry_price']
            stop_loss = trade['stop_loss'] if trade['stop_loss'] else entry * 0.98
            take_profit = trade['take_profit'] if trade['take_profit'] else entry * 1.03
            
            position = {
                'trade_id': trade['trade_id'],
                'pair': trade['pair'],
                'entry': entry,
                'quantity': trade['quantity'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'opened_at': trade['entry_time'],
                'id': trade['trade_id']
            }
            positions.append(position)
            
            # Display info
            print(f'\n✅ {trade["pair"]}')
            print(f'   Trade ID: {trade["trade_id"]}')
            print(f'   Entry: ${entry:.6f} | Qty: {trade["quantity"]:.6f}')
            print(f'   Stop: ${stop_loss:.6f} | TP: ${take_profit:.6f}')
            
            # Calculate potential P&L
            risk = ((stop_loss - entry) / entry) * 100
            reward = ((take_profit - entry) / entry) * 100
            print(f'   Risk: {risk:.2f}% | Reward: {reward:.2f}% | R:R = 1:{abs(reward/risk):.2f}')
        
        # Save to positions.json
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(positions, f, indent=2)
        
        print(f'\n{'='*70}')
        print(f'✅ Successfully synced {len(positions)} positions to {output_path}')
        print(f'\n🚀 Ready to monitor! Run:')
        print(f'   python monitor_positions.py --once')
        print(f'   python monitor_positions.py --interval 30')
        print('='*70 + '\n')
        
        db.close()
        
    except FileNotFoundError:
        print(f'❌ Error: Database file not found at {db_path}')
        print(f'   Run the trading bot first to create trades')
        sys.exit(1)
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync open trades from database to position monitor')
    parser.add_argument('--db', default='data/silktrader.db', help='Database path')
    parser.add_argument('--output', default='data/positions.json', help='Output positions file')
    
    args = parser.parse_args()
    
    sync_positions(args.db, args.output)
