# Sample Workflow

## 1. Test Setup
```bash
# Verify API connection
python tests/test_foundation.py

# Test LLM integration
python tests/test_llm.py

2. Manual Analysis

bash
# Scan market
python skills/silktrader-scanner/scripts/scan_pairs.py --min-score 6 --limit 5

# Analyze specific pair
python skills/silktrader-trader/scripts/analyze_trade.py --pair ACE_USDT

3. Run Bot (Dry Run)

bash
# Single cycle
python silktrader_bot.py --once

# Continuous (15 min intervals)
python silktrader_bot.py --interval 900

4. Monitor Positions

bash
# In separate terminal
python monitor_positions.py --interval 30

5. Review Logs

bash
tail -f logs/trading_log.txt
