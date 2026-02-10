#!/usr/bin/env python3
"""
Telegram Notifier for SilkTrader v3
Sends trading notifications via Telegram bot
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict
import asyncio
from telegram import Bot
from telegram.error import TelegramError

class TelegramNotifier:
    """Send trading notifications via Telegram"""
    
    def __init__(self, config_path: str = 'credentials/pionex.json', enabled: bool = True):
        """Initialize Telegram notifier
        
        Args:
            config_path: Path to config file with Telegram credentials
            enabled: Whether notifications are enabled
        """
        self.enabled = enabled
        self.bot = None
        self.chat_id = None
        
        # Setup logging
        self.logger = logging.getLogger('TelegramNotifier')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        if not enabled:
            self.logger.info("Telegram notifications disabled")
            return
        
        # Load config
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            telegram_config = config.get('telegram', {})
            
            bot_token = telegram_config.get('bot_token')
            self.chat_id = telegram_config.get('chat_id')
            
            if not bot_token or not self.chat_id:
                self.logger.warning("Telegram credentials not configured. Notifications disabled.")
                self.enabled = False
                return
            
            self.bot = Bot(token=bot_token)
            self.logger.info("Telegram notifier initialized successfully")
            
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {config_path}. Notifications disabled.")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enabled = False
    
    def _send_message_sync(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """Send message synchronously (creates event loop if needed)
        
        Args:
            message: Message text
            parse_mode: 'Markdown' or 'HTML'
            
        Returns:
            Success status
        """
        if not self.enabled or not self.bot:
            return False
        
        try:
            # Try to get running event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                )
                loop.close()
            else:
                # Running loop exists, create task
                result = loop.create_task(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                )
            
            self.logger.debug(f"Telegram message sent successfully")
            return True
            
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram: {e}")
            return False
    
    def send_position_opened(self, pair: str, side: str, entry_price: float, 
                            quantity: float, position_usdt: float, 
                            stop_loss: float, take_profit: float) -> bool:
        """Notify when new position is opened
        
        Args:
            pair: Trading pair
            side: 'BUY' or 'SELL'
            entry_price: Entry price
            quantity: Position quantity
            position_usdt: Position size in USDT
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            Success status
        """
        icon = "🟢" if side == "BUY" else "🔴"
        
        message = f"""{icon} *NEW POSITION OPENED*

*Pair:* `{pair}`
*Side:* {side}
*Entry:* ${entry_price:.8f}
*Quantity:* {quantity:.6f}
*Size:* ${position_usdt:.2f}

