#!/bin/bash
# SilkTrader v3 - Backtesting Example Workflow
# This script demonstrates how to use the backtesting system

set -e

echo "========================================"
echo "SilkTrader v3 - Backtesting Workflow"
echo "========================================"
echo ""

# Create results directory
mkdir -p results

# Step 1: Quick baseline test
echo "Step 1: Running baseline test (last 3 days, current config)..."
python backtest.py --quick-test 3d --output results/baseline.json

echo ""
echo "Baseline test complete! Check results above."
echo ""
read -p "Press Enter to continue to Step 2..."

# Step 2: Test with higher min_score
echo ""
echo "Step 2: Testing with min_score = 6 (more selective)..."
echo "(This requires temporarily editing your config)"
echo ""
echo "Manually edit credentials/pionex.json and change:"
echo '  "min_score": 5  -->  "min_score": 6'
echo ""
read -p "Press Enter after editing config..."

python backtest.py --quick-test 3d --output results/min_score_6.json

echo ""
echo "High selectivity test complete!"
echo ""
read -p "Press Enter to continue to Step 3..."

# Step 3: Test with top 20 pairs (more opportunities)
echo ""
echo "Step 3: Testing with top 20 pairs by volume..."
python backtest.py --quick-test 3d --top 20 --output results/top20_pairs.json

echo ""
echo "Top 20 pairs test complete!"
echo ""
read -p "Press Enter to continue to Step 4..."

# Step 4: Test with different balance
echo ""
echo "Step 4: Testing with $500 starting balance..."
python backtest.py --quick-test 3d --balance 500 --output results/balance_500.json

echo ""
echo "Small account test complete!"
echo ""

# Compare results
echo "========================================"
echo "Results Summary"
echo "========================================"
echo ""

if command -v jq &> /dev/null; then
    echo "Test | ROI | Win Rate | Profit Factor | Max DD"
    echo "-----|-----|----------|---------------|--------"
    
    for test in baseline min_score_6 top20_pairs balance_500; do
        file="results/${test}.json"
        if [ -f "$file" ]; then
            roi=$(jq -r '.results.roi_percent' "$file" 2>/dev/null || echo "N/A")
            winrate=$(jq -r '.results.win_rate' "$file" 2>/dev/null || echo "N/A")
            pf=$(jq -r '.results.profit_factor' "$file" 2>/dev/null || echo "N/A")
            dd=$(jq -r '.results.max_drawdown' "$file" 2>/dev/null || echo "N/A")
            
            printf "%-20s | %6.2f%% | %8.2f%% | %13.2f | %6.2f%%\n" \
                "$test" "$roi" "$winrate" "$pf" "$dd"
        fi
    done
    
    echo ""
    echo "Legend:"
    echo "  ROI = Return on Investment"
    echo "  Win Rate = Percentage of profitable trades"
    echo "  Profit Factor = Total Wins / Total Losses (>1.5 is good)"
    echo "  Max DD = Maximum Drawdown (lower is better)"
    echo ""
else
    echo "Install 'jq' for formatted comparison:"
    echo "  sudo pacman -S jq  # Arch Linux"
    echo ""
    echo "Results saved to results/ directory"
    ls -lh results/*.json
fi

echo ""
echo "========================================"
echo "Next Steps"
echo "========================================"
echo ""
echo "1. Review the results above"
echo "2. Choose the best-performing configuration"
echo "3. Run a longer backtest (1 week):"
echo "     python backtest.py --quick-test 1w --output results/final_test.json"
echo ""
echo "4. If results are positive (ROI >0%, Win Rate >50%):"
echo "   - Paper trade for 1-2 weeks to verify"
echo "   - Monitor with: python analyze_overnight.py"
echo ""
echo "5. For detailed analysis:"
echo "     python examples/analyze_backtest_results.py results/final_test.json"
echo ""
echo "See docs/BACKTESTING.md for full guide!"
echo ""
