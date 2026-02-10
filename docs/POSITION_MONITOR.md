# Position Monitor - Testing Guide

## Overview

The position monitor now includes full database integration for tracking:
- **Position snapshots** - Unrealized P&L over time
- **Exit logging** - Complete trade lifecycle from entry to exit
- **Trailing stops** - Track adjustments as positions move
- **Performance analytics** - Historical position data

## 🆕 What's New

### Database Integration
- ✅ Logs position snapshots every check cycle
- ✅ Updates trade records with exit data
- ✅ Tracks unrealized P&L changes
- ✅ Records trailing stop adjustments
- ✅ Graceful degradation (continues without DB if it fails)

### Enhanced Features
- ✅ Real-time P&L tracking
- ✅ Historical position performance
- ✅ Complete trade lifecycle logging
- ✅ Database statistics in summary

## 🚀 Quick Start

### Pull Latest Changes

```bash
cd /lab/dev/silktrader-v3
git pull origin dev
```

### Test with Paper Trades from Database

If you've been running the bot and have trades logged:

```bash
# Check what trades are in the database
python -c "
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')
trades = db.get_trades(status='OPEN', limit=10)

print('\n🔓 Open Trades in Database:')
for trade in trades:
    print(f'  {trade[\"trade_id\"]}: {trade[\"pair\"]} @ ${trade[\"entry_price\"]:.6f}')
    print(f'     Quantity: {trade[\"quantity\"]:.6f}')
    print(f'     Stop: ${trade[\"stop_loss\"]:.6f} | TP: ${trade[\"take_profit\"]:.6f}')

db.close()
"
```

### Convert Database Trades to Monitor Format

Create a helper script to load trades from database into the position monitor:

```python
# scripts/sync_positions.py
import sys
import json
sys.path.insert(0, 'lib')

from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')
trades = db.get_trades(status='OPEN')

positions = []
for trade in trades:
    position = {
        'trade_id': trade['trade_id'],
        'pair': trade['pair'],
        'entry': trade['entry_price'],
        'quantity': trade['quantity'],
        'stop_loss': trade['stop_loss'] or trade['entry_price'] * 0.95,  # Fallback
        'take_profit': trade['take_profit'] or trade['entry_price'] * 1.05,  # Fallback
        'opened_at': trade['entry_time'],
        'id': trade['trade_id']
    }
    positions.append(position)

# Save to positions.json
import os
os.makedirs('data', exist_ok=True)
with open('data/positions.json', 'w') as f:
    json.dump(positions, f, indent=2)

print(f'✅ Synced {len(positions)} open trades to positions.json')
for p in positions:
    print(f'   {p["pair"]}: ${p["entry"]:.6f}')

db.close()
```

Run it:

```bash
mkdir -p scripts
python scripts/sync_positions.py
```

### Run Position Monitor

```bash
# Monitor once (single check)
python monitor_positions.py --once

# Continuous monitoring (every 30 seconds)
python monitor_positions.py --interval 30

# Without database logging
python monitor_positions.py --once --no-db
```

## 🧪 Testing Scenarios

### Scenario 1: Manual Position with Database

Add a position manually and see it tracked in the database:

```bash
# Add a test position (PAPER TRADE)
python monitor_positions.py --add "BTC_USDT,70000,0.001,68500,73000" --once

# Check the database
python -c "
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')

# Check snapshots
print('📸 Position Snapshots:')
snapshots = db.get_position_snapshots(limit=10)
for snap in snapshots:
    print(f'  {snap[\"pair\"]}: ${snap[\"current_price\"]:.6f} - P&L: ${snap[\"unrealized_pnl\"]:.2f} ({snap[\"pnl_percent\"]:.2f}%)')

db.close()
"
```

### Scenario 2: Continuous Monitoring

Monitor positions continuously and watch snapshots accumulate:

```bash
# Run monitor for 5 minutes (10 checks at 30s intervals)
timeout 300 python monitor_positions.py --interval 30
```

