# Database Integration - Testing Guide

## ✅ Integration Complete!

The database module has been fully integrated into SilkTrader v3. All components now log their activities to the SQLite database while preserving full backward compatibility.

## 📦 What's Been Integrated

### 1. **silktrader_bot.py**
- ✅ Initializes `TradingDatabase` on startup
- ✅ Logs all scan results with unique scan_id
- ✅ Updates daily summaries after each cycle
- ✅ Shows database stats in startup banner
- ✅ Clean shutdown closes database connection
- ✅ Gracefully handles database failures (continues without DB if it fails)

### 2. **lib/exchange_manager.py**
- ✅ Accepts optional `db` parameter in constructor
- ✅ Logs all trade entries with full details
- ✅ Logs trade exits with P&L calculations
- ✅ New `close_position()` method for exit logging
- ✅ Continues trading if database logging fails

### 3. **lib/llm_decision.py**
- ✅ Accepts optional `db` parameter in constructor
- ✅ Logs all LLM decisions (action, confidence, reasoning)
- ✅ Stores model name and indicators used
- ✅ Continues if database logging fails

## 🚀 Testing the Integration

### Step 1: Pull Latest Changes

```bash
cd /lab/dev/silktrader-v3
git pull origin dev
```

You should see these new commits:
1. Database module (`lib/database.py`)
2. Database documentation (`docs/DATABASE.md`)
3. Database tests (`tests/test_database.py`)
4. Integration examples (`examples/database_integration_example.py`)
5. Bot integration (`silktrader_bot.py`)
6. Exchange manager integration (`lib/exchange_manager.py`)
7. LLM decision integration (`lib/llm_decision.py`)

### Step 2: Run Database Tests

```bash
source venv/bin/activate
python tests/test_database.py
```

**Expected Output:**
- ✅ All tests passed!
- ✅ Database created at `data/test_silktrader.db`
- ✅ 6 tables initialized
- ✅ All CRUD operations working

### Step 3: Test Bot with Database

```bash
# Run a single scan cycle (paper trading)
python silktrader_bot.py --once
```

**What to Look For:**

1. **Startup Banner:**
   ```
   🤖 SilkTrader v3 - Autonomous Trading Bot
   ...
   Database: ✅ Connected (X trades logged)
   ```

2. **During Scan:**
   ```
   🔍 [HH:MM:SS] Scanning markets...
   📝 Logged X scan results to database
   ```

3. **After Cycle:**
   - Database file created: `data/silktrader.db`
   - Session summary includes database stats

### Step 4: Verify Database Contents

Run this quick check:

```python
python -c "
import sys
sys.path.insert(0, 'lib')
from database import TradingDatabase

db = TradingDatabase('data/silktrader.db')
stats = db.get_database_stats()

print('\n📊 Database Contents:')
for key, value in stats.items():
    if 'size' in key:
        print(f'   {key}: {value:.3f} MB')
    else:
        print(f'   {key}: {value} records')

print('\n📈 Recent Scans:')
scans = db.get_scan_history(limit=5)
for scan in scans:
    print(f'   {scan[\"pair\"]}: score {scan[\"score\"]}/100 - {scan[\"scan_time\"]}')

db.close()
"
```

## 🎯 What Gets Logged

### Scan Results
Every market scan logs:
- Scan ID (UUID for grouping)
- All opportunities found
- Scores, prices, indicators
- Reasoning from scanner
- Affordability status
- Timestamp

### LLM Decisions
Every AI decision logs:
- Pair analyzed
- Scanner score that triggered analysis
- LLM action (BUY/WAIT/SELL)
- Confidence level (1-10)
- Reasoning text
- All indicators used
- Model name
- Timestamp

### Trades
Every trade logs:
- **On Entry:**
  - Trade ID (order ID)
  - Pair, side, order type
  - Entry price, quantity
  - Position size in USDT
  - Stop loss / take profit levels
  - Confidence score
  - Paper trading flag
  - Status: OPEN
  - Entry timestamp

- **On Exit:**
  - Exit price, exit time
  - Realized P&L (USDT and %)
  - Hold duration
  - Status: CLOSED

### Daily Summaries
End of each cycle updates:
- Date
- Trade count (total, wins, losses)
- Win rate percentage
- Total P&L
- Average win/loss
- Largest win/loss
- Volume traded
- Scans performed
- Opportunities found

## 📊 Viewing Your Data

### Quick Stats

