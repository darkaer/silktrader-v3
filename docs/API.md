# Pionex API Documentation

Comprehensive reference for `lib/pionex_api.py` - the low-level exchange API client.

## Overview

`PionexAPI` provides authenticated access to Pionex exchange with built-in:
- ✅ Automatic authentication (HMAC-SHA256 signatures)
- ✅ Rate limiting (50ms between requests)
- ✅ Retry logic (3 attempts with exponential backoff)
- ✅ Comprehensive error handling
- ✅ Detailed logging

---

## Initialization

```python
from lib.pionex_api import PionexAPI

# Initialize with default credentials path
api = PionexAPI()  # Uses 'credentials/pionex.json'

# Or specify custom path
api = PionexAPI('path/to/credentials.json')
```

### Configuration File Format

```json
{
  "PIONEX_API_KEY": "your_api_key_here",
  "PIONEX_API_SECRET": "your_secret_here",
  "base_url": "https://api.pionex.com"
}
```

---

## Market Data Methods

### `get_symbols(quote='USDT', min_volume=0)`

Get all tradeable pairs for a quote currency.

**Parameters:**
- `quote` (str): Quote currency to filter by (default: 'USDT')
- `min_volume` (float): Minimum 24h volume (not implemented yet)

**Returns:**
- `List[str]`: List of symbol names (e.g., ['BTC_USDT', 'ETH_USDT', ...])

**Example:**
```python
symbols = api.get_symbols(quote='USDT')
print(f"Found {len(symbols)} USDT pairs")
# Output: Found 358 USDT pairs
```

---

### `get_klines(symbol, interval='15M', limit=100)`

Get OHLCV candlestick data for technical analysis.

**Parameters:**
- `symbol` (str): Trading pair (e.g., 'BTC_USDT')
- `interval` (str): Timeframe - '1M', '5M', '15M', '30M', '60M', '4H', '8H', '12H', '1D'
- `limit` (int): Number of candles to fetch (max: 1000)

**Returns:**
- `List[Dict]`: List of kline dictionaries:
  ```python
  {
    'timestamp': 1707506400000,  # Unix timestamp (ms)
    'open': 70096.67,
    'high': 70341.23,
    'low': 69873.12,
    'close': 69941.75,
    'volume': 468.1508
  }
  ```

**Example:**
```python
klines = api.get_klines('BTC_USDT', interval='15M', limit=100)
for k in klines[-5:]:  # Last 5 candles
    print(f"Close: ${k['close']:.2f}, Volume: {k['volume']:.4f}")
```

---

### `get_24h_ticker(symbol=None)`

Get 24-hour price statistics.

**Parameters:**
- `symbol` (str, optional): Specific pair or None for all pairs

**Returns:**
- `Dict`: Ticker data for one symbol, or dict with all tickers

**Example:**
```python
ticker = api.get_24h_ticker('BTC_USDT')
print(f"Price: ${ticker['close']}")
print(f"24h Volume: {ticker['volume']}")
```

---

## Account Methods

### `get_account_balance()`

Get balance for all currencies in account.

**Returns:**
- `Dict`: Balance data with structure:
  ```python
  {
    'balances': [
      {'coin': 'USDT', 'free': '29.04', 'frozen': '0.00'},
      {'coin': 'BTC', 'free': '0.00021303', 'frozen': '0.00'},
      ...
    ]
  }
  ```

**Example:**
```python
balance_data = api.get_account_balance()
for bal in balance_data['balances']:
    total = float(bal['free']) + float(bal['frozen'])
    if total > 0:
        print(f"{bal['coin']}: {total:.8f}")
```

---

### `get_balance_by_currency(currency='USDT')`

Get balance for a specific currency (convenience method).

**Parameters:**
- `currency` (str): Currency code (e.g., 'USDT', 'BTC', 'ETH')

**Returns:**
- `Tuple[float, float, float]`: (free, frozen, total)

**Example:**
```python
free, frozen, total = api.get_balance_by_currency('USDT')
print(f"Available: ${free:.2f}")
print(f"In orders: ${frozen:.2f}")
print(f"Total: ${total:.2f}")
```

---

## Trading Methods

