#!/bin/bash
echo "🔒 Focused Security Audit (Our Code Only)"
echo "========================================"

# Exclude venv and cache
EXCLUDE="--exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=.git"

echo "1️⃣ Checking dry_run defaults in our code..."
grep -rn "def __init__.*dry_run.*=.*False" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "❌ Found unsafe defaults!"
else
    echo "✅ All defaults safe"
fi

echo -e "\n2️⃣ Checking API trading calls..."
CALLS=$(grep -rn "\.place_order\|\.cancel_order" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null | grep -v "def " | wc -l)
echo "Found $CALLS API calls:"
grep -rn "\.place_order\|\.cancel_order" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null | grep -v "def "

echo -e "\n3️⃣ Checking for unprotected trading..."
grep -B 5 "\.place_order" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null | grep -A 5 "if.*dry_run"

echo -e "\n4️⃣ Checking hardcoded paper_trading=False..."
grep -rn "paper_trading.*=.*False" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null | grep -v "self.dry_run"
if [ $? -eq 0 ]; then
    echo "⚠️ Found hardcoded paper_trading=False"
else
    echo "✅ No hardcoded paper_trading=False"
fi

echo -e "\n5️⃣ Checking eval/exec usage..."
grep -rn "eval(\|exec(" $EXCLUDE --include="*.py" lib/ skills/ *.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "❌ Found eval/exec in our code!"
else
    echo "✅ No eval/exec in our code"
fi

echo -e "\n========================================"
echo "✅ Focused audit complete"
