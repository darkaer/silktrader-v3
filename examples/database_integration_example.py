#!/usr/bin/env python3
"""
SilkTrader v3 - Database Integration Example
Shows how to integrate the database module into existing components
"""

# ==================== EXAMPLE 1: silktrader_bot.py ====================
"""
Add database to main bot class:
"""

class SilkTraderBot_WithDatabase:
    def __init__(self, config_path: str = 'credentials/pionex.json', dry_run: bool = True):
        # ... existing initialization ...
        
        # ADD: Initialize database
        from lib.database import TradingDatabase
        self.db = TradingDatabase('data/silktrader.db')
        
        print("📊 Database connected")
    
    def run_cycle(self):
        """Run one complete trading cycle with database logging"""
        import uuid
        from datetime import datetime
        
        cycle_start = datetime.now()
        scan_id = str(uuid.uuid4())
        scan_time = cycle_start.isoformat()
        
        # ... existing cycle setup ...
        
        # Scan markets
        opportunities = self.scan_markets()
        
        # ADD: Log scan results to database
        if opportunities:
            self.db.insert_scan_results(scan_id, scan_time, opportunities)
            print(f"   📝 Logged {len(opportunities)} opportunities to database")
        
        # Evaluate and execute opportunities
        trades_executed = 0
        
        for opp in opportunities:
            should_trade, decision = self.evaluate_with_llm(opp)
            
            if should_trade and decision:
                success = self.execute_trade(opp, decision)
                if success:
                    trades_executed += 1
        
        # ADD: Update daily summary at end of cycle
        today = datetime.now().strftime('%Y-%m-%d')
        self.db.update_daily_summary(today, paper_trading=self.dry_run)
        
        # ... rest of cycle ...
    
    def close(self):
        """Clean shutdown"""
        # ADD: Close database connection
        if hasattr(self, 'db'):
            self.db.close()
            print("📊 Database connection closed")


# ==================== EXAMPLE 2: exchange_manager.py ====================
"""
Add database logging to trade execution:
"""

class ExchangeManager_WithDatabase:
    def __init__(self, api, risk_mgr, dry_run=True, db=None):
        # ... existing initialization ...
        
        # ADD: Store database reference
        self.db = db
    
    def execute_trade(self, pair: str, side: str, entry_price: float, confidence: int):
        """Execute trade with database logging"""
        from datetime import datetime
        
        # ... existing trade execution logic ...
        
        if result['success']:
            # Existing logging/output
            print(f"✅ Trade Executed: {result['order_id']}")
            
            # ADD: Log trade to database
            if self.db:
                trade_data = {
                    'trade_id': result['order_id'],
                    'pair': pair,
                    'side': side,
                    'order_type': 'MARKET',
                    'entry_price': entry_price,
                    'quantity': result['quantity'],
                    'position_usdt': result['position_usdt'],
                    'stop_loss': result.get('stop_loss'),
                    'take_profit': result.get('take_profit'),
                    'confidence_score': confidence,
                    'paper_trading': self.dry_run,
                    'status': 'OPEN',
                    'entry_time': datetime.now().isoformat()
                }
                
                try:
                    self.db.insert_trade(trade_data)
                    print(f"   📝 Trade logged to database")
                except Exception as e:
                    print(f"   ⚠️  Database logging failed: {e}")
        
        return result
    
    def close_position(self, trade_id: str, exit_price: float, reason: str):
        """Close position with database update"""
        from datetime import datetime
        
        # ... existing position close logic ...
        
        # ADD: Update trade in database
        if self.db and result['success']:
            exit_data = {
                'exit_price': exit_price,
                'exit_time': datetime.now().isoformat(),
                'realized_pnl': result['pnl'],
                'pnl_percent': result['pnl_percent'],
                'status': 'CLOSED'
            }
            
            try:
                self.db.update_trade_exit(trade_id, exit_data)
                print(f"   📝 Trade exit logged to database")
            except Exception as e:
                print(f"   ⚠️  Database update failed: {e}")
        
        return result


# ==================== EXAMPLE 3: llm_decision.py ====================
"""
Add decision logging to LLM engine:
"""

class LLMDecisionEngine_WithDatabase:
    def __init__(self, api_key=None, db=None):
        # ... existing initialization ...
        
        # ADD: Store database reference
        self.db = db
    
    def analyze_opportunity(self, pair: str, indicators: dict, score: int) -> dict:
        """Analyze opportunity with decision logging"""
        from datetime import datetime
        
        # ... existing LLM analysis ...
        
        decision = {
            'action': 'BUY',  # or 'WAIT'
            'confidence': 8,
            'reasoning': 'Strong technical confluence...'
        }
        
        # ADD: Log decision to database
        if self.db:
            decision_data = {
                'pair': pair,
                'scanner_score': score,
                'action': decision['action'],
                'confidence': decision['confidence'],
                'reasoning': decision['reasoning'],
                'indicators': indicators,
                'model': self.model,
                'decision_time': datetime.now().isoformat()
            }
            
            try:
                self.db.insert_llm_decision(decision_data)
            except Exception as e:
                print(f"   ⚠️  Decision logging failed: {e}")
        
        return decision


# ==================== EXAMPLE 4: monitor_positions.py ====================
"""
Add position snapshots to monitoring:
"""