*Stop Loss:* ${stop_loss:.8f}
*Take Profit:* ${take_profit:.8f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self._send_message_sync(message)
    
    def send_position_closed(self, pair: str, reason: str, entry_price: float, 
                            exit_price: float, quantity: float, pnl_usdt: float, 
                            pnl_pct: float, duration: Optional[str] = None) -> bool:
        """Notify when position is closed
        
        Args:
            pair: Trading pair
            reason: Close reason (STOP_LOSS, TAKE_PROFIT, MANUAL, etc.)
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity
            pnl_usdt: Profit/loss in USDT
            pnl_pct: Profit/loss percentage
            duration: Optional position duration
            
        Returns:
            Success status
        """
        # Determine icon and message based on P&L
        if pnl_usdt > 0:
            icon = "💰"
            status = "PROFIT"
        else:
            icon = "🔴"
            status = "LOSS"
        
        message = f"""{icon} *POSITION CLOSED - {status}*

*Pair:* `{pair}`
*Reason:* {reason}

*Entry:* ${entry_price:.8f}
*Exit:* ${exit_price:.8f}
*Quantity:* {quantity:.6f}

*P&L:* ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)
        """
        
        if duration:
            message += f"\n*Duration:* {duration}"
        
        message += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self._send_message_sync(message)
    
    def send_trailing_stop_activated(self, pair: str, current_price: float, 
                                    new_stop: float, profit_pct: float) -> bool:
        """Notify when trailing stop is activated
        
        Args:
            pair: Trading pair
            current_price: Current market price
            new_stop: New trailing stop price
            profit_pct: Current profit percentage
            
        Returns:
            Success status
        """
        message = f"""🎯 *TRAILING STOP ACTIVATED*

*Pair:* `{pair}`
*Current Price:* ${current_price:.8f}
*New Stop:* ${new_stop:.8f}
*Profit:* +{profit_pct:.2f}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self._send_message_sync(message)
    
    def send_trailing_stop_updated(self, pair: str, old_stop: float, 
                                   new_stop: float, profit_pct: float) -> bool:
        """Notify when trailing stop is moved up
        
        Args:
            pair: Trading pair
            old_stop: Previous stop price
            new_stop: New trailing stop price
            profit_pct: Current profit percentage
            
        Returns:
            Success status
        """
        message = f"""📈 *TRAILING STOP MOVED*

*Pair:* `{pair}`
*Old Stop:* ${old_stop:.8f}
*New Stop:* ${new_stop:.8f}
*Profit:* +{profit_pct:.2f}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self._send_message_sync(message)
    
    def send_daily_summary(self, trades_today: int, wins: int, losses: int, 
                          total_pnl: float, win_rate: float, 
                          open_positions: int) -> bool:
        """Send daily performance summary
        
        Args:
            trades_today: Number of trades closed today
            wins: Number of winning trades
            losses: Number of losing trades
            total_pnl: Total P&L for the day
            win_rate: Win rate percentage
            open_positions: Number of currently open positions
            
        Returns:
            Success status
        """
        pnl_icon = "💰" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
        
        message = f"""📊 *DAILY SUMMARY*

*Trades Closed:* {trades_today}
*Wins:* {wins} | *Losses:* {losses}
*Win Rate:* {win_rate:.1f}%

{pnl_icon} *Total P&L:* ${total_pnl:+.2f}

*Open Positions:* {open_positions}

📅 {datetime.now().strftime('%Y-%m-%d')}
        """
        
        return self._send_message_sync(message)
    
    def send_error(self, error_type: str, details: str) -> bool:
        """Send error notification
        
        Args:
            error_type: Type of error
            details: Error details
            
        Returns:
            Success status
        """
        message = f"""⚠️ *ERROR ALERT*

*Type:* {error_type}
*Details:* {details}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self._send_message_sync(message)
    
    def send_bot_started(self, mode: str = "PAPER TRADING") -> bool:
        """Notify when bot starts
        
        Args:
            mode: Trading mode (PAPER TRADING or LIVE TRADING)
            
        Returns:
            Success status
        """
        icon = "🔵" if mode == "PAPER TRADING" else "🔴"
        
        message = f"""{icon} *BOT STARTED*

*Mode:* {mode}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SilkTrader v3 is now running autonomously.
        """
        
        return self._send_message_sync(message)
    
    def send_bot_stopped(self, reason: str = "User stopped") -> bool:
        """Notify when bot stops
        
        Args:
            reason: Stop reason
            
        Returns:
            Success status
        """
        message = f"""⚪ *BOT STOPPED*

*Reason:* {reason}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SilkTrader v3 has been stopped.
        """
        
        return self._send_message_sync(message)
    
    def send_custom_message(self, title: str, body: str, icon: str = "ℹ️") -> bool:
        """Send custom notification
        
        Args:
            title: Message title
            body: Message body
            icon: Emoji icon
            
        Returns:
            Success status
        """
        message = f"""{icon} *{title}*

{body}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self._send_message_sync(message)

if __name__ == '__main__':
    # Test script
    import sys
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("❌ Telegram notifier not configured. Please add credentials to config file.")
        sys.exit(1)
    
    print("Testing Telegram notifications...\n")
    
    # Test bot start
    print("1. Sending bot start notification...")
    notifier.send_bot_started("PAPER TRADING")
    
    # Test position opened
    print("2. Sending position opened notification...")
    notifier.send_position_opened(
        pair="BTC_USDT",
        side="BUY",
        entry_price=45000.00,
        quantity=0.002,
        position_usdt=90.00,
        stop_loss=44100.00,
        take_profit=46350.00
    )
    
    # Test trailing stop
    print("3. Sending trailing stop notification...")
    notifier.send_trailing_stop_activated(
        pair="BTC_USDT",
        current_price=46000.00,
        new_stop=45540.00,
        profit_pct=2.22
    )
    
    # Test position closed (profit)
    print("4. Sending position closed (profit) notification...")
    notifier.send_position_closed(
        pair="BTC_USDT",
        reason="TAKE_PROFIT",
        entry_price=45000.00,
        exit_price=46350.00,
        quantity=0.002,
        pnl_usdt=2.70,
        pnl_pct=3.0,
        duration="4h 32m"
    )
    
    # Test daily summary
    print("5. Sending daily summary...")
    notifier.send_daily_summary(
        trades_today=5,
        wins=3,
        losses=2,
        total_pnl=12.35,
        win_rate=60.0,
        open_positions=2
    )
    
    print("\n✅ All test notifications sent! Check your Telegram.")
