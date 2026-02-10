#!/bin/bash
# comprehensive_test.sh - Fixed paths

echo "🧪 SilkTrader v3 - Pre-Merge Test Suite"
echo "========================================"
echo ""

echo "1️⃣ Testing Database Module..."
python lib/database.py || exit 1
echo ""

echo "2️⃣ Testing Foundation..."
python tests/test_foundation.py || exit 1
echo ""

echo "3️⃣ Testing Scanner..."
python skills/silktrader-scanner/scripts/scan_pairs.py --min-score 5 --limit 3 || exit 1
echo ""

echo "4️⃣ Testing Main Bot..."
python silktrader_bot.py --once || exit 1
echo ""

echo "5️⃣ Testing Position Monitor..."
python monitor_positions.py --add "BTC_USDT,95000,0.001,93000,98000" --once || exit 1
echo ""

echo "6️⃣ Testing Sync Script..."
python scripts/sync_positions.py || exit 1
echo ""

echo "✅ All tests passed! Ready to merge."
