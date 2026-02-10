#!/bin/bash
echo "🔒 COMPLETE SECURITY AUDIT - SilkTrader v3"
echo "=========================================="
date
echo ""

cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ISSUES=0

echo "1️⃣ Checking all Python files..."
FILES=$(find . -name "*.py" -type f | grep -v __pycache__ | wc -l)
echo "   Found $FILES Python files"
echo ""

echo "2️⃣ Checking API trading calls protection..."
UNPROTECTED=$(grep -rn "api\.place_order\|self\.api\.place_order" --include="*.py" . 2>/dev/null | grep -v "def \|#" | wc -l)
if [ "$UNPROTECTED" -gt 3 ]; then
    echo -e "   ${RED}⚠️  Found $UNPROTECTED API calls - review needed${NC}"
    ISSUES=$((ISSUES+1))
else
    echo -e "   ${GREEN}✅ API calls: $UNPROTECTED (centralized)${NC}"
fi
echo ""

echo "3️⃣ Checking dry_run defaults..."
BAD_DEFAULTS=$(grep -rn "def __init__.*dry_run.*=.*False" --include="*.py" . 2>/dev/null | wc -l)
if [ "$BAD_DEFAULTS" -gt 0 ]; then
    echo -e "   ${RED}❌ Found $BAD_DEFAULTS unsafe defaults!${NC}"
    grep -rn "def __init__.*dry_run.*=.*False" --include="*.py" . 2>/dev/null
    ISSUES=$((ISSUES+1))
else
    echo -e "   ${GREEN}✅ All defaults safe (dry_run=True)${NC}"
fi
echo ""

echo "4️⃣ Checking for hardcoded credentials..."
HARDCODED=$(grep -rn "api_key.*=.*['\"][A-Za-z0-9]{10}" --include="*.py" . 2>/dev/null | grep -v "get(\|config\|example" | wc -l)
if [ "$HARDCODED" -gt 0 ]; then
    echo -e "   ${RED}❌ Found $HARDCODED potential hardcoded keys!${NC}"
    ISSUES=$((ISSUES+1))
else
    echo -e "   ${GREEN}✅ No hardcoded credentials${NC}"
fi
echo ""

echo "5️⃣ Checking hardcoded paper_trading=False..."
PAPER_FALSE=$(grep -rn "paper_trading.*=.*False" --include="*.py" . 2>/dev/null | grep -v "def \|#\|self.dry_run" | wc -l)
if [ "$PAPER_FALSE" -gt 0 ]; then
    echo -e "   ${YELLOW}⚠️  Found $PAPER_FALSE paper_trading=False${NC}"
    grep -rn "paper_trading.*=.*False" --include="*.py" . 2>/dev/null | grep -v "def \|#\|self.dry_run"
else
    echo -e "   ${GREEN}✅ No hardcoded paper_trading=False${NC}"
fi
echo ""

echo "6️⃣ Checking executable scripts..."
EXECUTABLES=$(find . -name "*.py" -executable -type f | wc -l)
echo "   Found $EXECUTABLES executable scripts"
find . -name "*.py" -executable -type f
echo ""

echo "7️⃣ Checking --live flag handling..."
LIVE_FLAGS=$(grep -rn "add_argument.*--live" --include="*.py" . 2>/dev/null | wc -l)
echo "   Found $LIVE_FLAGS scripts with --live flag"
grep -rn "add_argument.*--live" --include="*.py" . 2>/dev/null
echo ""

echo "8️⃣ Checking main entry points..."
MAINS=$(grep -rn "if __name__.*main" --include="*.py" . 2>/dev/null | wc -l)
echo "   Found $MAINS main entry points"
echo ""

echo "9️⃣ Critical files review..."
CRITICAL_FILES=(
    "lib/exchange_manager.py"
    "lib/pionex_api.py"
    "silktrader_bot.py"
    "monitor_positions.py"
    "skills/silktrader-trader/scripts/risk_manager.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✅${NC} $file exists"
        
        # Check if it has dry_run parameter
        if grep -q "dry_run" "$file" 2>/dev/null; then
            echo "      - Has dry_run protection"
        fi
        
        # Check if it calls place_order
        if grep -q "place_order" "$file" 2>/dev/null; then
            echo "      - Contains trading calls"
        fi
    else
        echo -e "   ${RED}❌${NC} $file MISSING"
        ISSUES=$((ISSUES+1))
    fi
done
echo ""

echo "🔟 Checking for dangerous patterns..."
echo ""

echo "   a) Checking for eval/exec usage..."
DANGEROUS=$(grep -rn "eval(\|exec(" --include="*.py" . 2>/dev/null | wc -l)
if [ "$DANGEROUS" -gt 0 ]; then
    echo -e "      ${RED}⚠️  Found $DANGEROUS eval/exec calls${NC}"
    ISSUES=$((ISSUES+1))
else
    echo -e "      ${GREEN}✅ No eval/exec usage${NC}"
fi

echo "   b) Checking for shell injection risks..."
SHELL=$(grep -rn "os\.system\|subprocess\.call.*shell=True" --include="*.py" . 2>/dev/null | wc -l)
if [ "$SHELL" -gt 0 ]; then
    echo -e "      ${YELLOW}⚠️  Found $SHELL potential shell injection points${NC}"
else
    echo -e "      ${GREEN}✅ No shell injection risks${NC}"
fi

echo "   c) Checking for SQL injection risks..."
SQL=$(grep -rn "execute.*%\|execute.*format" --include="*.py" . 2>/dev/null | grep -v "execute_query" | wc -l)
if [ "$SQL" -gt 0 ]; then
    echo -e "      ${YELLOW}⚠️  Found $SQL potential SQL injection points${NC}"
else
    echo -e "      ${GREEN}✅ No SQL injection risks${NC}"
fi

echo ""
echo "=========================================="
if [ "$ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✅ AUDIT PASSED - No critical issues found${NC}"
    exit 0
else
    echo -e "${RED}❌ AUDIT FOUND $ISSUES ISSUES - Review required${NC}"
    exit 1
fi
