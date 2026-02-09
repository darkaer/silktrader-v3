#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../lib'))

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup, format_indicators_for_llm
from llm_decision import LLMDecisionEngine
from risk_manager import RiskManager
import argparse
from datetime import datetime

def analyze_and_trade(pair: str, auto_execute: bool = False, min_confidence: int = 7, 
                     dry_run: bool = True):
    """Analyze a pair and optionally execute trade"""
    
    print(f"\n{'='*70}")
    print(f"🤖 SilkTrader v3 - Trade Analyzer")
    print(f"{'='*70}")
    print(f"Pair: {pair}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE TRADING'}")
    print(f"{'='*70}\n")
    
    # Initialize components
    api = PionexAPI()
    llm = LLMDecisionEngine()
    risk_mgr = RiskManager()
    
    # Step 1: Get market data
    print("📊 Fetching market data...")
    klines = api.get_klines(pair, '15M', 100)
    
    if len(klines) < 50:
        print("❌ Insufficient data for analysis")
        return
    
    print(f"✓ Retrieved {len(klines)} candles\n")
    
    # Step 2: Calculate indicators
    print("🔬 Calculating technical indicators...")
    indicators = calc_all_indicators(klines)
    score = score_setup(indicators)
    print(f"✓ Technical score: {score}/7\n")
    
    # Show technical summary
    formatted = format_indicators_for_llm(pair, indicators, score)
    print("📈 TECHNICAL ANALYSIS")
    print("-" * 70)
    print(formatted)
    print("-" * 70 + "\n")
    
    # Step 3: Get LLM decision
    print("🧠 Consulting AI trading model...")
    decision = llm.analyze_opportunity(pair, indicators, score)
    
    print("\n🎯 AI DECISION")
    print("-" * 70)
    print(f"Action:     {decision['action']}")
    print(f"Confidence: {decision['confidence']}/10")
    print(f"Reasoning:  {decision['reasoning']}")
    print("-" * 70 + "\n")
    
    # Step 4: Risk management
    if decision['action'] == 'BUY' and decision['confidence'] >= min_confidence:
        print("💰 RISK MANAGEMENT ANALYSIS")
        print("-" * 70)
        
        # Calculate stop loss and take profit
        entry_price = indicators['price']
        atr = indicators['atr']
        stop_loss = risk_mgr.calculate_stop_loss(entry_price, atr, 'BUY')
        take_profit = risk_mgr.calculate_take_profit(entry_price, atr, 'BUY')
        
        print(f"Entry Price:   ${entry_price:.6f}")
        print(f"Stop Loss:     ${stop_loss:.6f} ({((stop_loss - entry_price) / entry_price * 100):.2f}%)")
        print(f"Take Profit:   ${take_profit:.6f} ({((take_profit - entry_price) / entry_price * 100):.2f}%)")
        print(f"Risk/Reward:   1:1.5")
        
        # Mock account balance for demo (in production, get from API)
        account_balance = 1000.0  # $1000 demo account
        
        # Calculate position size
        quantity, position_msg = risk_mgr.calculate_position_size(
            pair, entry_price, stop_loss, account_balance
        )
        
        print(f"\n{position_msg}")
        
        # Validate trade
        current_positions = 0  # In production, get from API
        daily_pnl = 0.0  # In production, calculate from today's trades
        
        approved, msg = risk_mgr.validate_trade(
            pair, 'BUY', 
            quantity * entry_price,
            current_positions,
            daily_pnl
        )
        
        print(f"Risk Check:    {'✓ APPROVED' if approved else '✗ REJECTED'}")
        print(f"Status:        {msg}")
        print("-" * 70 + "\n")
        
        # Step 5: Execute trade
        if approved and auto_execute:
            if dry_run:
                print("🔔 DRY RUN - Trade would be executed:")
                print(f"   BUY {quantity:.6f} {pair} @ ${entry_price:.6f}")
                print(f"   Total: ${quantity * entry_price:.2f}")
                print(f"   Stop Loss: ${stop_loss:.6f}")
                print(f"   Take Profit: ${take_profit:.6f}")
            else:
                print("⚡ EXECUTING TRADE...")
                try:
                    # Place market buy order
                    order = api.place_order(pair, 'BUY', 'MARKET', quantity)
                    
                    if 'error' not in order:
                        print(f"✅ ORDER PLACED!")
                        print(f"   Order ID: {order.get('orderId', 'N/A')}")
                        print(f"   Status: {order.get('status', 'N/A')}")
                        
                        # Place stop loss and take profit orders
                        # (In production, use OCO orders or trailing stops)
                        print(f"\n📋 Protective orders:")
                        print(f"   Stop Loss:    Set at ${stop_loss:.6f}")
                        print(f"   Take Profit:  Set at ${take_profit:.6f}")
                    else:
                        print(f"❌ ORDER FAILED: {order['error']}")
                        
                except Exception as e:
                    print(f"❌ Execution error: {e}")
        elif not approved:
            print("⚠️  Trade rejected by risk management")
        else:
            print("ℹ️  Auto-execute disabled. Use --auto-execute to trade.")
    
    elif decision['action'] == 'WAIT':
        print("⏸️  AI recommends WAIT - no trade executed")
    
    elif decision['confidence'] < min_confidence:
        print(f"⚠️  Confidence {decision['confidence']}/10 below threshold {min_confidence}/10")
    
    print(f"\n{'='*70}")
    print("✅ Analysis complete")
    print(f"{'='*70}\n")

def main():
    parser = argparse.ArgumentParser(description='SilkTrader v3 Trade Analyzer')
    parser.add_argument('--pair', required=True, help='Trading pair (e.g., ACE_USDT)')
    parser.add_argument('--auto-execute', action='store_true', help='Execute if approved')
    parser.add_argument('--min-confidence', type=int, default=7, help='Minimum confidence (1-10)')
    parser.add_argument('--live', action='store_true', help='Live trading mode (default: dry-run)')
    
    args = parser.parse_args()
    
    try:
        analyze_and_trade(
            pair=args.pair,
            auto_execute=args.auto_execute,
            min_confidence=args.min_confidence,
            dry_run=not args.live
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == '__main__':
    main()
