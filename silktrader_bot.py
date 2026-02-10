#!/usr/bin/env python3
"""
SilkTrader v3 - Autonomous Trading Bot
Continuously scans markets and executes approved trades
"""
import sys
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add project paths
sys.path.insert(0, '.')
sys.path.append('lib')
sys.path.append('skills/silktrader-scanner/scripts')
sys.path.append('skills/silktrader-trader/scripts')

from lib.pionex_api import PionexAPI
from lib.exchange_manager import ExchangeManager
from lib.llm_decision import LLMDecisionEngine
from scanner import MarketScanner
from risk_manager import RiskManager


class SilkTraderBot:
    """Autonomous trading bot with AI-powered decision making"""
    
    def __init__(self, config_path: str = 'credentials/pionex.json', dry_run: bool = True):
        """Initialize bot components
        
        Args:
            config_path: Path to configuration file
            dry_run: If True, simulates trades without executing
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.dry_run = dry_run
        
        # Initialize core components
        self.api = PionexAPI(config_path)
        self.risk_mgr = RiskManager(config_path)
        self.exchange = ExchangeManager(self.api, self.risk_mgr, dry_run=dry_run)
        self.scanner = MarketScanner(self.api, self.exchange)
        
        # Initialize LLM decision engine
        try:
            self.llm = LLMDecisionEngine()
            # Check if API key is configured
            if not self.llm.api_key:
                print("⚠️  Warning: No OpenRouter API key found")
                print("   Set OPENROUTER_API_KEY environment variable to enable LLM mode")
                print("   Continuing in SCANNER-ONLY mode (score-based decisions)\n")
                self.llm_enabled = False
            else:
                self.llm_enabled = True
        except Exception as e:
            print(f"⚠️  Warning: LLM engine failed to initialize: {e}")
            print("   Continuing in SCANNER-ONLY mode (score-based decisions)\n")
            self.llm_enabled = False
        
        # Track consecutive LLM errors
        self.llm_error_count = 0
        self.llm_max_errors = 3  # Disable LLM after 3 consecutive errors
        
        # Setup logging
        self.log_file = 'logs/trading_log.txt'
        os.makedirs('logs', exist_ok=True)
        
        self.logger = logging.getLogger('SilkTraderBot')
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Session state
        self.session_start = datetime.now()
        self.last_scan_time = None
        
        # Print startup banner
        self._print_banner()
        self.logger.info(f"Bot started in {'DRY RUN' if dry_run else 'LIVE'} mode")
    
    def _print_banner(self):
        """Print startup banner"""
        summary = self.exchange.get_position_summary()
        
        print(f"\n{'='*70}")
        print(f"🤖 SilkTrader v3 - Autonomous Trading Bot")
        print(f"{'='*70}")
        print(f"Mode: {'🟢 PAPER TRADING' if self.dry_run else '🔴 LIVE TRADING'}")
        print(f"Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.llm_enabled:
            print(f"Decision Engine: ✅ LLM-Powered (OpenRouter)")
        else:
            print(f"Decision Engine: 📊 Scanner-Only Mode (Score-Based)")
        
        print(f"\n💰 Account Status:")
        print(f"   Balance: ${summary['available_balance']:.2f} USDT")
        print(f"   Open Positions: {summary['open_positions']}/{summary['max_positions']}")
        print(f"   Today: {summary['trades_today']}/{summary['max_daily_trades']} trades, ${summary['daily_pnl']:+.2f} P&L")
        print(f"   Can Trade: {'✅ YES' if summary['can_trade'] else '❌ NO - ' + summary['limit_message']}")
        print(f"\n🛡️ Risk Limits:")
        print(f"   Max Daily Loss: ${self.config['risk_limits']['max_daily_loss_usdt']:.2f}")
        print(f"   Max Position: ${self.config['risk_limits']['max_position_size_usdt']:.2f}")
        print(f"   Max Open: {self.config['risk_limits']['max_open_positions']} positions")
        print(f"{'='*70}\n")
    
    def scan_markets(self, min_score: int = None, top_n: int = None) -> List[Dict]:
        """Scan markets for opportunities
        
        Args:
            min_score: Minimum score threshold (uses config default if None)
            top_n: Number of top opportunities (uses config default if None)
            
        Returns:
            List of opportunity dicts from MarketScanner
        """
        scanner_config = self.config['scanner_config']
        
        if min_score is None:
            # Scanner uses 0-100 scale, config has 0-7 scale, convert
            min_score = int(scanner_config['min_score'] * (100 / 7))
        
        if top_n is None:
            top_n = scanner_config['top_pairs_limit']
        
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Scanning markets...")
        print(f"   Criteria: Min score {min_score}/100, Top {top_n} pairs\n")
        
        self.logger.info(f"Starting market scan (min_score={min_score}, top_n={top_n})")
        
        try:
            opportunities = self.scanner.scan_markets(
                top_n=top_n,
                min_score=min_score,
                check_affordability=True
            )
            
            self.logger.info(f"Scan complete: {len(opportunities)} opportunities found")
            return opportunities
            
        except Exception as e:
            print(f"❌ Scan error: {e}\n")
            self.logger.error(f"Scan error: {e}", exc_info=True)
            return []
    
    def evaluate_with_llm(self, opp: Dict) -> tuple[bool, Optional[Dict]]:
        """Evaluate opportunity with LLM decision engine or scanner scores
        
        Args:
            opp: Opportunity dict from scanner
            
        Returns:
            Tuple of (should_trade, decision_dict)
        """
        pair = opp['pair']
        indicators = opp['indicators']
        score = opp['score']
        
        print(f"📊 {pair} - Scanner Score: {score}/100")
        print(f"   Price: ${indicators['price']:.6f} | RSI: {indicators['rsi']:.1f} | Volume: {indicators['volume_ratio']:.2f}x")
        
        if not self.llm_enabled:
            # No LLM - use scanner score only
            # High confidence if score >= 80, medium if >= 70
            confidence = min(10, int(score / 10))
            decision = {
                'action': 'BUY' if score >= 70 else 'WAIT',
                'confidence': confidence,
                'reasoning': f"Scanner score {score}/100 - {opp['reasoning']}"
            }
            
            print(f"   📈 Score-Based Decision: {decision['action']} (confidence {confidence}/10)")
            
            # Truncate reasoning if too long
            reasoning = decision['reasoning']
            if len(reasoning) > 80:
                reasoning = reasoning[:77] + "..."
            print(f"   💭 {reasoning}")
            
            should_trade = decision['action'] == 'BUY' and confidence >= 7
            return should_trade, decision
        
        # Use LLM for decision
        try:
            # Convert score to 0-7 scale for LLM (it expects old format)
            llm_score = int(score / (100 / 7))
            decision = self.llm.analyze_opportunity(pair, indicators, llm_score)
            
            # Check if LLM returned an error
            if decision['confidence'] == 0 or 'Error:' in decision['reasoning']:
                # LLM error - increment counter and possibly disable
                self.llm_error_count += 1
                print(f"   ⚠️  LLM Error ({self.llm_error_count}/{self.llm_max_errors}): {decision['reasoning'][:60]}...")
                
                if self.llm_error_count >= self.llm_max_errors:
                    print(f"   ⚠️  LLM disabled after {self.llm_max_errors} errors, switching to SCANNER-ONLY mode\n")
                    self.llm_enabled = False
                    self.logger.warning(f"LLM disabled after {self.llm_max_errors} consecutive errors")
                    # Retry with scanner-only mode
                    return self.evaluate_with_llm(opp)
                
                # Use scanner score as fallback
                confidence = min(10, int(score / 10))
                decision = {
                    'action': 'BUY' if score >= 70 else 'WAIT',
                    'confidence': confidence,
                    'reasoning': f"Fallback to scanner score {score}/100"
                }
                print(f"   📈 Fallback Decision: {decision['action']} (confidence {confidence}/10)")
                should_trade = decision['action'] == 'BUY' and confidence >= 7
                return should_trade, decision
            
            # LLM success - reset error counter
            self.llm_error_count = 0
            
            print(f"   🧠 AI Decision: {decision['action']} (confidence {decision['confidence']}/10)")
            
            # Truncate reasoning if too long
            reasoning = decision['reasoning']
            if len(reasoning) > 80:
                reasoning = reasoning[:77] + "..."
            print(f"   💭 {reasoning}")
            
            self.logger.info(f"{pair}: {decision['action']} {decision['confidence']}/10 - {decision['reasoning']}")
            
            # Should trade if BUY with high confidence
            should_trade = decision['action'] == 'BUY' and decision['confidence'] >= 7
            return should_trade, decision
            
        except Exception as e:
            # LLM exception - increment counter
            self.llm_error_count += 1
            print(f"   ❌ LLM Exception ({self.llm_error_count}/{self.llm_max_errors}): {e}")
            self.logger.error(f"LLM error for {pair}: {e}", exc_info=True)
            
            if self.llm_error_count >= self.llm_max_errors:
                print(f"   ⚠️  LLM disabled after {self.llm_max_errors} errors, switching to SCANNER-ONLY mode\n")
                self.llm_enabled = False
                self.logger.warning(f"LLM disabled after {self.llm_max_errors} consecutive errors")
                # Retry with scanner-only mode
                return self.evaluate_with_llm(opp)
            
            return False, None
    
    def execute_trade(self, opp: Dict, decision: Dict) -> bool:
        """Execute approved trade via ExchangeManager
        
        Args:
            opp: Opportunity dict from scanner
            decision: Decision dict from LLM
            
        Returns:
            True if trade executed successfully
        """
        pair = opp['pair']
        entry_price = opp['entry_price']
        confidence = opp['score']  # Use scanner score for confidence
        
        print(f"   ⚡ Executing trade...")
        self.logger.info(f"Attempting trade: {pair} @ ${entry_price:.6f}")
        
        try:
            # Execute via ExchangeManager (handles all validation)
            result = self.exchange.execute_trade(
                pair=pair,
                side='BUY',
                entry_price=entry_price,
                confidence=confidence
            )
            
            if result['success']:
                print(f"   ✅ Trade Executed!")
                print(f"      Order: {result['order_id']}")
                print(f"      Position: ${result['position_usdt']:.2f} ({result['quantity']:.6f} {pair.split('_')[0]})")
                print(f"      Stop Loss: ${result['stop_loss']:.6f} | Take Profit: ${result['take_profit']:.6f}")
                
                self.logger.info(
                    f"Trade executed: {pair} {result['order_id']} - "
                    f"${result['position_usdt']:.2f} @ ${entry_price:.6f}"
                )
                
                return True
            else:
                print(f"   ❌ Trade Rejected: {result.get('error', 'Unknown error')}")
                self.logger.warning(f"Trade rejected for {pair}: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"   ❌ Execution Error: {e}")
            self.logger.error(f"Execution error for {pair}: {e}", exc_info=True)
            return False
    
    def run_cycle(self):
        """Run one complete trading cycle"""
        cycle_start = datetime.now()
        
        print(f"\n{'─'*70}")
        print(f"🔄 Starting Trading Cycle at {cycle_start.strftime('%H:%M:%S')}")
        print(f"{'─'*70}\n")
        
        self.logger.info("="*50)
        self.logger.info("Starting new trading cycle")
        
        # Check if we can trade
        summary = self.exchange.get_position_summary()
        
        if not summary['can_trade']:
            print(f"⏸️  Trading Paused: {summary['limit_message']}")
            print(f"   Positions: {summary['open_positions']}/{summary['max_positions']}")
            print(f"   Today: {summary['trades_today']}/{summary['max_daily_trades']} trades")
            print(f"   Daily P&L: ${summary['daily_pnl']:+.2f}\n")
            
            self.logger.info(f"Trading paused: {summary['limit_message']}")
            return
        
        # Scan markets for opportunities
        opportunities = self.scan_markets()
        
        if not opportunities:
            print("ℹ️  No opportunities found meeting criteria\n")
            self.logger.info("No opportunities found")
            
            # Still show current status
            summary = self.exchange.get_position_summary()
            print(f"💼 Current Status:")
            print(f"   Balance: ${summary['available_balance']:.2f}")
            print(f"   Positions: {summary['open_positions']}/{summary['max_positions']}")
            print(f"   Today: {summary['trades_today']}/{summary['max_daily_trades']} trades, ${summary['daily_pnl']:+.2f}\n")
            return
        
        # Evaluate and execute opportunities
        trades_executed = 0
        
        for opp in opportunities:
            # Check limits before each trade
            summary = self.exchange.get_position_summary()
            if not summary['can_trade']:
                print(f"\n⚠️  Daily limits reached mid-cycle\n")
                break
            
            # Evaluate with LLM or scanner scores
            should_trade, decision = self.evaluate_with_llm(opp)
            
            if should_trade and decision:
                success = self.execute_trade(opp, decision)
                if success:
                    trades_executed += 1
                    time.sleep(1)  # Brief pause between trades
            
            print()  # Blank line between opportunities
        
        # Cycle summary
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        summary = self.exchange.get_position_summary()
        
        print(f"{'─'*70}")
        print(f"✅ Cycle Complete in {cycle_duration:.1f}s")
        print(f"   Trades: {trades_executed} executed this cycle")
        print(f"   Today: {summary['trades_today']}/{summary['max_daily_trades']} trades, ${summary['daily_pnl']:+.2f} P&L")
        print(f"   Positions: {summary['open_positions']}/{summary['max_positions']} open")
        print(f"   Balance: ${summary['available_balance']:.2f}")
        print(f"{'─'*70}\n")
        
        self.logger.info(
            f"Cycle complete: {trades_executed} trades, "
            f"{summary['open_positions']} positions, ${summary['daily_pnl']:+.2f} P&L"
        )
        
        self.last_scan_time = datetime.now()
    
    def run_continuous(self, scan_interval_seconds: int = None):
        """Run bot in continuous mode
        
        Args:
            scan_interval_seconds: Time between scans (uses config default if None)
        """
        if scan_interval_seconds is None:
            scan_interval_seconds = self.config['scanner_config']['scan_interval_seconds']
        
        print(f"🚀 Starting Continuous Trading Mode")
        print(f"   Scan Interval: {scan_interval_seconds}s ({scan_interval_seconds/60:.0f} minutes)")
        print(f"   Press Ctrl+C to stop\n")
        
        self.logger.info(f"Starting continuous mode, interval: {scan_interval_seconds}s")
        
        try:
            while True:
                # Run trading cycle
                self.run_cycle()
                
                # Check if should continue
                summary = self.exchange.get_position_summary()
                
                if not summary['can_trade']:
                    if 'daily loss' in summary['limit_message'].lower() or \
                       'max daily trades' in summary['limit_message'].lower():
                        print(f"⚠️  Daily Limit Reached: {summary['limit_message']}")
                        print(f"   Bot will pause until tomorrow (midnight UTC)\n")
                        self.logger.info(f"Daily limit reached: {summary['limit_message']}")
                        break
                
                # Wait for next cycle
                next_scan = datetime.now() + timedelta(seconds=scan_interval_seconds)
                print(f"⏳ Next scan at {next_scan.strftime('%H:%M:%S')}")
                print(f"   Waiting {scan_interval_seconds}s...\n")
                
                time.sleep(scan_interval_seconds)
                
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Bot Stopped by User\n")
            self.logger.info("Bot stopped by user")
        
        # Print session summary
        self.print_summary()
    
    def print_summary(self):
        """Print trading session summary"""
        summary = self.exchange.get_position_summary()
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        print(f"{'='*70}")
        print(f"📊 SESSION SUMMARY")
        print(f"{'='*70}")
        print(f"Mode: {'🟢 PAPER TRADING' if self.dry_run else '🔴 LIVE TRADING'}")
        print(f"Duration: {session_duration / 3600:.1f} hours")
        print(f"Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n💼 Trading Statistics:")
        print(f"   Trades Today: {summary['trades_today']}/{summary['max_daily_trades']}")
        print(f"   Open Positions: {summary['open_positions']}/{summary['max_positions']}")
        print(f"   Daily P&L: ${summary['daily_pnl']:+.2f}")
        print(f"   Available Balance: ${summary['available_balance']:.2f}")
        print(f"\n📈 Performance:")
        
        if summary['trades_today'] > 0:
            avg_pnl = summary['daily_pnl'] / summary['trades_today']
            print(f"   Avg P&L per Trade: ${avg_pnl:+.2f}")
        else:
            print(f"   No trades executed this session")
        
        print(f"{'='*70}\n")
        
        self.logger.info(
            f"Session ended: {summary['trades_today']} trades, "
            f"{summary['open_positions']} positions, ${summary['daily_pnl']:+.2f} P&L"
        )


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='SilkTrader v3 - Autonomous Cryptocurrency Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single scan cycle (paper trading)
  python silktrader_bot.py --once
  
  # Continuous mode, 15 min intervals (paper trading)
  python silktrader_bot.py --interval 900
  
  # Live trading (REAL MONEY!)
  python silktrader_bot.py --live --interval 900

NOTE: Always test thoroughly in paper trading mode before going live!

LLM Mode:
  Set OPENROUTER_API_KEY environment variable to enable LLM-powered decisions.
  Without it, bot uses scanner scores only (score-based mode).
        """
    )
    
    parser.add_argument(
        '--live', 
        action='store_true',
        help='LIVE TRADING MODE - Executes real trades with real money! (default: paper trading)'
    )
    parser.add_argument(
        '--interval', 
        type=int, 
        default=900,
        help='Scan interval in seconds (default: 900 = 15 minutes)'
    )
    parser.add_argument(
        '--once', 
        action='store_true',
        help='Run single cycle and exit (useful for testing)'
    )
    parser.add_argument(
        '--config', 
        default='credentials/pionex.json',
        help='Path to configuration file (default: credentials/pionex.json)'
    )
    
    args = parser.parse_args()
    
    # Safety check for live mode
    if args.live:
        print("\n" + "="*70)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("="*70)
        print("This will execute REAL trades with REAL money!\n")
        print("Before proceeding, confirm you have:")
        print("  ✓ Tested thoroughly in paper trading mode (--once)")
        print("  ✓ Verified scanner finds good opportunities")
        print("  ✓ Set appropriate risk limits in config")
        print("  ✓ Funded account with money you can afford to lose")
        print("  ✓ Read and understood the risks")
        print("="*70)
        
        confirmation = input("\nType 'I ACCEPT THE RISK' to proceed: ")
        if confirmation != 'I ACCEPT THE RISK':
            print("\n❌ Live trading cancelled\n")
            return
        print()
    
    try:
        # Initialize bot
        bot = SilkTraderBot(config_path=args.config, dry_run=not args.live)
        
        if args.once:
            # Single cycle mode
            bot.run_cycle()
            bot.print_summary()
        else:
            # Continuous trading mode
            bot.run_continuous(scan_interval_seconds=args.interval)
            
    except FileNotFoundError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("   Make sure credentials/pionex.json exists!\n")
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        print()


if __name__ == '__main__':
    main()
