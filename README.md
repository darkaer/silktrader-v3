<p align="center">
  <img src="assets/logos/silktrader_logo.png" alt="SilkTrader v3 Logo" width="600"/>
</p>

<h1 align="center">SilkTrader v3</h1>

<p align="center">
  <strong>AI-Powered Autonomous Cryptocurrency Trading System</strong><br>
  for FlipperArmada | Created by <a href="https://github.com/Darkaer">Darkaer</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"/>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/status-beta-yellow" alt="Status"/>
</p>

---

## 🐧 About

SilkTrader v3 is an advanced, LLM-driven trading bot that autonomously scans crypto markets, analyzes opportunities using technical indicators, makes intelligent trading decisions, and executes trades with institutional-grade risk management.

Developed by **Darkaer** for the **FlipperArmada** community.


**AI-Powered Autonomous Cryptocurrency Trading System**


![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Status](https://img.shields.io/badge/status-beta-yellow)

## ✨ Features

- 🔍 **Real-time Market Scanner** - Scans 300+ trading pairs in under 2 minutes
- 🧠 **AI Decision Engine** - Uses LLMs (Claude, GPT-4, or local Ollama) for trade analysis
- 📊 **Technical Analysis** - TA-Lib powered indicators (EMA, RSI, MACD, ATR, Volume)
- 🛡️ **Risk Management** - Position sizing, stop losses, take profits, daily limits
- 📈 **Position Monitor** - Real-time P&L tracking with trailing stops
- 🔌 **OpenClaw Integration** - Works as OpenClaw skills for natural language trading
- 📱 **Telegram Ready** - Alert system support (coming soon)

## 🏗️ Architecture

File: README.md (Complete - Ready to Copy)

text
# 🚀 SilkTrader v3

**AI-Powered Autonomous Cryptocurrency Trading System**

SilkTrader v3 is an advanced, LLM-driven trading bot that autonomously scans crypto markets, analyzes opportunities using technical indicators, makes intelligent trading decisions, and executes trades with institutional-grade risk management.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Status](https://img.shields.io/badge/status-beta-yellow)

## ✨ Features

- 🔍 **Real-time Market Scanner** - Scans 300+ trading pairs in under 2 minutes
- 🧠 **AI Decision Engine** - Uses LLMs (Claude, GPT-4, or local Ollama) for trade analysis
- 📊 **Technical Analysis** - TA-Lib powered indicators (EMA, RSI, MACD, ATR, Volume)
- 🛡️ **Risk Management** - Position sizing, stop losses, take profits, daily limits
- 📈 **Position Monitor** - Real-time P&L tracking with trailing stops
- 🔌 **OpenClaw Integration** - Works as OpenClaw skills for natural language trading
- 📱 **Telegram Ready** - Alert system support (coming soon)

## 🏗️ Architecture

┌─────────────────────────────────────┐
│ User / OpenClaw Interface │
└──────────────┬──────────────────────┘
│
┌──────────────▼──────────────────────┐
│ SilkTrader Bot │
├─────────────────────────────────────┤
│ - Market Scanner │
│ - LLM Decision Engine │
│ - Trade Executor │
│ - Position Monitor │
└──────────────┬──────────────────────┘
│
┌──────────────▼──────────────────────┐
│ Exchange API (Pionex) │
└─────────────────────────────────────┘

## 🚀 Quick Start

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md) - Detailed setup instructions
- [Configuration Guide](docs/CONFIGURATION.md) - All configuration options
- [Examples](examples/) - Usage examples and scripts
- [API Reference](docs/API_REFERENCE.md) - Core library documentation

## 🧪 Testing

# Run all tests
python -m pytest tests/

# Test specific component
python tests/test_foundation.py
python tests/test_llm.py

### Prerequisites

- Python 3.12+ (3.13 recommended)
- Arch Linux (or any Linux distro)
- Pionex API credentials
- OpenRouter API key (or local Ollama)

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/silktrader-v3.git
cd silktrader-v3

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install TA-Lib (Arch Linux)
yay -S ta-lib
pip install TA-Lib

Configuration

    Copy credentials template:
cp credentials/pionex.json.example credentials/pionex.json

Edit credentials/pionex.json with your API keys:
{
  "PIONEX_API_KEY": "your-api-key",
  "PIONEX_API_SECRET": "your-api-secret",
  "risk_limits": {
    "max_position_size_usdt": 500,
    "max_open_positions": 3,
    "max_daily_loss_usdt": 200
  }
}


    Set environment variables:
export OPENROUTER_API_KEY="your-openrouter-key"


📖 Usage
Test Foundation
# Test API connection and indicators
python test_foundation.py

Scan Market
# Find top trading opportunities
python skills/silktrader-scanner/scripts/scan_pairs.py --min-score 5 --limit 10

Analyze Single Pair
# Get AI analysis for specific pair
python skills/silktrader-trader/scripts/analyze_trade.py --pair BTC_USDT --auto-execute

Run Autonomous Bot
# Dry run (paper trading)
python silktrader_bot.py --once

# Continuous mode (scan every 15 minutes)
python silktrader_bot.py --interval 900

# Live trading (REAL MONEY - use with caution!)
python silktrader_bot.py --live --interval 900

