#!/usr/bin/env python3
"""
SilkTrader v3 - Database Module Tests
Verify database functionality and integration
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import uuid
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.database import TradingDatabase


def test_database_creation():
    """Test database schema creation"""
    print("\n🔧 Testing database creation...")
    
    test_db_path = 'data/test_silktrader.db'
    
    # Remove test database if exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = TradingDatabase(test_db_path)
    
    stats = db.get_database_stats()
    print(f"   ✅ Database created: {test_db_path}")
    print(f"   ✅ Tables initialized: {len(stats) - 1} tables")
    print(f"   ✅ Size: {stats['database_size_mb']:.3f} MB")
    
    db.close()
    return db


def test_market_data():
    """Test market data storage"""
    print("\n📊 Testing market data storage...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    # Sample candles
    candles = [
        {
            'timestamp': 1707584400,
            'open': 50000.0,
            'high': 51000.0,
            'low': 49500.0,
            'close': 50500.0,
            'volume': 1234.56
        },
        {
            'timestamp': 1707585300,
            'open': 50500.0,
            'high': 50800.0,
            'low': 50200.0,
            'close': 50600.0,
            'volume': 987.65
        },
        {
            'timestamp': 1707586200,
            'open': 50600.0,
            'high': 51200.0,
            'low': 50500.0,
            'close': 51000.0,
            'volume': 1543.21
        }
    ]
    
    inserted = db.insert_candles('BTC_USDT', '15M', candles)
    print(f"   ✅ Inserted {inserted} candles")
    
    # Retrieve candles
    retrieved = db.get_candles('BTC_USDT', '15M', limit=10)
    print(f"   ✅ Retrieved {len(retrieved)} candles")
    print(f"   ✅ Latest close: ${retrieved[0]['close']:.2f}")
    
    db.close()


def test_trades():
    """Test trade storage and updates"""
    print("\n💰 Testing trade storage...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    # Insert new trade
    trade_id = f"PAPER-BTC_USDT-{int(datetime.now().timestamp())}"
    trade = {
        'trade_id': trade_id,
        'pair': 'BTC_USDT',
        'side': 'BUY',
        'order_type': 'MARKET',
        'entry_price': 50000.0,
        'quantity': 0.02,
        'position_usdt': 1000.0,
        'stop_loss': 49000.0,
        'take_profit': 52000.0,
        'confidence_score': 85,
        'paper_trading': True,
        'status': 'OPEN',
        'entry_time': datetime.now().isoformat()
    }
    
    db_trade_id = db.insert_trade(trade)
    print(f"   ✅ Trade inserted: {trade_id}")
    print(f"   ✅ Database ID: {db_trade_id}")
    
    # Update trade exit
    exit_data = {
        'exit_price': 51500.0,
        'exit_time': datetime.now().isoformat(),
        'entry_time': trade['entry_time'],
        'realized_pnl': 30.0,
        'pnl_percent': 3.0,
        'status': 'CLOSED'
    }
    
    updated = db.update_trade_exit(trade_id, exit_data)
    print(f"   ✅ Trade updated with exit: {updated}")
    
    # Get trade statistics
    stats = db.get_trade_statistics(paper_trading=True)
    print(f"   ✅ Total trades: {stats['total_trades']}")
    print(f"   ✅ Total P&L: ${stats['total_pnl']:.2f}")
    
    db.close()


def test_scan_results():
    """Test scanner results storage"""
    print("\n🔍 Testing scan results storage...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    scan_id = str(uuid.uuid4())
    scan_time = datetime.now().isoformat()
    
    results = [
        {
            'pair': 'ETH_USDT',
            'score': 85,
            'entry_price': 3000.0,
            'reasoning': 'Strong bullish momentum with volume confirmation',
            'indicators': {
                'rsi': 65.5,
                'ema_fast': 2950.0,
                'ema_slow': 2900.0,
                'volume_ratio': 1.8,
                'price': 3000.0
            },
            'affordable': True
        },
        {
            'pair': 'SOL_USDT',
            'score': 78,
            'entry_price': 150.0,
            'reasoning': 'Uptrend with RSI in buy zone',
            'indicators': {
                'rsi': 58.2,
                'ema_fast': 148.0,
                'ema_slow': 145.0,
                'volume_ratio': 1.5,
                'price': 150.0
            },
            'affordable': True
        }
    ]
    
    inserted = db.insert_scan_results(scan_id, scan_time, results)
    print(f"   ✅ Scan results inserted: {inserted} opportunities")
    print(f"   ✅ Scan ID: {scan_id[:8]}...")
    
    # Retrieve scan history
    history = db.get_scan_history(min_score=70, limit=10)
    print(f"   ✅ Retrieved {len(history)} scan results")
    if history:
        print(f"   ✅ Top pair: {history[0]['pair']} (score: {history[0]['score']})")
    
    db.close()


def test_llm_decisions():
    """Test LLM decision logging"""
    print("\n🧠 Testing LLM decision logging...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    decision = {
        'pair': 'BTC_USDT',
        'scanner_score': 85,
        'action': 'BUY',
        'confidence': 8,
        'reasoning': 'Strong technical confluence with bullish momentum and volume confirmation',
        'indicators': {
            'rsi': 65.0,
            'ema_trend': 'bullish',
            'volume_ratio': 1.8
        },
        'model': 'arcee-ai/arcee-trinity',
        'decision_time': datetime.now().isoformat()
    }
    
    decision_id = db.insert_llm_decision(decision)
    print(f"   ✅ LLM decision logged: ID {decision_id}")
    print(f"   ✅ Action: {decision['action']} (confidence {decision['confidence']}/10)")
    
    # Retrieve decisions
    decisions = db.get_llm_decisions(action='BUY', limit=10)
    print(f"   ✅ Retrieved {len(decisions)} BUY decisions")
    
    db.close()


def test_position_snapshots():
    """Test position snapshot storage"""
    print("\n📸 Testing position snapshots...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    trade_id = f"PAPER-ETH_USDT-{int(datetime.now().timestamp())}"
    
    # Create snapshots at different times
    snapshots = [
        {
            'trade_id': trade_id,
            'pair': 'ETH_USDT',
            'current_price': 3000.0,
            'entry_price': 2950.0,
            'quantity': 0.5,
            'unrealized_pnl': 25.0,
            'pnl_percent': 1.7,
            'stop_loss': 2900.0,
            'take_profit': 3100.0,
            'snapshot_time': datetime.now().isoformat()
        },
        {
            'trade_id': trade_id,
            'pair': 'ETH_USDT',
            'current_price': 3020.0,
            'entry_price': 2950.0,
            'quantity': 0.5,
            'unrealized_pnl': 35.0,
            'pnl_percent': 2.4,
            'stop_loss': 2900.0,
            'take_profit': 3100.0,
            'snapshot_time': datetime.now().isoformat()
        }
    ]
    
    for snapshot in snapshots:
        snapshot_id = db.insert_position_snapshot(snapshot)
        print(f"   ✅ Snapshot inserted: ID {snapshot_id}, P&L: ${snapshot['unrealized_pnl']:.2f}")
    
    # Retrieve position history
    history = db.get_position_history(trade_id)
    print(f"   ✅ Retrieved {len(history)} snapshots for trade {trade_id[:20]}...")
    
    db.close()


def test_daily_summary():
    """Test daily summary updates"""
    print("\n📅 Testing daily summary...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    db.update_daily_summary(today, paper_trading=True)
    print(f"   ✅ Daily summary updated for {today}")
    
    # Get summaries
    summaries = db.get_daily_summaries(limit=7)
    print(f"   ✅ Retrieved {len(summaries)} daily summaries")
    
    if summaries:
        latest = summaries[0]
        print(f"   ✅ Latest: {latest['trades_count']} trades, ${latest['total_pnl']:.2f} P&L")
    
    db.close()


def test_backup():
    """Test database backup"""
    print("\n💾 Testing database backup...")
    
    db = TradingDatabase('data/test_silktrader.db')
    
    backup_path = 'data/test_backup.db'
    db.backup_database(backup_path)
    
    if os.path.exists(backup_path):
        backup_size = os.path.getsize(backup_path)
        print(f"   ✅ Backup created: {backup_path}")
        print(f"   ✅ Backup size: {backup_size / 1024:.2f} KB")
        os.remove(backup_path)
    
    db.close()


def main():
    """Run all tests"""
    print("="*60)
    print("🧪 SilkTrader v3 - Database Module Tests")
    print("="*60)
    
    try:
        test_database_creation()
        test_market_data()
        test_trades()
        test_scan_results()
        test_llm_decisions()
        test_position_snapshots()
        test_daily_summary()
        test_backup()
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)
        
        # Final statistics
        db = TradingDatabase('data/test_silktrader.db')
        stats = db.get_database_stats()
        
        print("\n📊 Final Database Statistics:")
        for key, value in stats.items():
            if 'size' in key:
                print(f"   {key}: {value:.3f} MB")
            else:
                print(f"   {key}: {value}")
        
        db.close()
        
        print("\n💡 Next steps:")
        print("   1. Integrate database into silktrader_bot.py")
        print("   2. Add database logging to exchange_manager.py")
        print("   3. Log LLM decisions in llm_decision.py")
        print("   4. Add position snapshots to monitor_positions.py")
        print("\n📖 See docs/DATABASE.md for integration guide\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
