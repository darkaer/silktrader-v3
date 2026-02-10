# Telegram Notifications Setup Guide

Get real-time trading alerts on your phone with Telegram notifications.

## Quick Setup (5 minutes)

### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow the prompts:
   - Choose a display name (e.g., "SilkTrader Bot")
   - Choose a username ending in `bot` (e.g., "mysilktrader_bot")
4. **Copy the bot token** (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Start a chat and it will send you your **Chat ID** (looks like `123456789`)
3. **Copy this number**

### Step 3: Configure SilkTrader

1. Edit your `credentials/pionex.json` file:

```json
{
  "api_key": "your_pionex_api_key",
  "api_secret": "your_pionex_api_secret",
  
  "telegram": {
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "123456789",
    "enabled": true
  },
  
  "risk_limits": {
    ...
  }
}
```

2. Replace `bot_token` with your token from @BotFather
3. Replace `chat_id` with your ID from @userinfobot

### Step 4: Test Notifications

```bash
cd /lab/dev/silktrader-v3
python3 -c "import sys; sys.path.append('lib'); from telegram_notifier import TelegramNotifier; TelegramNotifier().send_bot_started('TEST')"
```

You should receive a test message on Telegram! 🎉

---

## Notification Types

SilkTrader sends these notifications:

### 🟢 Position Opened
```
🟢 NEW POSITION OPENED

Pair: BTC_USDT
Side: BUY
Entry: $45,000.00
Quantity: 0.002
Size: $90.00

Stop Loss: $44,100.00
Take Profit: $46,350.00
```

### 💰 Position Closed (Profit)
```
💰 POSITION CLOSED - PROFIT

Pair: BTC_USDT
Reason: TAKE_PROFIT

Entry: $45,000.00
Exit: $46,350.00
Quantity: 0.002

P&L: +$2.70 (+3.00%)
Duration: 4h 32m
```

### 🔴 Position Closed (Loss)
```
🔴 POSITION CLOSED - LOSS

Pair: ETH_USDT
Reason: STOP_LOSS

Entry: $2,500.00
Exit: $2,450.00
Quantity: 0.04

P&L: -$2.00 (-2.00%)
Duration: 1h 15m
```

### 🎯 Trailing Stop Activated
```
🎯 TRAILING STOP ACTIVATED

Pair: BTC_USDT
Current Price: $46,000.00
New Stop: $45,540.00
Profit: +2.22%
```

### 📊 Daily Summary
```
📊 DAILY SUMMARY

Trades Closed: 5
Wins: 3 | Losses: 2
Win Rate: 60.0%

💰 Total P&L: +$12.35

Open Positions: 2
```

### ⚠️ Error Alerts
```
⚠️ ERROR ALERT

Type: API_ERROR
Details: Connection timeout to exchange
```

---

## Integration with Your Bot

### In `monitor_positions.py`

Add at the top:
```python
import sys
sys.path.append('lib')
from telegram_notifier import TelegramNotifier

# Initialize
notifier = TelegramNotifier()
```

When closing a position:
```python
# Send notification
notifier.send_position_closed(
    pair=symbol,
    reason=reason,
    entry_price=entry,
    exit_price=exit,
    quantity=qty,
    pnl_usdt=pnl_usd,
    pnl_pct=pnl_pct,
    duration=duration_str
)
```

When trailing stop activates:
```python
notifier.send_trailing_stop_activated(
    pair=symbol,
    current_price=current_price,
    new_stop=new_stop,
    profit_pct=profit_pct
)
```

### In `silktrader_bot.py`

When entering position:
```python
notifier.send_position_opened(
    pair=pair,
    side="BUY",
    entry_price=entry_price,
    quantity=quantity,
    position_usdt=position_size,
    stop_loss=stop_loss,
    take_profit=take_profit
)
```

On bot start:
```python
mode = "PAPER TRADING" if config["paper_trading"] else "LIVE TRADING"
notifier.send_bot_started(mode)
```

---

## Disabling Notifications

### Temporarily disable:
```json
"telegram": {
  "bot_token": "...",
  "chat_id": "...",
  "enabled": false
}
```

### Permanently remove:
Delete the entire `"telegram"` section from `credentials/pionex.json`.

---

## Troubleshooting

### "Telegram notifier not configured"
- Check that `credentials/pionex.json` has the `telegram` section
- Verify bot_token and chat_id are filled in (not placeholder text)

### "Failed to send Telegram message: Unauthorized"
- Bot token is incorrect
- Get a new token from @BotFather with `/newbot`

### "Failed to send Telegram message: Chat not found"
- Chat ID is incorrect
- Verify your Chat ID with @userinfobot
- Make sure you've started a conversation with your bot first

### "Bot doesn't respond when I message it"
- This is normal! The bot only SENDS messages, it doesn't receive/respond
- It's a notification bot, not a chat bot

### Messages delayed?
- Check your internet connection
- Telegram API may be rate-limiting (rare)
- Bot will retry failed messages automatically

---

## Advanced: Multiple Recipients

To send notifications to a group:

1. Create a Telegram group
2. Add your bot to the group
3. Get the group chat ID:
   - Add @userinfobot to the group
   - It will show the group ID (negative number like `-987654321`)
4. Use the group ID as your `chat_id`

Now everyone in the group gets notifications!

---

## Security Notes

- **Never share your bot token** - it gives full control of your bot
- **Keep credentials/pionex.json private** - it contains sensitive tokens
- Bot tokens in example files are placeholders - they won't work
- If token is compromised, revoke it in @BotFather with `/revoke`

---

## Testing Script

Test all notification types:

```bash
python3 lib/telegram_notifier.py
```

This sends test messages for:
1. Bot started
2. Position opened
3. Trailing stop activated  
4. Position closed (profit)
5. Daily summary

---

## Next Steps

1. ✅ Set up Telegram bot (you are here)
2. 🔄 Integrate with `monitor_positions.py`
3. 🔄 Integrate with `silktrader_bot.py`
4. 🚀 Run your bot autonomously with peace of mind!

For integration code examples, see:
- `docs/INTEGRATION_EXAMPLES.md` (coming soon)
- `examples/telegram_integration.py` (coming soon)
