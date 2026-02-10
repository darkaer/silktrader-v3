#!/usr/bin/env python3
"""
SilkTrader v3 - Overnight Trading Analysis
Analyze paper trading performance from overnight session
"""
import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.append('lib')
from pionex_api import PionexAPI

class OvernightAnalyzer:
    """Analyze overnight trading session performance"""
    
    def __init__(self, db_path='data/silktrader.db', positions_file='data/positions.json'):
        """Initialize analyzer
        
        Args:
            db_path: Path to SQLite database
            positions_file: Path to positions JSON file
        """
        self.db_path = db_path
        self.positions_file = positions_file
        self.api = None
        
        # Try to initialize API for current prices (optional)
        try:
            self.api = PionexAPI('credentials/pionex.json')
        except:
            print("⚠️  Could not initialize API - unrealized P&L will be estimated\n")
    
    def get_db_connection(self):
        """Get database connection"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found: {self.db_path}")
            sys.exit(1)
        return sqlite3.connect(self.db_path)
    
    def load_open_positions(self) -> List[Dict]:
        """Load open positions from file"""
        if not os.path.exists(self.positions_file):
            return []
        
        try:
            with open(self.positions_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def get_current_price(self, pair: str) -> Optional[float]:
        """Get current market price for a pair"""
        if not self.api:
            return None
        
        try:
            klines = self.api.get_klines(pair, '1M', 1)
            if klines:
                return klines[0]['close']
        except:
            pass
        return None
    
    def print_header(self):
        """Print analysis header"""
        print("\n" + "="*80)
        print("📊 SilkTrader v3 - Overnight Trading Analysis")
        print("="*80)
        print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {self.db_path}")
        print("="*80 + "\n")
    
    def analyze_closed_trades(self, hours_back: int = 24) -> Dict:
        """Analyze closed trades from last N hours
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            Dict with trade statistics
        """
        conn = self.get_db_connection()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        
        query = """
        SELECT 
            trade_id, pair, entry_price, exit_price, quantity,
            realized_pnl, pnl_percent, entry_time, exit_time,
            confidence_score, paper_trading
        FROM trades
        WHERE status = 'CLOSED'
            AND exit_time >= ?
        ORDER BY exit_time DESC
        """
        
        cursor = conn.execute(query, (cutoff_time,))
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {
                'total_trades': 0,
                'trades': [],
                'total_pnl': 0,
                'avg_pnl': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'best_trade': None,
                'worst_trade': None
            }
        
        # Process trades
        trade_list = []
        total_pnl = 0
        wins = 0
        losses = 0
        
        for t in trades:
            trade_dict = {
                'trade_id': t[0],
                'pair': t[1],
                'entry_price': t[2],
                'exit_price': t[3],
                'quantity': t[4],
                'pnl': t[5],
                'pnl_pct': t[6],
                'entry_time': t[7],
                'exit_time': t[8],
                'confidence': t[9],
                'paper': t[10]
            }
            trade_list.append(trade_dict)
            total_pnl += t[5] if t[5] else 0
            
            if t[5] and t[5] > 0:
                wins += 1
            else:
                losses += 1
        
        win_rate = (wins / len(trades)) * 100 if trades else 0
        avg_pnl = total_pnl / len(trades) if trades else 0
        
        # Best and worst trades
        best_trade = max(trade_list, key=lambda x: x['pnl'] or 0) if trade_list else None
        worst_trade = min(trade_list, key=lambda x: x['pnl'] or 0) if trade_list else None
        
        return {
            'total_trades': len(trades),
            'trades': trade_list,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'best_trade': best_trade,
            'worst_trade': worst_trade
        }
    
    def analyze_open_positions(self) -> Dict:
        """Analyze currently open positions
        
        Returns:
            Dict with open position statistics
        """
        positions = self.load_open_positions()
        
        if not positions:
            return {
                'total_positions': 0,
                'positions': [],
                'total_unrealized_pnl': 0,
                'best_position': None,
                'worst_position': None
            }
        
        position_stats = []
        total_unrealized = 0
        
        for pos in positions:
            current_price = self.get_current_price(pos['pair'])
            
            if current_price:
                unrealized_pnl = (current_price - pos['entry']) * pos['quantity']
                unrealized_pct = ((current_price - pos['entry']) / pos['entry']) * 100
            else:
                # Estimate with stop loss / take profit midpoint
                unrealized_pnl = 0
                unrealized_pct = 0
            
            position_stats.append({
                'pair': pos['pair'],
                'entry': pos['entry'],
                'current': current_price,
                'quantity': pos['quantity'],
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pct': unrealized_pct,
                'stop_loss': pos.get('stop_loss'),
                'take_profit': pos.get('take_profit'),
                'opened_at': pos.get('opened_at'),
                'trailing_active': pos.get('trailing_active', False),
                'trailing_stop': pos.get('trailing_stop')
            })
            
            total_unrealized += unrealized_pnl
        
        best_pos = max(position_stats, key=lambda x: x['unrealized_pnl']) if position_stats else None
        worst_pos = min(position_stats, key=lambda x: x['unrealized_pnl']) if position_stats else None
        
        return {
            'total_positions': len(positions),
            'positions': position_stats,
            'total_unrealized_pnl': total_unrealized,
            'best_position': best_pos,
            'worst_position': worst_pos
        }
    
    def analyze_scanner_performance(self, hours_back: int = 24) -> Dict:
        """Analyze scanner effectiveness
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            Dict with scanner statistics
        """
        conn = self.get_db_connection()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        
        query = """
        SELECT 
            COUNT(*) as total_scans,
            AVG(score) as avg_score,
            MAX(score) as max_score,
            MIN(score) as min_score
        FROM scan_results
        WHERE scan_time >= ?
        """
        
        cursor = conn.execute(query, (cutoff_time,))
        result = cursor.fetchone()
        
        # Get most scanned pairs
        pair_query = """
        SELECT pair, COUNT(*) as scan_count, AVG(score) as avg_score
        FROM scan_results
        WHERE scan_time >= ?
        GROUP BY pair
        ORDER BY scan_count DESC
        LIMIT 5
        """
        
        cursor = conn.execute(pair_query, (cutoff_time,))
        top_pairs = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_scans': result[0] if result else 0,
            'avg_score': result[1] if result else 0,
            'max_score': result[2] if result else 0,
            'min_score': result[3] if result else 0,
            'top_pairs': [(p[0], p[1], p[2]) for p in top_pairs] if top_pairs else []
        }
    
    def print_closed_trades_summary(self, stats: Dict):
        """Print closed trades summary"""
        print("🔒 CLOSED TRADES (Last 24 Hours)")
        print("-" * 80)
        
        if stats['total_trades'] == 0:
            print("No closed trades in the last 24 hours\n")
            return
        
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Wins: {stats['wins']} | Losses: {stats['losses']} | Win Rate: {stats['win_rate']:.1f}%")
        print(f"Total P&L: ${stats['total_pnl']:.2f}")
        print(f"Avg P&L per Trade: ${stats['avg_pnl']:.2f}\n")
        
        if stats['best_trade']:
            bt = stats['best_trade']
            print(f"🏆 Best Trade: {bt['pair']} - ${bt['pnl']:.2f} ({bt['pnl_pct']:+.2f}%)")
        
        if stats['worst_trade']:
            wt = stats['worst_trade']
            print(f"📉 Worst Trade: {wt['pair']} - ${wt['pnl']:.2f} ({wt['pnl_pct']:+.2f}%)\n")
        
        # Show recent trades
        print("Recent Closed Trades:")
        for i, trade in enumerate(stats['trades'][:10], 1):
            status_emoji = "✅" if trade['pnl'] > 0 else "❌"
            exit_time = datetime.fromisoformat(trade['exit_time']).strftime('%H:%M:%S')
            print(f"  {status_emoji} {trade['pair']}: ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%) - {exit_time}")
        
        if len(stats['trades']) > 10:
            print(f"  ... and {len(stats['trades']) - 10} more trades")
        
        print()
    
    def print_open_positions_summary(self, stats: Dict):
        """Print open positions summary"""
        print("📈 OPEN POSITIONS (Current)")
        print("-" * 80)
        
        if stats['total_positions'] == 0:
            print("No open positions\n")
            return
        
        print(f"Total Open: {stats['total_positions']}")
        print(f"Total Unrealized P&L: ${stats['total_unrealized_pnl']:.2f}\n")
        
        for pos in stats['positions']:
            status_emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
            trailing_emoji = "🎯" if pos['trailing_active'] else ""
            
            current_str = f"${pos['current']:.6f}" if pos['current'] else "N/A"
            pnl_str = f"${pos['unrealized_pnl']:+.2f} ({pos['unrealized_pct']:+.2f}%)" if pos['current'] else "N/A"
            
            print(f"{status_emoji} {trailing_emoji} {pos['pair']}")
            print(f"   Entry: ${pos['entry']:.6f} → Current: {current_str}")
            print(f"   Unrealized P&L: {pnl_str}")
            
            if pos['trailing_active']:
                print(f"   Trailing Stop: ${pos['trailing_stop']:.6f}")
            else:
                print(f"   Stop Loss: ${pos['stop_loss']:.6f} | Take Profit: ${pos['take_profit']:.6f}")
            
            # Calculate duration
            if pos['opened_at']:
                opened = datetime.fromisoformat(pos['opened_at'])
                duration = datetime.now() - opened
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                print(f"   Duration: {hours}h {minutes}m")
            
            print()
    
    def print_scanner_summary(self, stats: Dict):
        """Print scanner performance summary"""
        print("🔍 SCANNER PERFORMANCE (Last 24 Hours)")
        print("-" * 80)
        
        if stats['total_scans'] == 0:
            print("No scan data available\n")
            return
        
        print(f"Total Opportunities Scanned: {stats['total_scans']}")
        print(f"Avg Score: {stats['avg_score']:.1f}/100")
        print(f"Score Range: {stats['min_score']:.1f} - {stats['max_score']:.1f}\n")
        
        if stats['top_pairs']:
            print("Most Frequently Scanned Pairs:")
            for pair, count, avg_score in stats['top_pairs']:
                print(f"  • {pair}: {count} times (avg score {avg_score:.1f})")
        
        print()
    
    def print_pair_breakdown(self, hours_back: int = 24):
        """Print per-pair performance breakdown"""
        conn = self.get_db_connection()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        
        query = """
        SELECT 
            pair,
            COUNT(*) as trades,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
            SUM(realized_pnl) as total_pnl,
            AVG(realized_pnl) as avg_pnl,
            AVG(pnl_percent) as avg_pnl_pct
        FROM trades
        WHERE status = 'CLOSED'
            AND exit_time >= ?
        GROUP BY pair
        ORDER BY total_pnl DESC
        """
        
        cursor = conn.execute(query, (cutoff_time,))
        pairs = cursor.fetchall()
        conn.close()
        
        if not pairs:
            return
        
        print("💰 PER-PAIR PERFORMANCE (Last 24 Hours)")
        print("-" * 80)
        
        for pair_data in pairs:
            pair, trades, wins, losses, total_pnl, avg_pnl, avg_pnl_pct = pair_data
            win_rate = (wins / trades * 100) if trades > 0 else 0
            
            status_emoji = "✅" if total_pnl > 0 else "❌"
            
            print(f"{status_emoji} {pair}")
            print(f"   Trades: {trades} ({wins}W/{losses}L) | Win Rate: {win_rate:.1f}%")
            print(f"   Total P&L: ${total_pnl:.2f} | Avg: ${avg_pnl:.2f} ({avg_pnl_pct:+.2f}%)\n")
    
    def run(self, hours_back: int = 24):
        """Run complete analysis
        
        Args:
            hours_back: Number of hours to analyze
        """
        self.print_header()
        
        # Analyze closed trades
        closed_stats = self.analyze_closed_trades(hours_back)
        self.print_closed_trades_summary(closed_stats)
        
        # Analyze open positions
        open_stats = self.analyze_open_positions()
        self.print_open_positions_summary(open_stats)
        
        # Per-pair breakdown
        self.print_pair_breakdown(hours_back)
        
        # Scanner performance
        scanner_stats = self.analyze_scanner_performance(hours_back)
        self.print_scanner_summary(scanner_stats)
        
        # Overall summary
        print("📊 OVERALL SUMMARY")
        print("-" * 80)
        total_realized = closed_stats['total_pnl']
        total_unrealized = open_stats['total_unrealized_pnl']
        total_pnl = total_realized + total_unrealized
        
        print(f"Realized P&L: ${total_realized:.2f}")
        print(f"Unrealized P&L: ${total_unrealized:.2f}")
        print(f"Total P&L: ${total_pnl:.2f}\n")
        
        if closed_stats['total_trades'] > 0:
            print(f"Closed Trades: {closed_stats['total_trades']} ({closed_stats['win_rate']:.1f}% win rate)")
        print(f"Open Positions: {open_stats['total_positions']}")
        print(f"Opportunities Scanned: {scanner_stats['total_scans']}")
        
        print("\n" + "="*80)
        print("Analysis Complete! 🎉")
        print("="*80 + "\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='SilkTrader v3 - Overnight Trading Analysis',
        epilog="""
Examples:
  # Analyze last 24 hours
  python3 analyze_overnight.py
  
  # Analyze last 12 hours
  python3 analyze_overnight.py --hours 12
  
  # Use custom database
  python3 analyze_overnight.py --db data/backup.db
        """
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to analyze (default: 24)'
    )
    parser.add_argument(
        '--db',
        default='data/silktrader.db',
        help='Path to database file (default: data/silktrader.db)'
    )
    parser.add_argument(
        '--positions',
        default='data/positions.json',
        help='Path to positions file (default: data/positions.json)'
    )
    
    args = parser.parse_args()
    
    try:
        analyzer = OvernightAnalyzer(args.db, args.positions)
        analyzer.run(hours_back=args.hours)
        
    except FileNotFoundError as e:
        print(f"\n❌ File not found: {e}")
        print("Make sure the bot has been running and created data files\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
