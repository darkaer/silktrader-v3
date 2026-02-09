#!/usr/bin/env python3
import json
from typing import Dict, Tuple

class RiskManager:
    """Risk management and position sizing"""
    
    def __init__(self, config_path: str = 'credentials/pionex.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.limits = self.config['risk_limits']
    
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
        """
        
        # Risk per trade (2% of account)
        risk_amount = account_balance * 0.02
        
        # Price distance to stop loss
        price_risk = abs(entry_price - stop_loss_price)
        risk_percent = (price_risk / entry_price) * 100
        
        # Calculate max position size based on dollar risk
        # If we risk $20 and stop is 2.5% away, we can trade $800 worth
        max_position_usdt = risk_amount / (price_risk / entry_price)
        
        # Apply position size limit from config
        max_allowed = self.limits['max_position_size_usdt']
        position_usdt = min(max_position_usdt, max_allowed)
        
        # Calculate quantity in base currency
        quantity = position_usdt / entry_price
        
        # Extract base currency from pair (BTC from BTC_USDT)
        base_currency = pair.split('_')[0]
        
        # Format message
        msg = f"Position: ${position_usdt:.2f} ({quantity:.4f} {base_currency}), Risk: ${risk_amount:.2f} ({risk_percent:.2f}%)"
        
        return quantity, msg
    
    def validate_trade(self, pair: str, side: str, position_usdt: float, 
                      current_positions: int, daily_pnl: float) -> Tuple[bool, str]:
        """Validate if trade meets risk management rules
        
        Args:
            pair: Trading pair
            side: 'BUY' or 'SELL'
            position_usdt: Position size in USDT
            current_positions: Number of currently open positions
            daily_pnl: Today's profit/loss in USDT (negative = loss)
            
        Returns:
            (approved, message): Boolean approval and reason
        """
        
        # Check max position size (allow small rounding tolerance)
        if position_usdt > self.limits['max_position_size_usdt'] * 1.01:
            return False, f"Position ${position_usdt:.2f} exceeds max ${self.limits['max_position_size_usdt']}"
        
        # Check max open positions
        if current_positions >= self.limits['max_open_positions']:
            return False, f"Already at max {self.limits['max_open_positions']} positions"
        
        # Check daily loss limit
        if daily_pnl < -self.limits['max_daily_loss_usdt']:
            return False, f"Daily loss ${abs(daily_pnl):.2f} exceeds limit ${self.limits['max_daily_loss_usdt']}"
        
        # Check minimum position size (avoid dust trades)
        if position_usdt < 10:
            return False, f"Position ${position_usdt:.2f} below minimum $10"
        
        # All checks passed
        return True, "Trade approved"
    
    def calculate_stop_loss(self, entry_price: float, atr: float, side: str = 'BUY') -> float:
        """Calculate stop loss based on ATR (2x ATR from entry)
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            side: 'BUY' (long) or 'SELL' (short)
            
        Returns:
            Stop loss price
        """
        if side == 'BUY':
            # For longs, stop below entry
            return entry_price - (2 * atr)
        else:
            # For shorts, stop above entry
            return entry_price + (2 * atr)
    
    def calculate_take_profit(self, entry_price: float, atr: float, side: str = 'BUY') -> float:
        """Calculate take profit (3x ATR for 1.5:1 risk/reward)
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            side: 'BUY' (long) or 'SELL' (short)
            
        Returns:
            Take profit price
        """
        if side == 'BUY':
            # For longs, take profit above entry
            return entry_price + (3 * atr)
        else:
            # For shorts, take profit below entry
            return entry_price - (3 * atr)
    
    def calculate_trailing_stop(self, entry_price: float, current_price: float, 
                                atr: float, side: str = 'BUY') -> Tuple[bool, float]:
        """Calculate trailing stop for winning trades
        
        Args:
            entry_price: Original entry price
            current_price: Current market price
            atr: Average True Range
            side: 'BUY' or 'SELL'
            
        Returns:
            (should_activate, new_stop): Whether to activate trailing and new stop price
        """
        activation_pct = self.limits['trailing_stop_activation_percent'] / 100
        distance_pct = self.limits['trailing_stop_distance_percent'] / 100
        
        if side == 'BUY':
            # Check if profit reached activation threshold
            profit_pct = (current_price - entry_price) / entry_price
            
            if profit_pct >= activation_pct:
                # Set trailing stop below current price
                new_stop = current_price * (1 - distance_pct)
                return True, new_stop
        else:
            # For shorts
            profit_pct = (entry_price - current_price) / entry_price
            
            if profit_pct >= activation_pct:
                # Set trailing stop above current price
                new_stop = current_price * (1 + distance_pct)
                return True, new_stop
        
        return False, 0.0
    
    def get_risk_summary(self) -> str:
        """Get formatted risk limits summary"""
        return f"""
Risk Management Limits:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Max Position Size:      ${self.limits['max_position_size_usdt']}
• Max Open Positions:     {self.limits['max_open_positions']}
• Max Daily Loss:         ${self.limits['max_daily_loss_usdt']}
• Max Daily Trades:       {self.limits['max_daily_trades']}
• Stop Loss %:            {self.limits['stop_loss_percent']}%
• Take Profit %:          {self.limits['take_profit_percent']}%
• Trailing Activation:    {self.limits['trailing_stop_activation_percent']}%
• Trailing Distance:      {self.limits['trailing_stop_distance_percent']}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
    
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