### `place_order(symbol, side, order_type, quantity, price=None, client_order_id=None)`

Place a new order.

**Parameters:**
- `symbol` (str): Trading pair (e.g., 'BTC_USDT')
- `side` (str): 'BUY' or 'SELL'
- `order_type` (str): 'LIMIT' or 'MARKET'
- `quantity` (float): Order size in base currency
- `price` (float, optional): Limit price (required for LIMIT orders)
- `client_order_id` (str, optional): Custom tracking ID

**Returns:**
- `Dict`: Order result with `orderId` and status

**Example:**
```python
# Market buy
result = api.place_order(
    symbol='BTC_USDT',
    side='BUY',
    order_type='MARKET',
    quantity=0.001
)

# Limit sell
result = api.place_order(
    symbol='BTC_USDT',
    side='SELL',
    order_type='LIMIT',
    quantity=0.001,
    price=71000.00
)

order_id = result['data']['orderId']
print(f"Order placed: {order_id}")
```

---

### `get_order_status(symbol, order_id)`

Check status of a specific order.

**Parameters:**
- `symbol` (str): Trading pair
- `order_id` (str): Order ID from `place_order()`

**Returns:**
- `Dict`: Order details including:
  - `status`: 'NEW', 'FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'REJECTED'
  - `origQty`: Original order quantity
  - `executedQty`: Filled quantity
  - `price`: Order price

**Example:**
```python
order = api.get_order_status('BTC_USDT', order_id)
print(f"Status: {order['status']}")
print(f"Filled: {order['executedQty']}/{order['origQty']}")
```

---

### `get_open_orders(symbol=None)`

Get all open orders.

**Parameters:**
- `symbol` (str, optional): Filter by trading pair

**Returns:**
- `List[Dict]`: List of open orders

**Example:**
```python
open_orders = api.get_open_orders('BTC_USDT')
print(f"Open orders: {len(open_orders)}")
for order in open_orders:
    print(f"{order['side']} {order['origQty']} @ {order['price']}")
```

---

### `get_order_history(symbol=None, limit=100, start_time=None, end_time=None)`

Get historical orders (open + closed).

**Parameters:**
- `symbol` (str, optional): Trading pair (**required by Pionex API**)
- `limit` (int): Max results (default: 100)
- `start_time` (int, optional): Start timestamp (ms)
- `end_time` (int, optional): End timestamp (ms)

**Returns:**
- `List[Dict]`: Historical orders

**Example:**
```python
history = api.get_order_history(symbol='BTC_USDT', limit=50)
for order in history:
    print(f"{order['side']} {order['status']} - {order['symbol']}")
```

---

### `get_trade_history(symbol=None, limit=100, start_time=None, end_time=None)`

Get trade history (actual fills/executions).

**Parameters:**
- `symbol` (str, optional): Trading pair (**required by Pionex API**)
- `limit` (int): Max results (default: 100)
- `start_time` (int, optional): Start timestamp (ms)
- `end_time` (int, optional): End timestamp (ms)

**Returns:**
- `List[Dict]`: Trade fills with execution details

**Example:**
```python
trades = api.get_trade_history(symbol='BTC_USDT', limit=20)
for trade in trades:
    print(f"{trade['side']} {trade['qty']} @ {trade['price']}")
```

---

### `cancel_order(symbol, order_id)`

Cancel a specific open order.

**Parameters:**
- `symbol` (str): Trading pair
- `order_id` (str): Order ID to cancel

**Returns:**
- `Dict`: Cancellation result

**Example:**
```python
result = api.cancel_order('BTC_USDT', order_id)
if result.get('result'):
    print("Order cancelled successfully")
```

---

### `cancel_all_orders(symbol=None)`

Cancel all open orders (emergency stop).

**Parameters:**
- `symbol` (str, optional): Limit to specific pair, or None for all

**Returns:**
- `Dict`: Cancellation result

**Example:**
```python
# Cancel all orders for BTC_USDT
api.cancel_all_orders('BTC_USDT')

# Cancel ALL orders across all pairs
api.cancel_all_orders()
```

---

## Helper Methods

### `wait_for_order_fill(symbol, order_id, timeout=30, poll_interval=1.0)`

