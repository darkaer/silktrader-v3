#!/usr/bin/env python3
"""
SilkTrader v3 - Autonomous Trading Bot
Continuously scans markets and executes approved trades
"""
import sys
import os
import time
import json
from datetime import datetime, timedelta

sys.path.append('lib')
sys.path.append('skills/silktrader-scanner/scripts')
sys.path.append('skills/silktrader-trader/scripts')

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup
from llm_decision import LLMDecisionEngine
from risk_manager import RiskManager

class SilkTraderBot:
    """Autonomous trading bot"""
    
    def __init__(self, config_path='credentials/pionex.json', dry_run=True):
        self.api = PionexAPI(config_path)
        self.llm = LLMDecisionEngine()
        self.risk_mgr = RiskManager(config_path)
        self.dry_run = dry_run
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Trading state
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.last_scan_time = None
        self.positions = self.load_positions()
        
        # Logs
        self.log_file = 'logs/trading_log.txt'
        os.makedirs('logs', exist_ok=True)
        
        print(f"\n{'='*70}")
        print(f"🤖 SilkTrader v3 - Autonomous Trading Bot")
        print(f"{'='*70}")
        print(f"Mode: {'DRY RUN' if dry_run else '🔴 LIVE TRADING'}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(self.risk_mgr.get_risk_summary())
        print(f"Open Positions: {len(self.positions)}")
        print(f"{'='*70}\n")
        
        self.log(f"Bot started in {'DRY RUN' if dry_run else 'LIVE'} mode")
    
    def log(self, message):
        """Log message to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
    
    def load_positions(self):
        """Load positions from file"""
        positions_file = 'data/positions.json'
        if not os.path.exists(positions_file):
            return []
        
        try:
            with open(positions_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_position(self, position):
        """Save new position to file for monitor"""
        positions_file = 'data/positions.json'
        
        # Load existing positions
        positions = []
        try:
            if os.path.exists(positions_file):
                with open(positions_file, 'r') as f:
                    positions = json.load(f)
        except:
            pass
        
        # Add new position with metadata
        position['opened_at'] = datetime.now().isoformat()
        position['id'] = f"{position['pair']}_{int(time.time())}"
        positions.append(position)
        
        # Save
        os.makedirs('data', exist_ok=True)
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        
        self.positions = positions
        self.log(f"Position saved: {position['pair']} - {position['quantity']:.4f} @ ${position['entry']:.6f}")
    
    def scan_and_analyze(self):
        """Scan market and analyze top opportunities"""
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Scanning market...")
        self.log("Starting market scan")
        
        scanner_config = self.config['scanner_config']
        symbols = self.api.get_symbols(quote='USDT')
        
        print(f"   Found {len(symbols)} USDT pairs, analyzing...")
        
        # Scan all pairs
        opportunities = []
        errors = 0
        
        for symbol in symbols:
            try:
                klines = self.api.get_klines(symbol, scanner_config['timeframe'], 100)
                
                if len(klines) < 50:
                    continue
                
                indicators = calc_all_indicators(klines)
                score = score_setup(indicators)
                
                if score >= scanner_config['min_score']:
                    opportunities.append({
                        'pair': symbol,
                        'score': score,
                        'indicators': indicators
                    })
                
                time.sleep(0.05)  # Rate limiting
                
            except Exception as e:
                errors += 1
                if errors <= 3:  # Only log first few errors
                    self.log(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        top_opps = opportunities[:scanner_config['top_pairs_limit']]
        
        print(f"✓ Found {len(opportunities)} opportunities, analyzing top {len(top_opps)}...")
        self.log(f"Scan complete: {len(opportunities)} opportunities, top {len(top_opps)} selected")
        print()
        
        return top_opps
    
    def evaluate_opportunity(self, opp):
        """Evaluate if opportunity should be traded"""
        pair = opp['pair']
        indicators = opp['indicators']
        score = opp['score']
        
        # Get LLM decision
        try:
            decision = self.llm.analyze_opportunity(pair, indicators, score)
        except Exception as e:
            print(f"📊 {pair} (Score: {score}/7)")
            print(f"   ❌ LLM Error: {e}\n")
            self.log(f"LLM error for {pair}: {e}")
            return False, None
        
        # Display analysis
        print(f"📊 {pair} (Score: {score}/7)")
        print(f"   Price: ${indicators['price']:.6f} | RSI: {indicators['rsi']:.1f}")
        print(f"   🧠 AI: {decision['action']} ({decision['confidence']}/10)")
        
        # Truncate reasoning if too long
        reasoning = decision['reasoning']
        if len(reasoning) > 60:
            reasoning = reasoning[:60] + "..."
        print(f"   💭 {reasoning}")
        
        self.log(f"{pair}: {decision['action']} {decision['confidence']}/10 - {decision['reasoning']}")
        
        # Check if should execute
        if decision['action'] == 'BUY' and decision['confidence'] >= 7:
            return True, decision
        
        return False, decision
    
    def execute_trade(self, pair, indicators, decision):
        """Execute approved trade"""
        
        # Check daily limits
        can_trade, limit_msg = self.risk_mgr.check_daily_limits(
            self.trades_today, 
            self.daily_pnl
        )
        
        if not can_trade:
            print(f"   ⚠️ {limit_msg}\n")
            self.log(f"Trade blocked for {pair}: {limit_msg}")
            return False
        
        # Calculate entry, stops, position size
        entry_price = indicators['price']
        atr = indicators['atr']
        stop_loss = self.risk_mgr.calculate_stop_loss(entry_price, atr, 'BUY')
        take_profit = self.risk_mgr.calculate_take_profit(entry_price, atr, 'BUY')
        
        # Get account balance (mock for dry run, real API call for live)
        if self.dry_run:
            account_balance = 1000.0  # Mock $1000 account
        else:
            try:
                balances = self.api.get_account_balance()
                usdt_balance = next((b for b in balances if b['coin'] == 'USDT'), None)
                account_balance = float(usdt_balance['free']) if usdt_balance else 1000.0
            except:
                account_balance = 1000.0
        
        quantity, pos_msg = self.risk_mgr.calculate_position_size(
            pair, entry_price, stop_loss, account_balance
        )
        
        position_usdt = quantity * entry_price
        
        # Validate trade
        approved, val_msg = self.risk_mgr.validate_trade(
            pair, 'BUY', position_usdt, len(self.positions), self.daily_pnl
        )
        
        if not approved:
            print(f"   ❌ Rejected: {val_msg}\n")
            self.log(f"Trade rejected for {pair}: {val_msg}")
            return False
        
        # Execute
        if self.dry_run:
            print(f"   🔔 DRY RUN: Would BUY {quantity:.4f} {pair} @ ${entry_price:.6f}")
            print(f"      SL: ${stop_loss:.6f} | TP: ${take_profit:.6f}")
            
            # Save position for monitor
            position = {
                'pair': pair,
                'entry': entry_price,
                'quantity': quantity,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': decision['confidence'],
                'reasoning': decision['reasoning']
            }
            self.save_position(position)
            
        else:
            print(f"   ⚡ EXECUTING: BUY {quantity:.4f} {pair}...")
            self.log(f"Executing BUY order: {quantity:.4f} {pair} @ ${entry_price:.6f}")
            
            try:
                order = self.api.place_order(pair, 'BUY', 'MARKET', quantity)
                
                if 'error' not in order:
                    print(f"   ✅ ORDER FILLED!")
                    print(f"      Order ID: {order.get('orderId', 'N/A')}")
                    print(f"      SL: ${stop_loss:.6f} | TP: ${take_profit:.6f}")
                    
                    self.log(f"Order filled: {pair} Order ID {order.get('orderId', 'N/A')}")
                    
                    # Save position for monitor
                    position = {
                        'pair': pair,
                        'entry': entry_price,
                        'quantity': quantity,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'order_id': order.get('orderId'),
                        'confidence': decision['confidence'],
                        'reasoning': decision['reasoning']
                    }
                    self.save_position(position)
                    
                    # TODO: Place stop loss and take profit orders
                    # (Requires checking if Pionex supports OCO orders)
                    
                    self.trades_today += 1
                    
                else:
                    print(f"   ❌ ORDER FAILED: {order['error']}")
                    self.log(f"Order failed for {pair}: {order['error']}")
                    return False
                    
            except Exception as e:
                print(f"   ❌ Execution error: {e}")
                self.log(f"Execution error for {pair}: {e}")
                return False
        
        print()
        return True
    
    def run_cycle(self):
        """Run one complete scan and trade cycle"""
        cycle_start = datetime.now()
        
        print(f"\n{'─'*70}")
        print(f"🔄 Starting new cycle at {cycle_start.strftime('%H:%M:%S')}")
        print(f"{'─'*70}\n")
        
        self.log("="*50)
        self.log("Starting new trading cycle")
        
        # Scan market
        try:
            opportunities = self.scan_and_analyze()
        except Exception as e:
            print(f"❌ Scan error: {e}\n")
            self.log(f"Scan error: {e}")
            return
        
        if not opportunities:
            print("ℹ️  No opportunities found meeting criteria\n")
            self.log("No opportunities found")
            return
        
        # Evaluate each opportunity
        trades_executed = 0
        for opp in opportunities:
            should_trade, decision = self.evaluate_opportunity(opp)
            
            if should_trade:
                success = self.execute_trade(opp['pair'], opp['indicators'], decision)
                if success:
                    trades_executed += 1
                    time.sleep(1)  # Brief pause between trades
        
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        
        print(f"\n{'─'*70}")
        print(f"✅ Cycle complete in {cycle_duration:.1f}s: {trades_executed} trades executed")
        print(f"   Total today: {self.trades_today}/{self.config['risk_limits']['max_daily_trades']}")
        print(f"   Open positions: {len(self.positions)}")
        print(f"   Daily P&L: ${self.daily_pnl:+.2f}")
        print(f"{'─'*70}\n")
        
        self.log(f"Cycle complete: {trades_executed} trades, {len(self.positions)} open positions")
        self.last_scan_time = datetime.now()
    
    def run_continuous(self, scan_interval_seconds=None):
        """Run bot continuously"""
        
        if scan_interval_seconds is None:
            scan_interval_seconds = self.config['scanner_config']['scan_interval_seconds']
        
        print(f"🚀 Starting continuous trading (scan every {scan_interval_seconds}s)")
        print(f"   Press Ctrl+C to stop\n")
        
        self.log(f"Starting continuous mode, interval: {scan_interval_seconds}s")
        
        try:
            while True:
                self.run_cycle()
                
                # Check if should continue (daily limits)
                can_continue, msg = self.risk_mgr.check_daily_limits(
                    self.trades_today, 
                    self.daily_pnl
                )
                
                if not can_continue:
                    print(f"\n⚠️  {msg}")
                    print(f"   Bot paused for today. Restart tomorrow.\n")
                    self.log(f"Daily limit reached: {msg}")
                    break
                
                # Wait for next cycle
                next_scan = datetime.now() + timedelta(seconds=scan_interval_seconds)
                print(f"⏳ Waiting until {next_scan.strftime('%H:%M:%S')} for next scan...")
                time.sleep(scan_interval_seconds)
                
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Bot stopped by user")
            self.print_summary()
    
    def print_summary(self):
        """Print trading session summary"""
        print(f"\n{'='*70}")
        print(f"📊 SESSION SUMMARY")
        print(f"{'='*70}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        print(f"Started: {self.last_scan_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_scan_time else 'N/A'}")
        print(f"Duration: {(datetime.now() - self.last_scan_time).total_seconds() / 3600:.1f} hours" if self.last_scan_time else "N/A")
        print(f"\nTrading Statistics:")
        print(f"  Trades Executed: {self.trades_today}/{self.config['risk_limits']['max_daily_trades']}")
        print(f"  Open Positions: {len(self.positions)}")
        print(f"  Daily P&L: ${self.daily_pnl:+.2f}")
        
        if self.positions:
            print(f"\nOpen Positions:")
            for pos in self.positions:
                print(f"  • {pos['pair']}: {pos['quantity']:.4f} @ ${pos['entry']:.6f}")
        
        print(f"{'='*70}\n")
        
        self.log("="*50)
        self.log(f"Session ended: {self.trades_today} trades, {len(self.positions)} positions, ${self.daily_pnl:+.2f} P&L")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SilkTrader v3 Autonomous Bot')
    parser.add_argument('--live', action='store_true', 
                       help='Live trading mode (default: dry-run)')
    parser.add_argument('--interval', type=int, default=900, 
                       help='Scan interval in seconds (default: 900 = 15min)')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit')
    parser.add_argument('--config', default='credentials/pionex.json',
                       help='Path to config file')
    
    args = parser.parse_args()
    
    # Safety check for live mode
    if args.live:
        print("\n" + "="*70)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("="*70)
        print("This will execute REAL trades with REAL money!")
        print("Make sure you have:")
        print("  • Tested thoroughly in dry-run mode")
        print("  • Set appropriate risk limits")
        print("  • Funded your account with test capital only")
        print("="*70)
        
        confirmation = input("\nType 'CONFIRM' to proceed with live trading: ")
        if confirmation != 'CONFIRM':
            print("\n❌ Live trading cancelled\n")
            return
        print()
    
    try:
        # Initialize bot
        bot = SilkTraderBot(config_path=args.config, dry_run=not args.live)
        
        if args.once:
            # Run single cycle
            bot.run_cycle()
            bot.print_summary()
        else:
            # Run continuously
            bot.run_continuous(scan_interval_seconds=args.interval)
            
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
