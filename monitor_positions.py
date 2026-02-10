#!/usr/bin/env python3
"""
SilkTrader v3 - Position Monitor
Continuously monitors open positions and manages exits
"""
import sys
import os
import time
import json
from datetime import datetime

sys.path.append('lib')
sys.path.append('skills/silktrader-trader/scripts')

from pionex_api import PionexAPI
from indicators import calc_all_indicators
from risk_manager import RiskManager
from database import TradingDatabase
from telegram_notifier import TelegramNotifier

class PositionMonitor:
    """Monitor and manage open trading positions"""
    
    def __init__(self, config_path='credentials/pionex.json', dry_run=True, db=None):
        """Initialize position monitor
        
        Args:
            config_path: Path to credentials file
            dry_run: If True, don't execute real trades
            db: Optional TradingDatabase instance for logging
        """
        self.api = PionexAPI(config_path)
        self.risk_mgr = RiskManager(config_path)
        self.dry_run = dry_run
        self.db = db
        
        # Initialize Telegram notifier
        self.telegram = TelegramNotifier(config_path, enabled=True)
        
        # Load positions from file or API
        self.positions_file = 'data/positions.json'
        self.positions = self.load_positions()
        
        # Statistics
        self.total_pnl = 0.0
        self.wins = 0
        self.losses = 0
        self.closed_today = []
        
        print(f"\n{'='*70}")
        print(f"📊 SilkTrader v3 - Position Monitor")
        print(f"{'='*70}")
        print(f"Mode: {'DRY RUN' if dry_run else '🔴 LIVE TRADING'}")
        print(f"Database: {'✅ Connected' if db else '⚠️  Not connected'}")
        print(f"Telegram: {'✅ Enabled' if self.telegram.enabled else '⚠️  Disabled'}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Open Positions: {len(self.positions)}")
        print(f"{'='*70}\n")
    
    def load_positions(self):
        """Load positions from file"""
        if not os.path.exists(self.positions_file):
            return []
        
        try:
            with open(self.positions_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_positions(self):
        """Save positions to file"""
        os.makedirs('data', exist_ok=True)
        with open(self.positions_file, 'w') as f:
            json.dump(self.positions, f, indent=2)
    
    def add_position(self, position):
        """Add new position to monitor
        
        Args:
            position: Dict with keys: pair, entry, quantity, stop_loss, take_profit, trade_id (optional)
        """
        position['opened_at'] = datetime.now().isoformat()
        position['id'] = f"{position['pair']}_{int(time.time())}"
        
        # If trade_id not provided, use the generated id
        if 'trade_id' not in position:
            position['trade_id'] = position['id']
        
        self.positions.append(position)
        self.save_positions()
        print(f"✅ Added position: {position['pair']} (Trade ID: {position['trade_id']})")
    
    def get_current_price(self, pair):
        """Get current market price"""
        try:
            klines = self.api.get_klines(pair, '1M', 1)
            if klines:
                return klines[0]['close']
        except:
            pass
        return None
    
    def log_position_snapshot(self, position, current_price, pnl_usdt, pnl_pct, trailing_stop):
        """Log position snapshot to database
        
        Args:
            position: Position dict
            current_price: Current market price
            pnl_usdt: Unrealized P&L in USDT
            pnl_pct: Unrealized P&L percentage
            trailing_stop: Current trailing stop price
        """
        if not self.db:
            return
        
        try:
            snapshot = {
                'trade_id': position.get('trade_id', position['id']),
                'pair': position['pair'],
                'current_price': current_price,
                'entry_price': position['entry'],
                'quantity': position['quantity'],
                'unrealized_pnl': pnl_usdt,
                'pnl_percent': pnl_pct,
                'stop_loss': position.get('stop_loss'),
                'take_profit': position.get('take_profit'),
                'trailing_stop': trailing_stop,
                'snapshot_time': datetime.now().isoformat()
            }
            self.db.insert_position_snapshot(snapshot)
        except Exception as e:
            print(f"   ⚠️  Snapshot logging failed: {e}")
    
    def calculate_duration(self, opened_at):
        """Calculate position duration string
        
        Args:
            opened_at: ISO format datetime string
            
        Returns:
            Duration string like '2h 15m' or '45m'
        """
        try:
            opened = datetime.fromisoformat(opened_at)
            duration = datetime.now() - opened
            
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except:
            return None
    
    def check_position(self, position):
        """Check single position for exit conditions"""
        pair = position['pair']
        entry = position['entry']
        quantity = position['quantity']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']
        position_id = position['id']
        
        # Get current price
        current_price = self.get_current_price(pair)
        
        if current_price is None:
            print(f"⚠️  {pair}: Unable to get current price")
            return None
        
        # Calculate P&L
        pnl_pct = ((current_price - entry) / entry) * 100
        pnl_usdt = (current_price - entry) * quantity
        position_value = current_price * quantity
        
        # Check trailing stop with position_id
        trailing_active = position.get('trailing_active', False)
        trailing_stop = position.get('trailing_stop', stop_loss)
        
        # Calculate ATR from price range (simplified)
        atr = (take_profit - entry) / 3
        
        if not trailing_active:
            # Check if should activate trailing stop
            should_activate, new_stop = self.risk_mgr.calculate_trailing_stop(
                position_id, entry, current_price, atr, 'BUY'
            )
            
            if should_activate:
                trailing_active = True
                trailing_stop = new_stop
                position['trailing_active'] = True
                position['trailing_stop'] = trailing_stop
                print(f"   🎯 {pair}: Trailing stop ACTIVATED at ${trailing_stop:.6f}")
                
                # Send Telegram notification
                self.telegram.send_trailing_stop_activated(
                    pair=pair,
                    current_price=current_price,
                    new_stop=trailing_stop,
                    profit_pct=pnl_pct
                )
        else:
            # Update trailing stop if price moved up
            should_update, new_stop = self.risk_mgr.calculate_trailing_stop(
                position_id, entry, current_price, atr, 'BUY'
            )
            
            if should_update and new_stop > trailing_stop:
                old_stop = trailing_stop
                trailing_stop = new_stop
                position['trailing_stop'] = trailing_stop
                print(f"   📈 {pair}: Trailing stop moved to ${trailing_stop:.6f}")
                
                # Send Telegram notification
                self.telegram.send_trailing_stop_updated(
                    pair=pair,
                    old_stop=old_stop,
                    new_stop=trailing_stop,
                    profit_pct=pnl_pct
                )
        
        # Log position snapshot to database
        self.log_position_snapshot(position, current_price, pnl_usdt, pnl_pct, trailing_stop)
        
        # Status display
        status = "🟢" if pnl_usdt > 0 else "🔴"
        
        print(f"{status} {pair}")
        print(f"   Entry: ${entry:.6f} → Current: ${current_price:.6f}")
        print(f"   P&L: {pnl_pct:+.2f}% (${pnl_usdt:+.2f})")
        print(f"   Value: ${position_value:.2f}")
        print(f"   Stop: ${trailing_stop:.6f} | Target: ${take_profit:.6f}")
        
        # Check exit conditions
        exit_reason = None
        exit_price = None
        
        # Stop loss hit
        if current_price <= trailing_stop:
            exit_reason = "STOP LOSS"
            exit_price = trailing_stop
            print(f"   🛑 STOP LOSS HIT at ${trailing_stop:.6f}")
        
        # Take profit hit
        elif current_price >= take_profit:
            exit_reason = "TAKE PROFIT"
            exit_price = take_profit
            print(f"   💰 TAKE PROFIT HIT at ${take_profit:.6f}")
        
        # Return exit signal if needed
        if exit_reason:
            return {
                'position': position,
                'reason': exit_reason,
                'exit_price': exit_price,
                'pnl_usdt': pnl_usdt,
                'pnl_pct': pnl_pct
            }
        
        print()
        return None
    
    def close_position(self, exit_signal):
        """Close a position and log to database"""
        position = exit_signal['position']
        pair = position['pair']
        quantity = position['quantity']
        reason = exit_signal['reason']
        exit_price = exit_signal['exit_price']
        pnl_usdt = exit_signal['pnl_usdt']
        pnl_pct = exit_signal['pnl_pct']
        position_id = position['id']
        trade_id = position.get('trade_id', position_id)
        
        # Calculate duration
        duration = self.calculate_duration(position.get('opened_at'))
        
        print(f"\n{'='*70}")
        print(f"🚪 CLOSING POSITION: {pair}")
        print(f"{'='*70}")
        print(f"Reason: {reason}")
        print(f"Entry: ${position['entry']:.6f}")
        print(f"Exit: ${exit_price:.6f}")
        print(f"Quantity: {quantity:.6f}")
        print(f"P&L: {pnl_pct:+.2f}% (${pnl_usdt:+.2f})")
        if duration:
            print(f"Duration: {duration}")
        print(f"{'='*70}\n")
        
        if not self.dry_run:
            try:
                # Execute sell order
                print(f"⚡ Executing SELL order...")
                order = self.api.place_order(pair, 'SELL', 'MARKET', quantity)
                
                if 'error' not in order:
                    print(f"✅ Position closed successfully!")
                else:
                    print(f"❌ Failed to close: {order['error']}")
                    return False
            except Exception as e:
                print(f"❌ Error closing position: {e}")
                return False
        else:
            print(f"🔔 DRY RUN: Would SELL {quantity:.6f} {pair} @ ${exit_price:.6f}")
        
        # Send Telegram notification
        self.telegram.send_position_closed(
            pair=pair,
            reason=reason,
            entry_price=position['entry'],
            exit_price=exit_price,
            quantity=quantity,
            pnl_usdt=pnl_usdt,
            pnl_pct=pnl_pct,
            duration=duration
        )
        
        # Update database with exit data
        if self.db:
            try:
                exit_data = {
                    'exit_price': exit_price,
                    'exit_time': datetime.now().isoformat(),
                    'entry_time': position.get('opened_at', datetime.now().isoformat()),
                    'realized_pnl': pnl_usdt,
                    'pnl_percent': pnl_pct,
                    'status': 'CLOSED'
                }
                self.db.update_trade_exit(trade_id, exit_data)
                print(f"📝 Trade exit logged to database: {trade_id}")
            except Exception as e:
                print(f"⚠️  Database logging failed: {e}")
        
        # Clear position tracking in risk manager
        self.risk_mgr.clear_position_tracking(position_id)
        
        # Update statistics
        self.total_pnl += pnl_usdt
        if pnl_usdt > 0:
            self.wins += 1
        else:
            self.losses += 1
        
        # Log closed trade
        self.closed_today.append({
            'trade_id': trade_id,
            'pair': pair,
            'entry': position['entry'],
            'exit': exit_price,
            'quantity': quantity,
            'pnl_usdt': pnl_usdt,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'opened_at': position.get('opened_at'),
            'closed_at': datetime.now().isoformat()
        })
        
        # Remove from positions
        self.positions = [p for p in self.positions if p['id'] != position_id]
        self.save_positions()
        
        return True
    
    def check_all_positions(self):
        """Check all open positions"""
        if not self.positions:
            print("ℹ️  No open positions to monitor\n")
            return
        
        print(f"📊 Checking {len(self.positions)} open position(s)...\n")
        
        exits_to_process = []
        
        for position in self.positions:
            exit_signal = self.check_position(position)
            if exit_signal:
                exits_to_process.append(exit_signal)
        
        # Process exits
        for exit_signal in exits_to_process:
            self.close_position(exit_signal)
        
        # Save updated positions
        self.save_positions()
    
    def print_summary(self):
        """Print session summary"""
        print(f"\n{'='*70}")
        print(f"📈 SESSION SUMMARY")
        print(f"{'='*70}")
        print(f"Open Positions: {len(self.positions)}")
        print(f"Closed Today: {len(self.closed_today)}")
        
        if self.closed_today:
            print(f"\nClosed Trades:")
            for trade in self.closed_today:
                status = "✅" if trade['pnl_usdt'] > 0 else "❌"
                print(f"  {status} {trade['pair']}: {trade['pnl_pct']:+.2f}% (${trade['pnl_usdt']:+.2f}) - {trade['reason']}")
        
        if self.wins + self.losses > 0:
            win_rate = (self.wins / (self.wins + self.losses)) * 100
            print(f"\nStatistics:")
            print(f"  Win Rate: {win_rate:.1f}% ({self.wins}W / {self.losses}L)")
            print(f"  Total P&L: ${self.total_pnl:+.2f}")
            
            if self.wins > 0 and self.losses > 0:
                avg_win = sum(t['pnl_usdt'] for t in self.closed_today if t['pnl_usdt'] > 0) / self.wins
                avg_loss = abs(sum(t['pnl_usdt'] for t in self.closed_today if t['pnl_usdt'] < 0) / self.losses)
                profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
                print(f"  Avg Win: ${avg_win:.2f}")
                print(f"  Avg Loss: ${avg_loss:.2f}")
                print(f"  Profit Factor: {profit_factor:.2f}")
        
        if self.db:
            print(f"\n📊 Database Statistics:")
            try:
                stats = self.db.get_database_stats()
                print(f"  Total trades logged: {stats['trades']}")
                print(f"  Position snapshots: {stats['position_snapshots']}")
            except:
                pass
        
        print(f"{'='*70}\n")
    
    def run_once(self):
        """Run single monitoring cycle"""
        print(f"\n{'─'*70}")
        print(f"🔄 Monitoring cycle at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'─'*70}\n")
        
        self.check_all_positions()
        
        print(f"{'─'*70}")
        print(f"✅ Monitoring cycle complete")
        print(f"{'─'*70}\n")
    
    def run_continuous(self, interval_seconds=30):
        """Run monitor continuously"""
        print(f"🚀 Starting continuous monitoring (check every {interval_seconds}s)")
        print(f"   Press Ctrl+C to stop\n")
        
        try:
            while True:
                self.run_once()
                
                # Wait for next check
                if self.positions:
                    print(f"⏳ Next check in {interval_seconds}s...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Monitor stopped by user")
            self.print_summary()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SilkTrader v3 Position Monitor')
    parser.add_argument('--live', action='store_true', help='Live trading mode')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--add', type=str, help='Add position: PAIR,ENTRY,QUANTITY,SL,TP')
    parser.add_argument('--no-db', action='store_true', help='Disable database logging')
    
    args = parser.parse_args()
    
    # Initialize database if enabled
    db = None
    if not args.no_db:
        try:
            db = TradingDatabase('data/silktrader.db')
        except Exception as e:
            print(f"⚠️  Database initialization failed: {e}")
            print(f"   Continuing without database logging...\n")
    
    monitor = PositionMonitor(dry_run=not args.live, db=db)
    
    # Add position manually if specified
    if args.add:
        try:
            parts = args.add.split(',')
            position = {
                'pair': parts[0],
                'entry': float(parts[1]),
                'quantity': float(parts[2]),
                'stop_loss': float(parts[3]),
                'take_profit': float(parts[4])
            }
            monitor.add_position(position)
            print(f"✅ Position added: {position['pair']}\n")
        except Exception as e:
            print(f"❌ Error adding position: {e}")
            print("Format: PAIR,ENTRY,QUANTITY,STOP_LOSS,TAKE_PROFIT")
            print("Example: BTC_USDT,50000,0.01,48500,52500")
            if db:
                db.close()
            return
    
    try:
        if args.once:
            monitor.run_once()
        else:
            monitor.run_continuous(interval_seconds=args.interval)
    finally:
        if db:
            db.close()
            print("📊 Database connection closed")

if __name__ == '__main__':
    main()
