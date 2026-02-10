#!/usr/bin/env python3
"""
ExchangeManager: High-level trading interface for SilkTrader v3
Combines PionexAPI + RiskManager for validated order execution
"""
import sys
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add skills path for RiskManager import
sys.path.append('skills/silktrader-trader/scripts')

from lib.pionex_api import PionexAPI
from risk_manager import RiskManager


class ExchangeManager:
    """High-level trading interface with comprehensive validation and risk management"""
    
    def __init__(self, api: PionexAPI, risk_manager: RiskManager, dry_run: bool = False, db=None):
        """Initialize ExchangeManager
        
        Args:
            api: Initialized PionexAPI client
            risk_manager: Initialized RiskManager
            dry_run: If True, simulate trades without placing real orders (paper trading)
            db: Optional TradingDatabase instance for logging
        """
        self.api = api
        self.risk_manager = risk_manager
        self.dry_run = dry_run
        self.db = db
        
        # Setup logging
        self.logger = logging.getLogger('ExchangeManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Track today's trades for daily limits (in production, persist to DB)
        self._trades_today = 0
        self._daily_pnl = 0.0
        
        mode = "PAPER TRADING" if dry_run else "LIVE TRADING"
        self.logger.warning(f"ExchangeManager initialized in {mode} mode")
    
    def get_available_balance(self) -> float:
        """Get free USDT balance available for trading
        
        Returns:
            Free USDT balance, or 0.0 if error
        """
        try:
            free, frozen, total = self.api.get_balance_by_currency('USDT')
            self.logger.info(f"Available balance: ${free:.2f} USDT (${frozen:.2f} frozen)")
            return free
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    def is_pair_affordable(self, pair: str, entry_price: float, balance: float) -> bool:
        """Check if pair's minimum requirements are within account's 25% limit
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            entry_price: Expected entry price
            balance: Current account balance
            
        Returns:
            True if pair is affordable, False otherwise
        """
        try:
            # Get symbol info (uses cache automatically)
            info = self.api.get_symbol_info(pair)
            
            if 'error' in info:
                self.logger.warning(f"Could not fetch symbol info for {pair}: {info['error']}")
                return False
            
            if not info.get('enable', True):
                self.logger.warning(f"Pair {pair} is not enabled for trading")
                return False
            
            min_amount = info.get('minAmount', 0.0)
            min_trade_size = info.get('minTradeSize', 0.0)
            
            # Calculate minimum USDT required (min notional value)
            min_usdt_required = max(min_amount, min_trade_size * entry_price)
            
            # Check if minimum is within 25% account limit
            max_per_position = balance * 0.25
            
            if min_usdt_required > max_per_position:
                self.logger.warning(
                    f"{pair} requires ${min_usdt_required:.2f} minimum, "
                    f"but 25% limit is ${max_per_position:.2f}"
                )
                return False
            
            self.logger.debug(
                f"{pair} is affordable: min ${min_usdt_required:.4f}, "
                f"25% limit ${max_per_position:.2f}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking affordability for {pair}: {e}")
            return False
    
    def calculate_order(self, pair: str, entry_price: float, confidence: int) -> Dict:
        """Calculate position size and validate order parameters
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            entry_price: Planned entry price
            confidence: Setup quality score (0-100)
            
        Returns:
            Dict with order details or error:
            {
                'approved': bool,
                'pair': str,
                'entry_price': float,
                'position_usdt': float,
                'quantity': float,
                'min_amount': float,
                'min_trade_size': float,
                'message': str,
                'error': str (if rejected)
            }
        """
        result = {
            'approved': False,
            'pair': pair,
            'entry_price': entry_price,
            'confidence': confidence
        }
        
        try:
            # Step 1: Get available balance
            balance = self.get_available_balance()
            if balance <= 0:
                result['error'] = "No available balance"
                return result
            
            # Step 2: Get symbol info (cached automatically)
            info = self.api.get_symbol_info(pair)
            
            if 'error' in info:
                result['error'] = f"Symbol info error: {info['error']}"
                return result
            
            if not info.get('enable', True):
                result['error'] = f"Pair {pair} is disabled for trading"
                return result
            
            min_amount = info.get('minAmount', 0.0)
            min_trade_size = info.get('minTradeSize', 0.0)
            result['min_amount'] = min_amount
            result['min_trade_size'] = min_trade_size
            
            # Step 3: Calculate position size via RiskManager
            try:
                position_usdt, quantity, size_msg = self.risk_manager.calculate_position_size_tiered(
                    account_balance=balance,
                    entry_price=entry_price,
                    confidence_score=float(confidence),
                    pair=pair
                )
            except ValueError as e:
                result['error'] = f"Position sizing error: {e}"
                return result
            
            result['position_usdt'] = position_usdt
            result['quantity'] = quantity
            
            # Step 4: Validate against exchange minimums
            min_notional = max(min_amount, min_trade_size * entry_price)
            
            if position_usdt < min_notional:
                result['error'] = (
                    f"Position ${position_usdt:.2f} below exchange minimum ${min_notional:.4f} "
                    f"(minAmount: ${min_amount}, minTradeSize: {min_trade_size})"
                )
                return result
            
            # Step 5: Validate through RiskManager
            current_positions = len(self.get_open_positions())
            
            approved, validation_msg = self.risk_manager.validate_trade(
                pair=pair,
                side='BUY',
                quantity=quantity,
                position_usdt=position_usdt,
                current_positions=current_positions,
                daily_pnl=self._daily_pnl,
                trades_today=self._trades_today,
                account_balance=balance
            )
            
            result['approved'] = approved
            result['message'] = f"{size_msg} | {validation_msg}"
            
            if not approved:
                result['error'] = validation_msg
            
            self.logger.info(
                f"Order calculation for {pair}: "
                f"${position_usdt:.2f} ({quantity:.8f}) @ ${entry_price:.2f} - "
                f"{'APPROVED' if approved else 'REJECTED'}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating order for {pair}: {e}", exc_info=True)
            result['error'] = f"Unexpected error: {e}"
            return result
    
    def execute_trade(self, pair: str, side: str, entry_price: float, 
                     confidence: int, order_type: str = 'LIMIT', 
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None) -> Dict:
        """Calculate, validate, and execute a trade
        
        NOTE: Stop-loss orders are NOT placed by this method. They should be
        managed by the position monitor after entry is confirmed.
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            side: 'BUY' or 'SELL'
            entry_price: Entry price for limit orders
            confidence: Setup quality score (0-100)
            order_type: 'LIMIT' or 'MARKET' (default: LIMIT)
            stop_loss: Optional stop loss price (for reference only, not placed)
            take_profit: Optional take profit price (for reference only, not placed)
            
        Returns:
            Dict with execution result:
            {
                'success': bool,
                'order_id': str (if successful),
                'pair': str,
                'side': str,
                'entry_price': float,
                'quantity': float,
                'position_usdt': float,
                'stop_loss': float (optional),
                'take_profit': float (optional),
                'dry_run': bool,
                'message': str,
                'error': str (if failed)
            }
        """
        result = {
            'success': False,
            'pair': pair,
            'side': side.upper(),
            'entry_price': entry_price,
            'order_type': order_type.upper(),
            'dry_run': self.dry_run
        }
        
        try:
            # Step 1: Calculate and validate order
            calculation = self.calculate_order(pair, entry_price, confidence)
            
            if not calculation.get('approved', False):
                result['error'] = calculation.get('error', 'Order rejected')
                result['message'] = calculation.get('message', '')
                self.logger.warning(f"Trade rejected for {pair}: {result['error']}")
                return result
            
            quantity = calculation['quantity']
            position_usdt = calculation['position_usdt']
            
            result['quantity'] = quantity
            result['position_usdt'] = position_usdt
            result['stop_loss'] = stop_loss
            result['take_profit'] = take_profit
            
            # Step 2: Execute order (or simulate if dry_run)
            if self.dry_run:
                # Paper trading simulation
                result['success'] = True
                result['order_id'] = f"PAPER-{pair}-{int(time.time())}"
                result['message'] = (
                    f"[PAPER TRADE] {side} {quantity:.8f} {pair} @ ${entry_price:.2f} "
                    f"(${position_usdt:.2f}) - NOT EXECUTED ON EXCHANGE"
                )
                self.logger.warning(result['message'])
                
            else:
                # Live trading
                order_result = self.api.place_order(
                    symbol=pair,
                    side=side.upper(),
                    order_type=order_type.upper(),
                    quantity=quantity,
                    price=entry_price if order_type.upper() == 'LIMIT' else None
                )
                
                if 'data' in order_result and 'orderId' in order_result['data']:
                    result['success'] = True
                    result['order_id'] = order_result['data']['orderId']
                    result['message'] = (
                        f"Order placed: {side} {quantity:.8f} {pair} @ ${entry_price:.2f} "
                        f"(${position_usdt:.2f}) - Order ID: {result['order_id']}"
                    )
                    self.logger.info(result['message'])
                    
                    # Increment trade counter
                    self._trades_today += 1
                    
                else:
                    result['error'] = order_result.get('error', 'Unknown order error')
                    result['message'] = f"Order failed: {result['error']}"
                    self.logger.error(result['message'])
            
            # Step 3: Log trade to database
            if result['success'] and self.db:
                try:
                    trade_data = {
                        'trade_id': result['order_id'],
                        'pair': pair,
                        'side': side.upper(),
                        'order_type': order_type.upper(),
                        'entry_price': entry_price,
                        'quantity': quantity,
                        'position_usdt': position_usdt,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'confidence_score': confidence,
                        'paper_trading': self.dry_run,
                        'status': 'OPEN',
                        'entry_time': datetime.now().isoformat()
                    }
                    self.db.insert_trade(trade_data)
                    self.logger.info(f"Trade logged to database: {result['order_id']}")
                except Exception as e:
                    self.logger.warning(f"Database trade logging failed: {e}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing trade for {pair}: {e}", exc_info=True)
            result['error'] = f"Execution error: {e}"
            result['message'] = result['error']
            return result
    
    def close_position(self, trade_id: str, pair: str, exit_price: float, 
                      entry_price: float, quantity: float, reason: str = "Manual close") -> Dict:
        """Close a position and update database
        
        Args:
            trade_id: Trade/order ID
            pair: Trading pair
            exit_price: Current exit price
            entry_price: Original entry price
            quantity: Position quantity
            reason: Reason for closing (e.g., 'Stop loss hit', 'Take profit')
            
        Returns:
            Dict with close result
        """
        result = {
            'success': False,
            'trade_id': trade_id,
            'pair': pair
        }
        
        try:
            # Calculate P&L
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            
            result['exit_price'] = exit_price
            result['pnl'] = pnl
            result['pnl_percent'] = pnl_percent
            result['reason'] = reason
            
            # Update database if available
            if self.db:
                try:
                    exit_data = {
                        'exit_price': exit_price,
                        'exit_time': datetime.now().isoformat(),
                        'entry_time': datetime.now().isoformat(),  # Will be updated by DB
                        'realized_pnl': pnl,
                        'pnl_percent': pnl_percent,
                        'status': 'CLOSED'
                    }
                    self.db.update_trade_exit(trade_id, exit_data)
                    self.logger.info(f"Trade exit logged to database: {trade_id}")
                except Exception as e:
                    self.logger.warning(f"Database exit logging failed: {e}")
            
            # Update daily P&L
            self.update_daily_pnl(pnl)
            
            result['success'] = True
            result['message'] = f"Position closed: {reason} - ${pnl:+.2f} ({pnl_percent:+.2f}%)"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position {trade_id}: {e}")
            result['error'] = str(e)
            return result
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions (wrapper for API get_open_orders)
        
        Returns:
            List of open orders/positions
        """
        try:
            orders = self.api.get_open_orders()
            self.logger.debug(f"Retrieved {len(orders)} open positions")
            return orders
        except Exception as e:
            self.logger.error(f"Failed to get open positions: {e}")
            return []
    
    def check_max_positions(self) -> bool:
        """Check if max open positions limit is reached
        
        Returns:
            True if more positions can be opened, False if at limit
        """
        current_positions = len(self.get_open_positions())
        max_positions = self.risk_manager.limits['max_open_positions']
        
        if current_positions >= max_positions:
            self.logger.warning(
                f"Max positions reached: {current_positions}/{max_positions}"
            )
            return False
        
        return True
    
    def get_position_summary(self) -> Dict:
        """Get summary of current positions and account status
        
        Returns:
            Dict with account summary:
            {
                'available_balance': float,
                'open_positions': int,
                'max_positions': int,
                'trades_today': int,
                'max_daily_trades': int,
                'daily_pnl': float,
                'can_trade': bool,
                'limit_message': str
            }
        """
        balance = self.get_available_balance()
        open_positions = len(self.get_open_positions())
        max_positions = self.risk_manager.limits['max_open_positions']
        max_daily_trades = self.risk_manager.limits['max_daily_trades']
        
        can_trade, limit_msg = self.risk_manager.check_daily_limits(
            self._trades_today, 
            self._daily_pnl
        )
        
        summary = {
            'available_balance': balance,
            'open_positions': open_positions,
            'max_positions': max_positions,
            'trades_today': self._trades_today,
            'max_daily_trades': max_daily_trades,
            'daily_pnl': self._daily_pnl,
            'can_trade': can_trade,
            'limit_message': limit_msg
        }
        
        self.logger.info(
            f"Position Summary: ${balance:.2f} balance, "
            f"{open_positions}/{max_positions} positions, "
            f"{self._trades_today} trades today, ${self._daily_pnl:.2f} P&L"
        )
        
        return summary
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L (called by position monitor when positions close)
        
        Args:
            pnl: Profit/loss amount to add to daily total
        """
        self._daily_pnl += pnl
        self.logger.info(f"Daily P&L updated: ${self._daily_pnl:.2f} ({'+' if pnl >= 0 else ''}{pnl:.2f})")
    
    def reset_daily_counters(self):
        """Reset daily trade counters (should be called at start of each trading day)"""
        self._trades_today = 0
        self._daily_pnl = 0.0
        self.logger.info("Daily counters reset")


if __name__ == '__main__':
    """Test ExchangeManager functionality"""
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize components
    try:
        api = PionexAPI('credentials/pionex.json')
        risk_manager = RiskManager('credentials/pionex.json')
        
        # IMPORTANT: Start in paper trading mode
        exchange_manager = ExchangeManager(api, risk_manager, dry_run=True)
        
        print("\n" + "="*80)
        print("SilkTrader v3 - ExchangeManager Test Suite")
        print("="*80)
        
        # Test 1: Get balance
        print("\n[TEST 1] Get Available Balance")
        print("-" * 80)
        balance = exchange_manager.get_available_balance()
        print(f"✓ Available balance: ${balance:.2f} USDT")
        
        # Test 2: Check pair affordability
        print("\n[TEST 2] Check Pair Affordability")
        print("-" * 80)
        test_pairs = [
            ('BTC_USDT', 70000.0),
            ('ETH_USDT', 3500.0),
            ('DOGE_USDT', 0.15)
        ]
        
        for pair, price in test_pairs:
            affordable = exchange_manager.is_pair_affordable(pair, price, balance)
            status = "✓ AFFORDABLE" if affordable else "✗ TOO EXPENSIVE"
            print(f"{status}: {pair} @ ${price:.2f}")
        
        # Test 3: Calculate order for BTC
        print("\n[TEST 3] Calculate Order - BTC_USDT @ $70,000 (75% confidence)")
        print("-" * 80)
        calculation = exchange_manager.calculate_order('BTC_USDT', 70000.0, 75)
        
        if calculation['approved']:
            print(f"✓ ORDER APPROVED")
            print(f"  Position: ${calculation['position_usdt']:.2f}")
            print(f"  Quantity: {calculation['quantity']:.8f} BTC")
            print(f"  Entry: ${calculation['entry_price']:.2f}")
            print(f"  Message: {calculation['message']}")
        else:
            print(f"✗ ORDER REJECTED: {calculation.get('error', 'Unknown reason')}")
        
        # Test 4: Position summary
        print("\n[TEST 4] Position Summary")
        print("-" * 80)
        summary = exchange_manager.get_position_summary()
        print(f"Balance: ${summary['available_balance']:.2f}")
        print(f"Open Positions: {summary['open_positions']}/{summary['max_positions']}")
        print(f"Daily Trades: {summary['trades_today']}/{summary['max_daily_trades']}")
        print(f"Daily P&L: ${summary['daily_pnl']:.2f}")
        print(f"Can Trade: {summary['can_trade']} - {summary['limit_message']}")
        
        # Test 5: Execute paper trade
        print("\n[TEST 5] Execute Paper Trade - ETH_USDT @ $3,500 (80% confidence)")
        print("-" * 80)
        result = exchange_manager.execute_trade(
            pair='ETH_USDT',
            side='BUY',
            entry_price=3500.0,
            confidence=80,
            order_type='LIMIT',
            stop_loss=3400.0,
            take_profit=3700.0
        )
        
        if result['success']:
            print(f"✓ TRADE EXECUTED")
            print(f"  Order ID: {result['order_id']}")
            print(f"  {result['side']} {result['quantity']:.8f} {result['pair']}")
            print(f"  Position: ${result['position_usdt']:.2f}")
            print(f"  Entry: ${result['entry_price']:.2f}")
            print(f"  Stop Loss: ${result.get('stop_loss', 'N/A')}")
            print(f"  Take Profit: ${result.get('take_profit', 'N/A')}")
            print(f"  {'[PAPER TRADE]' if result['dry_run'] else '[LIVE]'}")
        else:
            print(f"✗ TRADE FAILED: {result.get('error', 'Unknown error')}")
        
        print("\n" + "="*80)
        print("Test Suite Complete")
        print("="*80)
        print("\nNote: All trades executed in PAPER TRADING mode (dry_run=True)")
        print("To enable live trading, set dry_run=False when initializing ExchangeManager")
        
    except FileNotFoundError:
        print("ERROR: credentials/pionex.json not found!")
        print("Please create it from credentials/pionex.json.example")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
