---
name: silktrader-scanner
description: Scan all Pionex USDT pairs and identify top trading opportunities using technical analysis
requires:
  python:
    - pandas>=2.0.0
    - TA-Lib>=0.4.28
    - requests>=2.31.0
  config:
    - ../../credentials/pionex.json
---

# SilkTrader v3 Market Scanner

Scans all available USDT trading pairs on Pionex and ranks them by technical setup quality.

## Usage

Scan for opportunities:
```bash
python scripts/scan_pairs.py --min-score 5 --limit 10