```bash
python -c "
import sys; sys.path.insert(0, 'lib')
from database import TradingDatabase
db = TradingDatabase('data/silktrader.db')
stats = db.get_trade_statistics(paper_trading=True)
print(f'Win Rate: {stats.get(\"win_rate\", 0):.1f}%')
print(f'Total P&L: ${stats.get(\"total_pnl\", 0):.2f}')
db.close()
"
```

### Generate Performance Report

```bash
python examples/database_integration_example.py
```

This runs the performance report generator from the examples.

### Using SQLite Browser (Optional)

If you have SQLite browser installed:

```bash
# On Arch Linux
sudo pacman -S sqlitebrowser
sqlitebrowser data/silktrader.db
```

Or use command line:

```bash
sqlite3 data/silktrader.db
sqlite> SELECT * FROM trades LIMIT 5;
sqlite> SELECT * FROM scan_results ORDER BY score DESC LIMIT 10;
sqlite> .exit
```

## 🧪 Testing Scenarios

### Scenario 1: Single Scan Cycle
```bash
python silktrader_bot.py --once
```

**Verify:**
- `data/silktrader.db` created
- Scan results logged
- Daily summary exists
- No errors in output

### Scenario 2: Multiple Cycles
```bash
# Run 3 scans with 60 second intervals
timeout 180 python silktrader_bot.py --interval 60
```

**Verify:**
- Multiple scan_ids in database
- Daily summary updates after each cycle
- Database size grows appropriately

### Scenario 3: With LLM Enabled

If you have OpenRouter API key:

1. Add to `credentials/pionex.json`:
   ```json
   {
     "openrouter_api_key": "sk-or-v1-...",
     ...
   }
   ```

2. Run:
   ```bash
   python silktrader_bot.py --once
   ```

**Verify:**
- LLM decisions logged in database
- Check with:
  ```bash
  sqlite3 data/silktrader.db "SELECT pair, action, confidence, reasoning FROM llm_decisions LIMIT 5;"
  ```

## 🔧 Troubleshooting

### Database Not Created

**Symptom:** No `data/silktrader.db` file

**Solution:**
```bash
# Check if data directory exists
mkdir -p data

# Test database creation directly
python lib/database.py
```

### Database Connection Errors

**Symptom:** "Database locked" or connection errors

**Solution:**
- Close any other programs accessing the database
- Check file permissions: `ls -la data/silktrader.db`
- Try: `chmod 644 data/silktrader.db`

### No Data Being Logged

**Symptom:** Database exists but tables are empty

**Check:**
1. Look for database warnings in bot output
2. Verify bot completed at least one cycle
3. Check if dry_run mode is working:
   ```bash
   python silktrader_bot.py --once 2>&1 | grep -i database
   ```

### Bot Continues Without Database

**This is normal!** The integration is designed to fail gracefully:
- If database initialization fails → Bot continues without DB
- If database logging fails → Bot continues, logs warning
- All core functionality preserved

## 📈 Next Steps

Once basic integration is working:

1. **Run Extended Test**
   - Let bot run for a day in paper trading mode
   - Accumulate real market data
   - Test performance analytics

2. **Add Position Monitoring**
   - Integrate `monitor_positions.py` with database
   - Log position snapshots
   - Track P&L over time

3. **Build Analytics Dashboard**
   - Create custom reports
   - Analyze win/loss patterns
   - Optimize scanner/LLM parameters

4. **Backtesting Preparation**
   - Start collecting historical candles
   - Log sufficient trade data
   - Prepare for strategy optimization

## 🆘 Need Help?

If something doesn't work:

1. **Check the logs:**
   ```bash
   cat logs/trading_log.txt | tail -50
   ```

2. **Run database tests:**
   ```bash
   python tests/test_database.py
   ```

3. **Verify file structure:**
   ```bash
   ls -la data/
   ls -la lib/database.py
   ```

4. **Check permissions:**
   ```bash
   chmod +x silktrader_bot.py
   chmod 755 data/
   ```

## ✅ Success Checklist

- [ ] Database tests pass
- [ ] `data/silktrader.db` created on first run
- [ ] Scan results logged
- [ ] Daily summary exists
- [ ] Bot completes cycle without errors
- [ ] Database stats show in session summary
- [ ] No "database locked" errors
- [ ] Bot continues if database fails (graceful degradation)

Once all checked, you're ready to start collecting real trading data! 🚀
