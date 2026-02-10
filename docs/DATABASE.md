# SilkTrader v3 - Database Module

## Overview

The database module provides persistent storage for all trading data, enabling backtesting, performance analysis, and audit trails. It uses SQLite for simplicity and portability.

**Location:** `lib/database.py`  
**Database File:** `data/silktrader.db` (auto-created)

## Database Schema

### Tables

#### 1. `market_data` - Historical OHLCV Candles
Stores price candles for backtesting and technical analysis.

```sql
CREATE TABLE market_data (
    id INTEGER PRIMARY KEY,
    pair TEXT NOT NULL,              -- e.g., 'BTC_USDT'
    timeframe TEXT NOT NULL,         -- e.g., '15M', '1H', '1D'
    timestamp INTEGER NOT NULL,      -- Unix timestamp
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pair, timeframe, timestamp)
);
```

**Indexes:**
- `idx_market_data_pair_time` on `(pair, timeframe, timestamp DESC)`

#### 2. `trades` - Trade Execution History
Complete trade lifecycle from entry to exit.

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    trade_id TEXT UNIQUE NOT NULL,   -- e.g., 'PAPER-BTC_USDT-1707584400'
    pair TEXT NOT NULL,
    side TEXT NOT NULL,              -- 'BUY' or 'SELL'
    order_type TEXT NOT NULL,        -- 'MARKET' or 'LIMIT'
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    position_usdt REAL NOT NULL,
    exit_price REAL,
    realized_pnl REAL,
    pnl_percent REAL,
    stop_loss REAL,
    take_profit REAL,
    confidence_score INTEGER,        -- Scanner score 0-100
    paper_trading BOOLEAN NOT NULL,
    status TEXT NOT NULL,            -- 'OPEN', 'CLOSED'
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    hold_duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_trades_pair_time` on `(pair, entry_time DESC)`
- `idx_trades_status` on `(status, entry_time DESC)`

#### 3. `scan_results` - Scanner Opportunities
Every market scan result with scores and indicators.

```sql
CREATE TABLE scan_results (
    id INTEGER PRIMARY KEY,
    scan_id TEXT NOT NULL,           -- Unique per scan cycle
    pair TEXT NOT NULL,
    score INTEGER NOT NULL,          -- 0-100
    price REAL NOT NULL,
    reasoning TEXT,
    indicators TEXT,                 -- JSON string
    affordable BOOLEAN NOT NULL,
    selected_for_trade BOOLEAN DEFAULT 0,
    scan_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_scan_results_time` on `(scan_time DESC)`
- `idx_scan_results_pair` on `(pair, scan_time DESC)`

#### 4. `llm_decisions` - AI Decision Audit Trail
Every LLM decision for transparency and improvement.

```sql
CREATE TABLE llm_decisions (
    id INTEGER PRIMARY KEY,
    pair TEXT NOT NULL,
    scanner_score INTEGER NOT NULL,
    action TEXT NOT NULL,            -- 'BUY', 'WAIT'
    confidence INTEGER NOT NULL,     -- 1-10
    reasoning TEXT NOT NULL,
    indicators TEXT,                 -- JSON string
    model_name TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    decision_time TIMESTAMP NOT NULL,
    executed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_llm_decisions_time` on `(decision_time DESC)`

#### 5. `position_snapshots` - Position State Tracking
Periodic snapshots of open positions for performance analysis.

```sql
CREATE TABLE position_snapshots (
    id INTEGER PRIMARY KEY,
    trade_id TEXT NOT NULL,
    pair TEXT NOT NULL,
    current_price REAL NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    pnl_percent REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    trailing_stop REAL,
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_position_snapshots_trade` on `(trade_id, snapshot_time DESC)`

#### 6. `daily_summary` - Daily Performance Statistics
Aggregated daily metrics for reporting.

```sql
CREATE TABLE daily_summary (
    id INTEGER PRIMARY KEY,
    date TEXT UNIQUE NOT NULL,       -- YYYY-MM-DD
    trades_count INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    total_pnl REAL NOT NULL,
    win_rate REAL NOT NULL,
    avg_win REAL,
    avg_loss REAL,
    largest_win REAL,
    largest_loss REAL,
    total_volume REAL NOT NULL,
    scans_performed INTEGER NOT NULL,
    opportunities_found INTEGER NOT NULL,
    paper_trading BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_daily_summary_date` on `(date DESC)`

## Usage Examples

### Basic Initialization

```python
from lib.database import TradingDatabase

# Initialize database (auto-creates schema)
db = TradingDatabase('data/silktrader.db')
```

### Storing Market Data

```python
# Insert historical candles
candles = [
    {
        'timestamp': 1707584400,
        'open': 50000.0,
        'high': 51000.0,
        'low': 49500.0,
        'close': 50500.0,
        'volume': 1234.56
    },
    # ... more candles
]

inserted = db.insert_candles('BTC_USDT', '15M', candles)
print(f"Inserted {inserted} candles")

# Retrieve candles
candles = db.get_candles(
    pair='BTC_USDT',
    timeframe='15M',
    start_time=1707580000,
    limit=100
)
```

### Logging Trades

```python
from datetime import datetime

# Insert new trade
trade = {
    'trade_id': 'PAPER-BTC_USDT-1707584400',
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

trade_id = db.insert_trade(trade)

# Update trade on exit
exit_data = {
    'exit_price': 51500.0,
    'exit_time': datetime.now().isoformat(),
    'realized_pnl': 30.0,
    'pnl_percent': 3.0,
    'status': 'CLOSED'
}

db.update_trade_exit('PAPER-BTC_USDT-1707584400', exit_data)
```

### Storing Scanner Results

```python
import uuid
from datetime import datetime

scan_id = str(uuid.uuid4())
scan_time = datetime.now().isoformat()

results = [
    {
        'pair': 'ETH_USDT',
        'score': 85,
        'entry_price': 3000.0,
        'reasoning': 'Strong bullish momentum',
        'indicators': {
            'rsi': 65.5,
            'ema_fast': 2950.0,
            'ema_slow': 2900.0,
            'volume_ratio': 1.8
        },
        'affordable': True
    },
    # ... more results
]

db.insert_scan_results(scan_id, scan_time, results)
```

### Logging LLM Decisions

```python
decision = {
    'pair': 'SOL_USDT',
    'scanner_score': 85,
    'action': 'BUY',
    'confidence': 8,
    'reasoning': 'Technical confluence with strong volume',
    'indicators': {'rsi': 65, 'ema_trend': 'bullish'},
    'model': 'arcee-ai/arcee-trinity',
    'decision_time': datetime.now().isoformat()
}

db.insert_llm_decision(decision)
```

### Position Snapshots

```python
snapshot = {
    'trade_id': 'PAPER-BTC_USDT-1707584400',
    'pair': 'BTC_USDT',
    'current_price': 50500.0,
    'entry_price': 50000.0,
    'quantity': 0.02,
    'unrealized_pnl': 10.0,
    'pnl_percent': 1.0,
    'stop_loss': 49000.0,
    'take_profit': 52000.0,
    'snapshot_time': datetime.now().isoformat()
}

db.insert_position_snapshot(snapshot)
```

### Analytics Queries

```python
# Get trade statistics
stats = db.get_trade_statistics(
    paper_trading=True,
    start_date='2026-02-01T00:00:00'
)

print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Total P&L: ${stats['total_pnl']:.2f}")
print(f"Avg Win: ${stats['avg_win']:.2f}")
print(f"Avg Loss: ${stats['avg_loss']:.2f}")

# Get recent trades
trades = db.get_trades(
    status='CLOSED',
    paper_trading=True,
    limit=20
)

# Get scan history
scans = db.get_scan_history(
    pair='BTC_USDT',
    min_score=70,
    limit=50
)

# Update daily summary
db.update_daily_summary('2026-02-10', paper_trading=True)

# Get daily summaries
summaries = db.get_daily_summaries(start_date='2026-02-01', limit=30)
```

### Database Maintenance

```python
# Get database statistics
stats = db.get_database_stats()
print(f"Total trades: {stats['trades']}")
print(f"Total scans: {stats['scan_results']}")
print(f"Database size: {stats['database_size_mb']:.2f} MB")

# Backup database
db.backup_database('backups/silktrader_backup_2026-02-10.db')

# Close connection
db.close()
```

## Integration with SilkTrader Components

### In `silktrader_bot.py`

```python
from lib.database import TradingDatabase

class SilkTraderBot:
    def __init__(self, config_path: str = 'credentials/pionex.json', dry_run: bool = True):
        # ... existing initialization ...
        
        # Initialize database
        self.db = TradingDatabase('data/silktrader.db')
    
    def run_cycle(self):
        scan_id = str(uuid.uuid4())
        scan_time = datetime.now().isoformat()
        
        # Scan markets
        opportunities = self.scan_markets()
        
        # Log scan results
        if opportunities:
            self.db.insert_scan_results(scan_id, scan_time, opportunities)
        
        # ... rest of trading logic ...
```

### In `exchange_manager.py`

```python
def execute_trade(self, pair: str, side: str, entry_price: float, confidence: int):
    # ... existing trade execution ...
    
    if result['success']:
        # Log trade to database
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
        self.db.insert_trade(trade_data)
    
    return result
```

### In `llm_decision.py`

```python
def analyze_opportunity(self, pair: str, indicators: Dict, score: int) -> Dict:
    decision = # ... LLM analysis ...
    
    # Log decision to database
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
    self.db.insert_llm_decision(decision_data)
    
    return decision
```

## Best Practices

### 1. Regular Backups

```python
import schedule
from datetime import datetime

def backup_database():
    db = TradingDatabase()
    backup_path = f"backups/silktrader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    db.backup_database(backup_path)
    print(f"Backup created: {backup_path}")
    db.close()

# Schedule daily backups
schedule.every().day.at("00:00").do(backup_database)
```

### 2. Daily Summary Updates

```python
def end_of_day_tasks():
    db = TradingDatabase()
    today = datetime.now().strftime('%Y-%m-%d')
    db.update_daily_summary(today, paper_trading=True)
    db.close()
```

### 3. Position Monitoring

```python
def monitor_positions():
    db = TradingDatabase()
    open_trades = db.get_trades(status='OPEN', limit=100)
    
    for trade in open_trades:
        # Get current price and calculate P&L
        current_price = get_current_price(trade['pair'])
        
        snapshot = {
            'trade_id': trade['trade_id'],
            'pair': trade['pair'],
            'current_price': current_price,
            'entry_price': trade['entry_price'],
            'quantity': trade['quantity'],
            'unrealized_pnl': calculate_pnl(trade, current_price),
            'pnl_percent': calculate_pnl_percent(trade, current_price),
            'snapshot_time': datetime.now().isoformat()
        }
        
        db.insert_position_snapshot(snapshot)
    
    db.close()
```

### 4. Performance Analysis

```python
def generate_performance_report():
    db = TradingDatabase()
    
    # Overall statistics
    stats = db.get_trade_statistics(paper_trading=True)
    
    print("=" * 50)
    print("PERFORMANCE REPORT")
    print("=" * 50)
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Total P&L: ${stats['total_pnl']:.2f}")
    print(f"Average Win: ${stats['avg_win']:.2f}")
    print(f"Average Loss: ${stats['avg_loss']:.2f}")
    print(f"Largest Win: ${stats['largest_win']:.2f}")
    print(f"Largest Loss: ${stats['largest_loss']:.2f}")
    
    # Best performing pairs
    # ... query and display ...
    
    db.close()
```

## Migration Guide

The database uses a simple versioning system. Future schema changes will be handled automatically:

```python
class TradingDatabase:
    SCHEMA_VERSION = 2  # Increment for schema changes
    
    def _migrate_to_v2(self):
        # Migration logic here
        pass
```

## Troubleshooting

### Database Locked
If you get "database is locked" errors:
```python
# Increase timeout
db = TradingDatabase()
db._get_connection().execute("PRAGMA busy_timeout = 30000")  # 30 seconds
```

### Large Database Size
Archive old data:
```python
# Archive trades older than 1 year
conn = db._get_connection()
conn.execute("""
    DELETE FROM trades 
    WHERE entry_time < datetime('now', '-1 year')
    AND status = 'CLOSED'
""")
conn.commit()

# Vacuum to reclaim space
conn.execute("VACUUM")
```

### Query Performance
If queries are slow, check indexes:
```python
conn = db._get_connection()
cursor = conn.execute("SELECT * FROM sqlite_master WHERE type='index'")
for row in cursor:
    print(row)
```

## Testing

Run the included test:
```bash
python lib/database.py
```

This will create a test database and verify all operations work correctly.