**What to observe:**
- Position checks every 30 seconds
- Snapshots logged to database each check
- Trailing stops adjust as price moves
- Real-time P&L updates

**Verify snapshots:**

```bash
python -c "
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')
stats = db.get_database_stats()

print(f'📊 Database Stats:')
print(f'   Position snapshots: {stats[\"position_snapshots\"]}')
print(f'   Total trades: {stats[\"trades\"]}')

db.close()
"
```

### Scenario 3: Simulated Exit

To test exit logging, you can modify a position's stop loss to force a close:

1. **Check current price:**
   ```bash
   python -c "
   import sys; sys.path.insert(0, 'lib')
   from pionex_api import PionexAPI
   
   api = PionexAPI('credentials/pionex.json')
   klines = api.get_klines('BTC_USDT', '1M', 1)
   print(f'BTC_USDT current price: ${klines[0][\"close\"]:.2f}')
   "
   ```

2. **Edit positions.json** - Set stop_loss slightly above current price

3. **Run monitor:**
   ```bash
   python monitor_positions.py --once
   ```

4. **Verify exit logged:**
   ```bash
   python -c "
   import sys; sys.path.insert(0, 'lib')
   from database import TradingDatabase
   
   db = TradingDatabase('data/silktrader.db')
   trades = db.get_trades(status='CLOSED', limit=5)
   
   print('🔴 Closed Trades:')
   for trade in trades:
       print(f'  {trade[\"pair\"]}: ${trade[\"realized_pnl\"]:.2f} ({trade[\"pnl_percent\"]:.2f}%)')
       print(f'     Entry: ${trade[\"entry_price\"]:.6f} → Exit: ${trade[\"exit_price\"]:.6f}')
   
   db.close()
   "
   ```

### Scenario 4: Full Integration Test

Test the complete flow from bot → monitor → database:

```bash
# Terminal 1: Run the bot (creates trades)
python silktrader_bot.py --once

# Terminal 2: Sync positions from database
python scripts/sync_positions.py

# Terminal 3: Monitor positions
python monitor_positions.py --interval 30
```

**What happens:**
1. Bot scans markets, AI decides, executes trades (logged to DB)
2. Sync script loads open trades into monitor
3. Monitor tracks P&L and logs snapshots
4. When exit conditions hit, monitor updates trade records

## 📊 Database Queries

### View Position History

```python
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')

# Get snapshots for specific trade
trade_id = 'PAPER-VANA_USDT-1770742502'
snapshots = db.get_position_snapshots(trade_id=trade_id, limit=100)

print(f'📈 Position History for {trade_id}:')
for snap in snapshots:
    print(f'  {snap["snapshot_time"]}: ${snap["unrealized_pnl"]:+.2f} ({snap["pnl_percent"]:+.2f}%)')

db.close()
```

### Analyze P&L Changes

```python
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')

# Get all snapshots ordered by time
snapshots = db.execute_query(
    "SELECT * FROM position_snapshots ORDER BY snapshot_time DESC LIMIT 50"
)

print('📊 Recent P&L Movements:')
for snap in snapshots:
    status = '🟢' if snap[4] > 0 else '🔴'  # unrealized_pnl column
    print(f'{status} {snap[1]}: ${snap[4]:+.2f} at {snap[7]}')

db.close()
```

### Get Trade Performance Summary

```python
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')

# Trade statistics
stats = db.get_trade_statistics(paper_trading=True)

print('💰 Trading Performance:')
print(f'   Total Trades: {stats.get("total_trades", 0)}')
print(f'   Win Rate: {stats.get("win_rate", 0):.1f}%')
print(f'   Total P&L: ${stats.get("total_pnl", 0):.2f}')
print(f'   Avg Win: ${stats.get("avg_win", 0):.2f}')
print(f'   Avg Loss: ${stats.get("avg_loss", 0):.2f}')
print(f'   Profit Factor: {stats.get("profit_factor", 0):.2f}')

db.close()
```

## 🎯 What Gets Logged

