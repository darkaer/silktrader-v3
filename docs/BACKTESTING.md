# SilkTrader v3 - Backtesting Guide

## Overview

The backtesting system allows you to validate your trading strategy on historical data before risking real capital. It simulates realistic trading conditions including:

- ✅ **Realistic costs**: Trading fees (0.05%) + slippage (0.1%)
- ✅ **Risk management**: Position sizing, stop losses, take profits, trailing stops
- ✅ **Market scanning**: Uses your actual scanner logic with configurable min_score
- ✅ **Multiple positions**: Respects max_open_positions limit
- ✅ **Bar-by-bar replay**: No lookahead bias

## Quick Start

### Run a Quick Test (Recommended First)

```bash
# Test strategy over last 3 days with top 10 pairs
python backtest.py --quick-test 3d

# Test last week with top 20 pairs
python backtest.py --quick-test 1w --top 20

# Test last month with $500 starting balance
python backtest.py --quick-test 1m --balance 500
```

### Run Custom Date Range

```bash
# Test specific period
python backtest.py --start 2026-01-01 --end 2026-01-31

# Test with specific pairs
python backtest.py --start 2026-01-15 --end 2026-02-10 --pairs BTC_USDT,ETH_USDT,BNB_USDT

# Export results to JSON
python backtest.py --quick-test 1w --output results/backtest_$(date +%Y%m%d).json
```

## Command-Line Options

### Date Range
```bash
--start YYYY-MM-DD      # Start date for backtest
--end YYYY-MM-DD        # End date for backtest
--quick-test MODE       # Quick test: 1d, 3d, 1w, 2w, 1m
```

### Pair Selection
```bash
--pairs PAIR1,PAIR2     # Specific pairs (e.g., BTC_USDT,ETH_USDT)
--top N                 # Use top N pairs by 24h volume (e.g., --top 20)
```

### Trading Parameters
```bash
--balance AMOUNT        # Initial USDT balance (default: 1000)
--fee PERCENT          # Trading fee percent (default: 0.05)
--slippage PERCENT     # Slippage percent (default: 0.1)
--scan-interval HOURS  # Hours between scans (default: 1)
```

### Configuration
```bash
--config PATH          # Path to config file (default: credentials/pionex.json)
--output PATH          # Export results to JSON file
```

## Understanding Results

### Financial Performance

- **Initial/Final Balance**: Your account value at start/end
- **Total P&L**: Total profit or loss in USDT
- **ROI**: Return on Investment as percentage
- **Max Drawdown**: Largest peak-to-trough decline (lower is better)

### Trading Statistics

- **Total Trades**: Number of completed trades
- **Win Rate**: Percentage of profitable trades (target: ≥50%)
- **Profit Factor**: Total wins ÷ Total losses (target: >1.5)

### P&L Breakdown

- **Average P&L**: Average profit/loss per trade
- **Average Win**: Average profit on winning trades
- **Average Loss**: Average loss on losing trades
- **Best/Worst Trade**: Your biggest win and loss

### Example Output

```
📈 BACKTEST RESULTS
======================================================================

💰 Financial Performance:
   Initial Balance: $1000.00
   Final Balance: $1085.50
   Total P&L: +$85.50
   ROI: +8.55%
   Max Drawdown: 3.20%

📊 Trading Statistics:
   Total Trades: 24
   Winning Trades: 14
   Losing Trades: 10
   Win Rate: 58.33%
   Profit Factor: 1.85

💵 P&L Breakdown:
   Average P&L: +$3.56
   Average Win: +$12.45
   Average Loss: -$6.73

⏱️  Timing:
   Average Hold Time: 4.2 hours

🏆 Best Trade:
   BTC_USDT: +$28.50 (+5.70%)

💔 Worst Trade:
   ETH_USDT: -$15.20 (-3.04%)
```

## Interpreting Results

### ✅ Good Signs

- **Win Rate ≥50%**: Strategy has edge
- **Profit Factor >1.5**: Wins are larger than losses
- **Max Drawdown <10%**: Manageable risk
- **Average Win > 2x Average Loss**: Good risk/reward
- **ROI >0%**: Strategy is profitable

### ⚠️ Warning Signs

- **Win Rate <40%**: Too many losing trades
- **Profit Factor <1.0**: Losing more than winning
- **Max Drawdown >20%**: High risk
- **Average Win < Average Loss**: Poor risk/reward
- **ROI <0%**: Losing strategy

### 🔴 Red Flags

- **Win Rate <30%**: Strategy fundamentally broken
- **Profit Factor <0.5**: Massive losses
- **Max Drawdown >50%**: Account blown up
- **All trades stopped out**: Entry timing terrible

## Optimization Workflow

### 1. Baseline Test (Current Settings)

```bash
# Test current strategy over 1 week
python backtest.py --quick-test 1w --output results/baseline.json
```

**Analyze**:
- Is win rate ≥50%?
- Is profit factor >1.5?
- Are you profitable?

### 2. Adjust Scanner Threshold

If too many losing trades, raise the min_score in `credentials/pionex.json`:

```json
{
  "scanner_config": {
    "min_score": 6  // Changed from 5 → 6 (more selective)
  }
}
```