def monitor_positions_with_database():
    """Monitor positions with database snapshots"""
    from datetime import datetime
    from lib.database import TradingDatabase
    from lib.exchange_manager import ExchangeManager
    
    db = TradingDatabase('data/silktrader.db')
    
    # Get open trades from database
    open_trades = db.get_trades(status='OPEN', limit=100)
    
    print(f"\n📊 Monitoring {len(open_trades)} open positions...\n")
    
    for trade in open_trades:
        # Get current price (from your API)
        current_price = get_current_price(trade['pair'])
        
        # Calculate unrealized P&L
        unrealized_pnl = (current_price - trade['entry_price']) * trade['quantity']
        pnl_percent = (unrealized_pnl / trade['position_usdt']) * 100
        
        # Create snapshot
        snapshot = {
            'trade_id': trade['trade_id'],
            'pair': trade['pair'],
            'current_price': current_price,
            'entry_price': trade['entry_price'],
            'quantity': trade['quantity'],
            'unrealized_pnl': unrealized_pnl,
            'pnl_percent': pnl_percent,
            'stop_loss': trade.get('stop_loss'),
            'take_profit': trade.get('take_profit'),
            'snapshot_time': datetime.now().isoformat()
        }
        
        # ADD: Insert snapshot
        db.insert_position_snapshot(snapshot)
        
        # Display current status
        print(f"   {trade['pair']}: ${unrealized_pnl:+.2f} ({pnl_percent:+.1f}%)")
        
        # Check if should close (stop loss / take profit hit)
        if trade.get('stop_loss') and current_price <= trade['stop_loss']:
            print(f"   ⚠️  Stop loss hit! Closing position...")
            # close_position(trade['trade_id'])
    
    db.close()


# ==================== EXAMPLE 5: Performance Analytics ====================
"""
Create performance reports from database:
"""

def generate_performance_report():
    """Generate comprehensive performance report"""
    from lib.database import TradingDatabase
    from datetime import datetime, timedelta
    
    db = TradingDatabase('data/silktrader.db')
    
    print("="*70)
    print("📊 SILKTRADER V3 - PERFORMANCE REPORT")
    print("="*70)
    
    # Overall statistics
    stats = db.get_trade_statistics(paper_trading=True)
    
    print("\n📈 Overall Statistics:")
    print(f"   Total Trades: {stats.get('total_trades', 0)}")
    print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
    print(f"   Total P&L: ${stats.get('total_pnl', 0):.2f}")
    print(f"   Average Win: ${stats.get('avg_win', 0):.2f}")
    print(f"   Average Loss: ${stats.get('avg_loss', 0):.2f}")
    print(f"   Largest Win: ${stats.get('largest_win', 0):.2f}")
    print(f"   Largest Loss: ${stats.get('largest_loss', 0):.2f}")
    
    # Last 7 days performance
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    summaries = db.get_daily_summaries(start_date=seven_days_ago, limit=7)
    
    print("\n📅 Last 7 Days:")
    for summary in reversed(summaries):
        print(f"   {summary['date']}: {summary['trades_count']} trades, "
              f"${summary['total_pnl']:+.2f} ({summary['win_rate']:.0f}% win rate)")
    
    # Best performing pairs
    all_trades = db.get_trades(status='CLOSED', paper_trading=True, limit=1000)
    pair_performance = {}
    
    for trade in all_trades:
        pair = trade['pair']
        if pair not in pair_performance:
            pair_performance[pair] = {'trades': 0, 'pnl': 0.0}
        pair_performance[pair]['trades'] += 1
        pair_performance[pair]['pnl'] += trade.get('realized_pnl', 0)
    
    print("\n🏆 Top Performing Pairs:")
    sorted_pairs = sorted(pair_performance.items(), key=lambda x: x[1]['pnl'], reverse=True)
    for pair, data in sorted_pairs[:5]:
        print(f"   {pair}: ${data['pnl']:+.2f} ({data['trades']} trades)")
    
    # LLM decision accuracy
    buy_decisions = db.get_llm_decisions(action='BUY', limit=1000)
    print(f"\n🧠 LLM Decision Statistics:")
    print(f"   Total BUY decisions: {len(buy_decisions)}")
    
    # Database stats
    db_stats = db.get_database_stats()
    print(f"\n💾 Database Statistics:")
    print(f"   Total records: {sum(v for k, v in db_stats.items() if k != 'database_size_mb')}")
    print(f"   Database size: {db_stats['database_size_mb']:.2f} MB")
    print(f"   Trades logged: {db_stats['trades']}")
    print(f"   Scans logged: {db_stats['scan_results']}")
    print(f"   Decisions logged: {db_stats['llm_decisions']}")
    
    print("="*70 + "\n")
    
    db.close()


# ==================== EXAMPLE 6: Quick Start Script ====================
"""
Simple script to test database immediately:
"""

if __name__ == '__main__':
    print("\n🚀 SilkTrader v3 - Database Quick Start\n")
    
    from lib.database import TradingDatabase
    
    # Initialize database
    db = TradingDatabase('data/silktrader.db')
    print("✅ Database initialized")
    
    # Show current stats
    stats = db.get_database_stats()
    print("\n📊 Current Database Stats:")
    for key, value in stats.items():
        if 'size' in key:
            print(f"   {key}: {value:.3f} MB")
        else:
            print(f"   {key}: {value} records")
    
    # Show recent trades if any
    trades = db.get_trades(limit=5)
    if trades:
        print(f"\n💰 Last {len(trades)} Trades:")
        for trade in trades:
            pnl = trade.get('realized_pnl', 0)
            status = trade.get('status', 'UNKNOWN')
            print(f"   {trade['pair']}: {status} - ${pnl:+.2f} P&L")
    else:
        print("\nℹ️  No trades logged yet. Start trading to populate database!")
    
    db.close()
    print("\n📖 See docs/DATABASE.md for full integration guide\n")
