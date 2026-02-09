---
name: silktrader-trader
description: Execute crypto trades on Pionex with LLM decision-making and risk management
requires:
  python:
    - pandas>=2.0.0
    - TA-Lib>=0.4.28
    - requests>=2.31.0
  config:
    - ../../credentials/pionex.json
  env:
    - OPENROUTER_API_KEY
---

# SilkTrader v3 Trader

Executes trades based on LLM analysis with mandatory risk controls.

## Safety Features
- Position size limits
- Daily loss limits
- Stop-loss enforcement
- Pre-trade balance verification
- Automatic risk calculations based on ATR

## Usage

Analyze and potentially trade a pair:
```bash
python scripts/analyze_trade.py --pair ACE_USDT --auto-execute
