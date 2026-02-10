#!/bin/bash
echo "🔒 SilkTrader v3 - Security Audit"
echo "=================================="
echo ""

echo "1️⃣ Finding all trading API calls..."
grep -rn "\.place_order\|\.cancel.*order" --include="*.py" lib/ skills/ *.py 2>/dev/null | wc -l
echo ""

echo "2️⃣ Checking dry_run defaults..."
grep "def __init__.*dry_run.*True" lib/exchange_manager.py silktrader_bot.py monitor_positions.py
echo ""

echo "3️⃣ Checking --live flag behavior..."
grep -A 3 "add_argument.*--live" silktrader_bot.py monitor_positions.py
echo ""

echo "4️⃣ Looking for hardcoded dry_run=False..."
FOUND=$(grep -rn "dry_run.*=.*False" --include="*.py" lib/ skills/ *.py 2>/dev/null)
if [ -z "$FOUND" ]; then
    echo "✅ No hardcoded dry_run=False found"
else
    echo "❌ Found hardcoded dry_run=False:"
    echo "$FOUND"
fi
echo ""

echo "5️⃣ Checking paper_trading flag consistency..."
grep -n "paper_trading.*True\|paper_trading.*self.dry" lib/exchange_manager.py
echo ""

echo "=================================="
echo "✅ Audit Complete"