Test again:
```bash
python backtest.py --quick-test 1w --output results/min_score_6.json
```

### 3. Adjust Risk Parameters

If drawdown is too high, tighten stops:

```json
{
  "risk_limits": {
    "stop_loss_percent": 2.5,  // Changed from 3.0 → 2.5
    "take_profit_percent": 5.0  // Changed from 6.0 → 5.0
  }
}
```

### 4. Compare Results

```bash
# View multiple test results
ls -lh results/
cat results/baseline.json | jq '.results.roi_percent'
cat results/min_score_6.json | jq '.results.roi_percent'
```

### 5. Test Different Timeframes

Edit `credentials/pionex.json`:
```json
{
  "scanner_config": {
    "timeframe": "30M"  // Test 30-minute instead of 15-minute
  }
}
```

## Best Practices

### ✅ Do This

1. **Start small**: Test 3-7 days first, then expand
2. **Use top pairs**: High volume = better fills in reality
3. **Test recent data**: Market conditions change
4. **Export results**: Keep records of all tests
5. **Compare multiple configs**: A/B test your changes
6. **Validate with paper trading**: Backtest → Paper → Live

### ❌ Don't Do This

1. **Over-optimize**: Don't tune until results are "perfect"
2. **Cherry-pick dates**: Test various periods, not just bull runs
3. **Ignore costs**: Always include realistic fees/slippage
4. **Test too far back**: Old data may not reflect current market
5. **Skip validation**: Always paper trade after backtesting

## Data Limitations

### Historical Data Availability

- **Pionex API**: ~1000 candles per request
- **15M timeframe**: ~10 days of history
- **30M timeframe**: ~20 days of history
- **1H timeframe**: ~40 days of history

**Workaround**: For longer backtests, cache historical data to database:
```bash
# TODO: Add data caching utility
python scripts/cache_historical_data.py --days 90
```

### Known Issues

1. **Gap handling**: Backtest doesn't simulate exchange outages
2. **Order book depth**: Assumes your order always fills at target price (+ slippage)
3. **Market impact**: Assumes you don't move the market (valid for small positions)

## Advanced Usage

### Test Multiple Configurations

```bash
#!/bin/bash
# test_configs.sh - Test multiple parameter combinations

for score in 5 6 7; do
  for sl in 2.5 3.0 3.5; do
    echo "Testing min_score=$score, stop_loss=$sl%"
    
    # Update config
    jq ".scanner_config.min_score = $score | .risk_limits.stop_loss_percent = $sl" \
      credentials/pionex.json > credentials/pionex.tmp.json
    
    # Run backtest
    python backtest.py --quick-test 1w --config credentials/pionex.tmp.json \
      --output "results/score_${score}_sl_${sl}.json"
  done
done

echo "\nResults summary:"
for f in results/*.json; do
  roi=$(jq -r '.results.roi_percent' $f)
  echo "$f: ROI = $roi%"
done
```

### Analyze Trade Details

```python
#!/usr/bin/env python3
# analyze_backtest.py - Detailed analysis of backtest results

import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

results = data['results']
trades = results['all_trades']

print(f"\nTrade Analysis:")
print(f"Total trades: {len(trades)}")

# Analyze by pair
from collections import defaultdict
pair_stats = defaultdict(lambda: {'trades': 0, 'pnl': 0})

for trade in trades:
    pair = trade['pair']
    pair_stats[pair]['trades'] += 1
    pair_stats[pair]['pnl'] += trade['pnl_usdt']

print(f"\nPer-pair performance:")
for pair in sorted(pair_stats, key=lambda p: pair_stats[p]['pnl'], reverse=True):
    stats = pair_stats[pair]
    print(f"  {pair}: {stats['trades']} trades, ${stats['pnl']:+.2f}")
```

## Troubleshooting

### "Insufficient data" errors

**Problem**: Not enough historical candles for indicators

**Solution**:
- Reduce timeframe (1H → 30M → 15M)
- Test shorter date ranges
- Use pairs with longer history

### No trades executed

**Problem**: Scanner not finding opportunities

**Solution**:
- Lower `min_score` in config (try 4 or 5)
- Increase number of pairs tested
- Check if data is available for selected dates

### All trades stopped out

**Problem**: Entry timing or stop loss too tight

**Solution**:
- Increase `stop_loss_percent` (3% → 4%)
- Raise `min_score` for better quality setups
- Test different timeframes

## Next Steps

After backtesting shows positive results:

1. **Paper trade**: Run live bot in paper mode for 1-2 weeks
   ```bash
   python silktrader_bot.py --interval 900
   ```

2. **Compare results**: Backtest vs paper trading
   ```bash
   python analyze_overnight.py
   ```

3. **Iterate**: Adjust based on paper trading results

4. **Go live**: Start with minimal capital ($50-100)
   ```bash
   python silktrader_bot.py --live --interval 900
   ```

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/darkaer/silktrader-v3/issues)
- **Discussions**: [Ask questions](https://github.com/darkaer/silktrader-v3/discussions)
- **Documentation**: [Full docs](../README.md)

---

**Remember**: Backtesting is validation, not prediction. Always paper trade before going live!