### Position Snapshots (Every Check)
```json
{
  "trade_id": "PAPER-VANA_USDT-1770742502",
  "pair": "VANA_USDT",
  "current_price": 1.72,
  "unrealized_pnl": 0.04,
  "pnl_percent": 0.58,
  "trailing_stop": 1.68,
  "position_value": 7.30,
  "snapshot_time": "2026-02-10T18:45:30"
}
```

### Trade Exits (When Position Closes)
```json
{
  "exit_price": 1.75,
  "exit_time": "2026-02-10T19:15:45",
  "realized_pnl": 0.21,
  "pnl_percent": 2.34,
  "status": "CLOSED"
}
```

## 🔍 Troubleshooting

### No Positions Loading

**Problem:** `No open positions to monitor`

**Solution:**
```bash
# Check if positions.json exists
cat data/positions.json

# If empty, sync from database
python scripts/sync_positions.py

# Or add manually
python monitor_positions.py --add "PAIR,ENTRY,QUANTITY,SL,TP"
```

### Database Not Connected

**Problem:** Monitor shows "⚠️ Not connected"

**Solution:**
```bash
# Check if database file exists
ls -la data/silktrader.db

# Test database directly
python lib/database.py

# Run monitor without DB if needed
python monitor_positions.py --no-db
```

### Snapshots Not Logging

**Problem:** No snapshots in database

**Check:**
```bash
# Verify monitor has DB enabled
python monitor_positions.py --once 2>&1 | grep -i database

# Should show: "Database: ✅ Connected"

# Check for errors
python monitor_positions.py --once 2>&1 | grep -i error
```

### Positions Not Closing

**Problem:** Stop loss/take profit hit but position still open

**Debug:**
```bash
# Check current price vs stop/TP
python -c "
import json
with open('data/positions.json') as f:
    positions = json.load(f)
    for p in positions:
        print(f'{p[\"pair\"]}: Entry ${p[\"entry\"]} | Stop ${p[\"stop_loss\"]} | TP ${p[\"take_profit\"]}')
"

# Verify price is actually hitting levels
# If it should have closed, check for errors in monitor output
```

## 💡 Pro Tips

### Automatic Position Sync

Create a cron job to sync positions regularly:

```bash
# Add to crontab (every 5 minutes)
*/5 * * * * cd /lab/dev/silktrader-v3 && /usr/bin/python3 scripts/sync_positions.py
```

### Combined Bot + Monitor

Run both in tmux/screen sessions:

```bash
# Session 1: Trading bot
tmux new -s silktrader-bot
python silktrader_bot.py --interval 900
# Ctrl+B, D to detach

# Session 2: Position monitor
tmux new -s silktrader-monitor
python monitor_positions.py --interval 30
# Ctrl+B, D to detach

# Reattach with:
tmux attach -t silktrader-bot
tmux attach -t silktrader-monitor
```

### Real-time Dashboard

Watch position snapshots in real-time:

```bash
# In another terminal
watch -n 5 'python -c "
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase
db = TradingDatabase('data/silktrader.db')
snaps = db.get_position_snapshots(limit=5)
for s in snaps:
    print(f'{s[\"pair\"]}: ${s[\"unrealized_pnl\"]:+.2f}')
db.close()
"'
```

## ✅ Success Checklist

- [ ] Position monitor pulls latest code
- [ ] Database integration enabled (shows ✅ Connected)
- [ ] Positions loaded (from file or database)
- [ ] Monitor runs without errors
- [ ] Snapshots logged to database after each check
- [ ] Trailing stops adjust correctly
- [ ] Exit conditions detected
- [ ] Trade records updated on close
- [ ] Statistics show in session summary

## 🚀 Next Steps

Once position monitoring is working:

1. **Run Extended Test** - Monitor for 24 hours
2. **Analyze Patterns** - Use database queries to find optimization opportunities
3. **Build Dashboard** - Visualize P&L changes over time
4. **Optimize Stops** - Test different trailing stop strategies
5. **Backtesting** - Use historical data to validate approach

You now have **complete trade lifecycle tracking** from scan → decision → entry → monitoring → exit! 🎉
