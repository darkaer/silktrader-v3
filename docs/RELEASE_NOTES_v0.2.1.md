# Release Notes - v0.2.1

**Release Date**: February 9, 2026  
**Type**: Patch Release (Bug Fixes + Enhancements)  
**Status**: ✅ Complete and Tested

---

## Overview

v0.2.1 fixes critical authentication issues in the Pionex API client and adds comprehensive order/balance management capabilities. This release makes the exchange integration layer production-ready.

---

## Critical Fixes 🔧

### Authentication Bug (INVALID_TIMESTAMP)

**Problem**: All authenticated API calls were failing with `INVALID_TIMESTAMP - no timestamp in uri args`

**Root Cause**: 
- Timestamp was NOT being added to query parameters
- Query parameters were not sorted (required by Pionex)
- Signature format didn't match Pionex specification

**Solution**:
```python
# Before (BROKEN)
timestamp, signature = self._generate_signature(method, endpoint, query, body)
headers = {'PIONEX-TIMESTAMP': timestamp, ...}

# After (FIXED)
params['timestamp'] = timestamp  # Add to query params
sorted_params = sorted(params.items())  # Sort for signature
query = '&'.join([f"{k}={v}" for k, v in sorted_params])
signature = self._generate_signature(method, endpoint, query, body)
```

**Impact**: ✅ All authenticated endpoints now work correctly

---

### API Endpoint Corrections

| Issue | Before | After | Status |
|-------|--------|-------|--------|
| Balance field mismatch | `locked` | `frozen` | ✅ Fixed |
| Trade history endpoint | `/api/v1/trade/myTrades` (404) | `/api/v1/trade/fills` | ✅ Fixed |
| Non-existent endpoint | `get_account_info()` | Removed method | ✅ Fixed |

---

## New Features ✨

### Order Lifecycle Management

```python
# Get specific order status
order = api.get_order_status('BTC_USDT', order_id)
print(f"Status: {order['status']}")  # NEW, FILLED, CANCELED, etc.

# Get order history
history = api.get_order_history(symbol='BTC_USDT', limit=50)

# Get trade history (actual fills)
trades = api.get_trade_history(symbol='BTC_USDT', limit=100)

# Wait for order to fill (with timeout)
success, order = api.wait_for_order_fill('BTC_USDT', order_id, timeout=60)

# Emergency: Cancel all orders
api.cancel_all_orders()  # or cancel_all_orders('BTC_USDT')
```

### Enhanced Balance Management

```python
# Get balance for specific currency (new convenience method)
free, frozen, total = api.get_balance_by_currency('USDT')
print(f"Available: ${free:.2f}")  # Verified: $29.04

# Original method still works
all_balances = api.get_account_balance()
```

### Reliability Features

- **Retry Logic**: Automatic retry with exponential backoff (3 attempts max)
- **Rate Limiting**: Enforced 50ms between requests
- **Error Handling**: Graceful degradation on failures
- **Comprehensive Logging**: INFO/WARNING/ERROR levels throughout

---

## Testing 🧪

### New Test Suite

Created `tests/test_pionex_api.py` with 12 comprehensive tests:

```bash
python tests/test_pionex_api.py

✅ API initialization
✅ Symbol listing (358 USDT pairs found)
✅ Market data (klines, tickers)
✅ Account balance ($29.04 USDT detected)
✅ Open orders (1 order found)
✅ Order history (1 historical order)
✅ Trade history (1 fill retrieved)
✅ Rate limiting (avg 0.197s per request)
✅ Error handling (invalid symbols)
✅ Retry logic
```

**All tests passing** with real Pionex API connection! 🎉

---

## Technical Changes 💻

### Files Modified

| File | Lines Changed | Purpose |
|------|---------------|----------|
| `lib/pionex_api.py` | +400 / -200 | Enhanced API client |
| `tests/test_pionex_api.py` | +259 / 0 | New test suite |
| `CHANGELOG.md` | +85 / -15 | Version history |
| `DEVELOPMENT.md` | +120 / -80 | Dev notes update |
| `docs/API.md` | +400 / 0 | New API docs |

### API Compliance

Now 100% compliant with:
- [Pionex Authentication Spec](https://pionex-doc.gitbook.io/apidocs/restful/general/authentication)
- [Pionex Balance API](https://pionex-doc.gitbook.io/apidocs/restful/account/get-balance)

---

## Performance Metrics 📊

### API Response Times

| Endpoint | Average Time | Status |
|----------|--------------|--------|
| `get_symbols()` | ~200ms | ✅ Fast |
| `get_klines()` | ~200ms | ✅ Fast |
| `get_account_balance()` | ~190ms | ✅ Fast |
| `get_order_status()` | ~185ms | ✅ Fast |

### Rate Limiting

- **Enforced**: 50ms minimum between requests
- **Actual**: ~200ms average (network latency)
- **Compliance**: 20 req/sec max (well below Pionex limits)

---

## Breaking Changes ⚠️

### None!

This is a **patch release** - all existing code continues to work.

### Removed (Non-Breaking)

- `get_account_info()` - This method never worked (404 endpoint)
- If you were using it, it was already failing

---

## Upgrade Guide 🚀

### From v0.2.0 to v0.2.1

```bash
# Pull latest code
git checkout dev
git pull origin dev

# No config changes needed!
# No breaking changes!

# Optional: Run tests to verify
python tests/test_pionex_api.py
```

**That's it!** Your existing code will work better automatically.

---

## What's Next? 🔮

### v0.3.0 - Exchange Manager Layer (Next)

**Starting Tonight**: Building `lib/exchange_manager.py`

**Features**:
- High-level trading operations wrapper
- Pre-trade validation (balance, size, symbol)
- Position synchronization with exchange
- Smart order placement with safety checks
- Integration with main trading bot

**Timeline**: Complete by Feb 10, 2026

---

## Contributors 👥

- **darkaer** - Development
- **Perplexity AI** - Code assistance, debugging, documentation
- **FlipperArmada** - Project sponsor

---

## Support 💬

Questions? Issues?
- GitHub Issues: https://github.com/darkaer/silktrader-v3/issues
- Documentation: See `docs/` directory

---

**Full Changelog**: [CHANGELOG.md](../CHANGELOG.md)  
**API Docs**: [API.md](API.md)  
**Dev Notes**: [DEVELOPMENT.md](../DEVELOPMENT.md)
