# Configuration Guide

## credentials/pionex.json Structure

### API Configuration
```json
{
  "PIONEX_API_KEY": "your-key",
  "PIONEX_API_SECRET": "your-secret",
  "base_url": "https://api.pionex.com"
}

Risk Limits

json
{
  "risk_limits": {
    "max_position_size_usdt": 500,      // Max $ per trade
    "max_open_positions": 3,             // Max concurrent trades
    "max_daily_loss_usdt": 200,         // Stop trading if loss exceeds
    "max_daily_trades": 10,             // Max trades per day
    "stop_loss_percent": 3.0,           // Stop loss percentage
    "take_profit_percent": 6.0          // Take profit percentage
  }
}

Scanner Configuration

json
{
  "scanner_config": {
    "min_volume_usdt_24h": 1000000,    // Min 24h volume filter
    "timeframe": "15M",                 // Candle timeframe
    "scan_interval_seconds": 900,       // How often to scan
    "min_score": 5,                     // Minimum technical score
    "top_pairs_limit": 5                // How many to analyze
  }
}

Indicator Parameters

json
{
  "indicator_params": {
    "ema_fast": 21,
    "ema_slow": 50,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "volume_ma_period": 20
  }
}

Environment Variables

bash
export OPENROUTER_API_KEY="sk-or-..."
export TELEGRAM_BOT_TOKEN="..."  # Optional

Recommended Settings
Conservative (Beginner)

    max_position_size_usdt: 100

    max_open_positions: 2

    max_daily_loss_usdt: 50

    min_score: 6

Moderate (Intermediate)

    max_position_size_usdt: 500

    max_open_positions: 3

    max_daily_loss_usdt: 200

    min_score: 5

Aggressive (Advanced)

    max_position_size_usdt: 1000

    max_open_positions: 5

    max_daily_loss_usdt: 500

    min_score: 4