Monitor Positions
# Monitor open positions (check every 30 seconds)
python monitor_positions.py --interval 30

# Add position manually for testing
python monitor_positions.py --add "BTC_USDT,50000,0.01,48500,52500"

🔧 OpenClaw Integration

SilkTrader v3 works as OpenClaw skills for natural language trading:
# Add to OpenClaw workspace
ln -s /path/to/silktrader-v3 ~/.openclaw/workspaces/silktrader

# Use with natural language
User: "Scan Pionex for trading opportunities"
User: "Analyze ACE_USDT for potential trade"
User: "Check my open positions"

📊 Technical Indicators

SilkTrader uses multiple indicator categories for confluence:

    Trend: EMA(21), EMA(50)

    Momentum: RSI(14), MACD(12,26,9)

    Volume: Volume MA(20), Volume Ratio

    Volatility: ATR(14)

Each opportunity is scored 0-7 based on indicator alignment.
🛡️ Risk Management

    Position Sizing: 2% risk per trade based on ATR stop loss

    Max Position: $500 per trade (configurable)

    Max Positions: 3 concurrent (configurable)

    Stop Loss: 2x ATR below entry

    Take Profit: 3x ATR above entry (1.5:1 R:R minimum)

    Trailing Stop: Activates at 3% profit, trails 1.5% below price

    Daily Limits: Max 10 trades, max $200 loss per day

📁 Project Structure
silktrader-v3/
├── silktrader_bot.py           # Main autonomous bot
├── monitor_positions.py         # Position monitoring
├── test_foundation.py          # Foundation tests
├── requirements.txt            # Python dependencies
├── lib/                        # Core libraries
│   ├── pionex_api.py          # Exchange API client
│   ├── indicators.py          # Technical analysis
│   ├── llm_decision.py        # AI decision engine
│   └── config.py              # Configuration
├── skills/                     # OpenClaw skills
│   ├── silktrader-scanner/    # Market scanner
│   ├── silktrader-trader/     # Trade executor
│   └── silktrader-monitor/    # Position monitor
├── credentials/                # API keys (gitignored)
│   └── pionex.json.example    # Template
├── data/                       # Runtime data
│   └── positions.json         # Open positions
└── logs/                       # Trading logs
    └── trading_log.txt        # Activity log


⚙️ Configuration

All settings in credentials/pionex.json:
{
  "risk_limits": {
    "max_position_size_usdt": 500,
    "max_open_positions": 3,
    "max_daily_loss_usdt": 200,
    "max_daily_trades": 10,
    "stop_loss_percent": 3.0,
    "take_profit_percent": 6.0
  },
  "scanner_config": {
    "min_volume_usdt_24h": 1000000,
    "timeframe": "15M",
    "scan_interval_seconds": 900,
    "min_score": 5,
    "top_pairs_limit": 5
  },
  "indicator_params": {
    "ema_fast": 21,
    "ema_slow": 50,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14
  }
}

🧪 Testing
Paper Trading (Recommended)

    Run bot in dry-run mode for 1-2 weeks

    Monitor performance metrics

    Tune parameters based on results

    Validate win rate ≥50% before going live

Backtesting (Coming Soon)
python backtest.py --start 2025-01-01 --end 2026-01-01

📈 Performance Metrics

Track these metrics during paper trading:

    Win Rate: % of profitable trades

    Profit Factor: Avg win / Avg loss

    Sharpe Ratio: Risk-adjusted returns

    Max Drawdown: Largest peak-to-trough decline

    Avg Trade Duration: Time in market

⚠️ Warnings

    NOT FINANCIAL ADVICE: This is experimental software

    RISK OF LOSS: Cryptocurrency trading involves substantial risk

    TEST FIRST: Always paper trade before using real money

    START SMALL: Begin with minimal capital ($50-100)

    MONITOR CLOSELY: Check bot regularly, especially during first weeks

    NO GUARANTEES: Past performance does not indicate future results

🛣️ Roadmap

    Market scanner with technical analysis

    LLM decision engine integration

    Risk management system

    Position monitoring with trailing stops

    OpenClaw skills integration

    Telegram notification system

    Backtesting framework

    Multi-exchange support (Binance, Bybit)

    Web dashboard

    Advanced strategies (mean reversion, breakouts)

    Portfolio rebalancing

    Machine learning signal optimization

🤝 Contributing

Contributions welcome! Please:

    Fork the repository

    Create feature branch (git checkout -b feature/amazing-feature)

    Commit changes (git commit -m 'Add amazing feature')

    Push to branch (git push origin feature/amazing-feature)

    Open Pull Request

📝 License

This project is licensed under the MIT License - see LICENSE file for details.
🙏 Acknowledgments

    OpenClaw - AI agent framework

    TA-Lib - Technical analysis library

    OpenRouter - LLM API aggregation

    Pionex - Cryptocurrency exchange

📞 Support

    Issues: GitHub Issues

    Discussions: GitHub Discussions

⚖️ Disclaimer

This software is provided "as is" without warranty of any kind. Trading cryptocurrencies carries substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always do your own research and never invest more than you can afford to lose.

Made with ❤️  for the FlipperArmada community.