Poll order status until filled or timeout.

**Parameters:**
- `symbol` (str): Trading pair
- `order_id` (str): Order ID to monitor
- `timeout` (int): Max seconds to wait (default: 30)
- `poll_interval` (float): Seconds between checks (default: 1.0)

**Returns:**
- `Tuple[bool, Dict]`: (success, order_data)

**Example:**
```python
success, order = api.wait_for_order_fill('BTC_USDT', order_id, timeout=60)
if success:
    print(f"Order filled: {order['executedQty']}")
else:
    print(f"Order status: {order['status']}")
```

---

### `is_symbol_tradeable(symbol)`

Check if a trading pair is currently tradeable.

**Parameters:**
- `symbol` (str): Trading pair to check

**Returns:**
- `bool`: True if tradeable, False otherwise

**Example:**
```python
if api.is_symbol_tradeable('BTC_USDT'):
    print("BTC_USDT is available for trading")
else:
    print("BTC_USDT is not available")
```

⚠️ **Known Issue**: Currently returns False for valid symbols due to data structure mismatch (non-blocking).

---

## Error Handling

### Retry Logic

All methods automatically retry failed requests up to 3 times with exponential backoff:
- Attempt 1: Immediate
- Attempt 2: Wait 2 seconds
- Attempt 3: Wait 4 seconds

### Error Response Format

Failed requests return a dict with `error` key:

```python
{
  'error': 'Connection timeout',
  'retries_exhausted': True
}
```

### HTTP Status Codes

- `4xx` errors (except 429): No retry (client error)
- `429` (rate limit): Retries with backoff
- `5xx` errors: Retries with backoff
- `Timeout`: Retries with backoff

### Example Error Handling

```python
result = api.get_account_balance()

if 'error' in result:
    print(f"API Error: {result['error']}")
    # Handle error
else:
    # Process successful result
    balances = result['data']['balances']
```

---

## Rate Limiting

**Enforced**: 50ms minimum between requests (20 requests/second max)

**Automatic**: The API client handles this internally - you don't need to add delays.

**Override** (not recommended):
```python
api.min_request_interval = 0.1  # 100ms between requests
```

---

## Logging

The API uses Python's `logging` module:

```python
import logging

# Set log level
logging.getLogger('PionexAPI').setLevel(logging.DEBUG)

# Log levels used:
# - DEBUG: Detailed request/response info
# - INFO: Successful operations
# - WARNING: API errors, retries
# - ERROR: Critical failures
```

---

## Testing

Run the comprehensive test suite:

```bash
python tests/test_pionex_api.py
```

**Tests cover:**
- ✅ Symbol listing
- ✅ Market data (klines, tickers)
- ✅ Account balance
- ✅ Order operations
- ✅ Trade history
- ✅ Rate limiting
- ✅ Error handling

---

## Best Practices

### 1. Always Check for Errors

```python
result = api.place_order(...)
if 'error' in result:
    # Handle error
    return
order_id = result['data']['orderId']
```

### 2. Use Specific Currency Queries

```python
# Good: Direct currency query
free, frozen, total = api.get_balance_by_currency('USDT')

# Less efficient: Parse all balances
all_balances = api.get_account_balance()
```

### 3. Wait for Order Fills

```python
# Place order
result = api.place_order('BTC_USDT', 'BUY', 'LIMIT', 0.001, 70000)
order_id = result['data']['orderId']

# Wait for fill (instead of polling manually)
success, order = api.wait_for_order_fill('BTC_USDT', order_id, timeout=60)
```

### 4. Emergency Stop

```python
# In case of issues, cancel all orders
try:
    # Trading logic
    ...
except Exception as e:
    api.cancel_all_orders()  # Emergency stop
    raise
```

---

## References

- **Official Docs**: https://pionex-doc.gitbook.io/apidocs/
- **Authentication**: https://pionex-doc.gitbook.io/apidocs/restful/general/authentication
- **Test Suite**: `tests/test_pionex_api.py`
- **Source Code**: `lib/pionex_api.py`

---

**Last Updated**: February 9, 2026  
**Version**: v0.2.1  
**Status**: Production-ready ✅
