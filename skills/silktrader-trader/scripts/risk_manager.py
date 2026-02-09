#!/usr/bin/env python3
import json
import logging
from typing import Dict, Tuple, Optional

class RiskManager:
    """Risk management and position sizing with comprehensive safety checks"""
    
    def __init__(self, config_path: str = 'credentials/pionex.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.limits = self.config['risk_limits']
        
        # Initialize logger
        self.logger = logging.getLogger('RiskManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Track high water marks for trailing stops
        self.position_high_prices = {}
        
        # Load minimum order sizes (can be extended per exchange requirements)
        self.min_order_sizes = self.config.get('min_order_sizes', {
            'BTC_USDT': 0.0001,
            'ETH_USDT': 0.001,
            'BNB_USDT': 0.01,
            'SOL_USDT': 0.1,
            'XRP_USDT': 1.0,
            'ADA_USDT': 1.0,
            'DOGE_USDT': 10.0,
            'MATIC_USDT': 1.0,
            'DOT_USDT': 0.1,
            'AVAX_USDT': 0.1
        })
    
    def calculate_position_size(self, pair: str, entry_price: float, stop_loss_price: float, 
                               account_balance: float) -> Tuple[float, str]:
        """Calculate position size based on ATR and risk limits
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            account_balance: Total account balance in USDT
            
        Returns:
            (quantity, message): Quantity to trade and formatted message
        
        Raises:
            ValueError: If inputs are invalid
        """
        
        # Input validation
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_loss_price <= 0:
            raise ValueError(f"Stop loss price must be positive, got {stop_loss_price}")
        if account_balance <= 0:
            raise ValueError(f"Account balance must be positive, got {account_balance}")
        if entry_price == stop_loss_price:
            raise ValueError("Stop loss cannot equal entry price")
        
        # Get risk percentage from config
        risk_per_trade_pct = self.limits.get('risk_per_trade_percent', 2.0)
        
        # Risk per trade
        risk_amount = account_balance * (risk_per_trade_pct / 100)
        
        # Price distance to stop loss
        price_risk = abs(entry_price - stop_loss_price)
        risk_percent = (price_risk / entry_price) * 100
        
        # Calculate max position size based on dollar risk
        max_position_usdt = risk_amount / (price_risk / entry_price)
        
        # Apply position size limit from config
        max_allowed = self.limits['max_position_size_usdt']
        
        # Don't risk more than 5% of account on single position
        max_account_pct = account_balance * 0.05
        
        # Take minimum of all limits
        position_usdt = min(max_position_usdt, max_allowed, max_account_pct)
        
        # Calculate quantity in base currency
        quantity = position_usdt / entry_price
        
        # Extract base currency from pair (BTC from BTC_USDT)
        base_currency = pair.split('_')[0]
        
        # Check minimum order size for this pair
        min_qty = self.min_order_sizes.get(pair, 0)
        if quantity < min_qty:
            self.logger.warning(f"Calculated quantity {quantity:.6f} {base_currency} below minimum {min_qty} for {pair}")
        
        # Format message
        msg = f"Position: ${position_usdt:.2f} ({quantity:.6f} {base_currency}), Risk: ${risk_amount:.2f} ({risk_percent:.2f}%)"
        
        self.logger.info(f"Position size calculated for {pair}: {msg}")
        return quantity, msg
    
    def validate_trade(self, pair: str, side: str, quantity: float, position_usdt: float, 
                      current_positions: int, daily_pnl: float, trades_today: int,
                      account_balance: float) -> Tuple[bool, str]:
        """Validate if trade meets risk management rules
        
        Args:
            pair: Trading pair
            side: 'BUY' or 'SELL'
            quantity: Quantity in base currency
            position_usdt: Position size in USDT
            current_positions: Number of currently open positions
            daily_pnl: Today's profit/loss in USDT (negative = loss)
            trades_today: Number of trades executed today
            account_balance: Total account balance in USDT
            
        Returns:
            (approved, message): Boolean approval and reason
        """
        
        self.logger.info(f"Validating {side} {pair}: ${position_usdt:.2f} ({quantity:.6f})")
        
        # Check daily limits FIRST (most important check)
        can_trade, daily_msg = self.check_daily_limits(trades_today, daily_pnl)
        if not can_trade:
            self.logger.warning(f"Trade rejected - Daily limits: {daily_msg}")
            return False, daily_msg
        
        # Check minimum position size
        min_position = self.limits.get('min_position_size_usdt', 10.0)
        if position_usdt < min_position:
            msg = f"Position ${position_usdt:.2f} below minimum ${min_position}"
            self.logger.warning(f"Trade rejected: {msg}")
            return False, msg
        
        # Check max position size (allow small rounding tolerance)
        if position_usdt > self.limits['max_position_size_usdt'] * 1.01:
            msg = f"Position ${position_usdt:.2f} exceeds max ${self.limits['max_position_size_usdt']}"
            self.logger.warning(f"Trade rejected: {msg}")
            return False, msg
        
        # Check account percentage limit (5% max per position)
        if position_usdt > account_balance * 0.05:
            msg = f"Position ${position_usdt:.2f} exceeds 5% of account ${account_balance:.2f}"
            self.logger.warning(f"Trade rejected: {msg}")
            return False, msg
        
        # Check max open positions
        if current_positions >= self.limits['max_open_positions']:
            msg = f"Already at max {self.limits['max_open_positions']} positions"
            self.logger.warning(f"Trade rejected: {msg}")
            return False, msg
        
        # Check minimum order size for this pair
        base_currency = pair.split('_')[0]
        min_qty = self.min_order_sizes.get(pair, 0)
        if min_qty > 0 and quantity < min_qty:
            msg = f"Quantity {quantity:.6f} {base_currency} below minimum {min_qty} for {pair}"
            self.logger.warning(f"Trade rejected: {msg}")
            return False, msg
        
        # All checks passed
        self.logger.info(f"Trade approved: {side} {pair} ${position_usdt:.2f}")
        return True, "Trade approved - all risk checks passed"
    
    def calculate_stop_loss(self, entry_price: float, atr: float, side: str = 'BUY') -> float:
        """Calculate stop loss based on ATR
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            side: 'BUY' (long) or 'SELL' (short)
            
        Returns:
            Stop loss price
            
        Raises:
            ValueError: If inputs are invalid
        """
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if atr <= 0:
            raise ValueError(f"ATR must be positive, got {atr}")
        
        # Get multiplier from config
        atr_multiplier = self.limits.get('atr_stop_multiplier', 2.0)
        
        if side == 'BUY':
            # For longs, stop below entry
            return entry_price - (atr_multiplier * atr)
        else:
            # For shorts, stop above entry
            return entry_price + (atr_multiplier * atr)
    
    def calculate_take_profit(self, entry_price: float, atr: float, side: str = 'BUY') -> float:
        """Calculate take profit based on ATR
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            side: 'BUY' (long) or 'SELL' (short)
            
        Returns:
            Take profit price
            
        Raises:
            ValueError: If inputs are invalid
        """
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if atr <= 0:
            raise ValueError(f"ATR must be positive, got {atr}")
        
        # Get multiplier from config
        atr_tp_multiplier = self.limits.get('atr_tp_multiplier', 3.0)
        
        if side == 'BUY':
            # For longs, take profit above entry
            return entry_price + (atr_tp_multiplier * atr)
        else:
            # For shorts, take profit below entry
            return entry_price - (atr_tp_multiplier * atr)
    
    def calculate_trailing_stop(self, position_id: str, entry_price: float, 
                                current_price: float, atr: float, 
                                side: str = 'BUY') -> Tuple[bool, float]:
        """Calculate trailing stop for winning trades with high water mark tracking
        
        Args:
            position_id: Unique position identifier for tracking high water mark
            entry_price: Original entry price
            current_price: Current market price
            atr: Average True Range
            side: 'BUY' or 'SELL'
            
        Returns:
            (should_activate, new_stop): Whether to activate trailing and new stop price
        """
        activation_pct = self.limits['trailing_stop_activation_percent'] / 100
        distance_pct = self.limits['trailing_stop_distance_percent'] / 100
        
        # Initialize or update high water mark
        if position_id not in self.position_high_prices:
            self.position_high_prices[position_id] = current_price
        
        if side == 'BUY':
            # Update high water mark if price is higher
            if current_price > self.position_high_prices[position_id]:
                self.position_high_prices[position_id] = current_price
            
            # Check if profit reached activation threshold
            profit_pct = (self.position_high_prices[position_id] - entry_price) / entry_price
            
            if profit_pct >= activation_pct:
                # Set trailing stop below high water mark (not current price)
                new_stop = self.position_high_prices[position_id] * (1 - distance_pct)
                self.logger.info(f"Trailing stop activated for {position_id}: ${new_stop:.2f} "
                               f"(HWM: ${self.position_high_prices[position_id]:.2f}, profit: {profit_pct*100:.2f}%)")
                return True, new_stop
        else:
            # For shorts - update low water mark
            if current_price < self.position_high_prices[position_id]:
                self.position_high_prices[position_id] = current_price
            
            profit_pct = (entry_price - self.position_high_prices[position_id]) / entry_price
            
            if profit_pct >= activation_pct:
                # Set trailing stop above low water mark
                new_stop = self.position_high_prices[position_id] * (1 + distance_pct)
                self.logger.info(f"Trailing stop activated for {position_id}: ${new_stop:.2f} "
                               f"(LWM: ${self.position_high_prices[position_id]:.2f}, profit: {profit_pct*100:.2f}%)")
                return True, new_stop
        
        return False, 0.0
    
    def clear_position_tracking(self, position_id: str):
        """Clear high water mark tracking when position closes"""
        if position_id in self.position_high_prices:
            del self.position_high_prices[position_id]
            self.logger.debug(f"Cleared tracking for position {position_id}")
    
    def check_daily_limits(self, trades_today: int, pnl_today: float) -> Tuple[bool, str]:
        """Check if daily trading limits have been reached
        
        Args:
            trades_today: Number of trades executed today
            pnl_today: Today's total P&L
            
        Returns:
            (can_trade, message): Whether trading is allowed and reason
        """
        
        # Check max trades per day
        if trades_today >= self.limits['max_daily_trades']:
            return False, f"Daily trade limit reached ({trades_today}/{self.limits['max_daily_trades']})"
        
        # Check daily loss limit
        if pnl_today < -self.limits['max_daily_loss_usdt']:
            return False, f"Daily loss limit hit (${abs(pnl_today):.2f}/${self.limits['max_daily_loss_usdt']})"
        
        return True, f"Daily limits OK ({trades_today}/{self.limits['max_daily_trades']} trades, ${pnl_today:.2f} P&L)"
    
    def get_risk_summary(self) -> str:
        """Get formatted risk limits summary"""
        risk_pct = self.limits.get('risk_per_trade_percent', 2.0)
        min_pos = self.limits.get('min_position_size_usdt', 10.0)
        atr_stop = self.limits.get('atr_stop_multiplier', 2.0)
        atr_tp = self.limits.get('atr_tp_multiplier', 3.0)
        
        return f"""
Risk Management Limits:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Risk Per Trade:         {risk_pct}%
• Min Position Size:      ${min_pos}
• Max Position Size:      ${self.limits['max_position_size_usdt']}
• Max Open Positions:     {self.limits['max_open_positions']}
• Max Daily Loss:         ${self.limits['max_daily_loss_usdt']}
• Max Daily Trades:       {self.limits['max_daily_trades']}
• ATR Stop Multiplier:    {atr_stop}x
• ATR TP Multiplier:      {atr_tp}x
• Trailing Activation:    {self.limits['trailing_stop_activation_percent']}%
• Trailing Distance:      {self.limits['trailing_stop_distance_percent']}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
