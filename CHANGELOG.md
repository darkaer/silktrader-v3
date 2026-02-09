# Changelog

All notable changes to SilkTrader v3 will be documented here.

## [Unreleased]

### Tier 0: Exchange Integration (v0.3.0) - In Progress
- [ ] Exchange manager abstraction layer (`lib/exchange_manager.py`)
- [ ] Pre-trade validation system integration
- [ ] Position synchronization with exchange
- [ ] Advanced order types support
- [x] Robust balance and position synchronization
- [x] Order status and lifecycle management  
- [x] Error recovery and retry logic

## [0.2.1] - 2026-02-09

### Fixed - Pionex API Authentication & Endpoints
- **CRITICAL**: Fixed `INVALID_TIMESTAMP` error in authenticated requests
  - Timestamp now correctly added to query parameters
  - Query parameters properly sorted for signature generation
  - Signature format matches Pionex spec: `METHOD+PATH+?+SORTED_QUERY+BODY`
- **Balance Fields**: Changed `locked` → `frozen` to match Pionex API response format
- **Trade History Endpoint**: Corrected `/api/v1/trade/myTrades` → `/api/v1/trade/fills`
- **Removed Non-Existent Endpoint**: Deleted `get_account_info()` method (404 in Pionex API)

### Added - Enhanced API Methods
- **Order Lifecycle Management**:
  - `get_order_status(symbol, order_id)` - Query specific order details
  - `get_order_history(symbol, limit, start_time, end_time)` - Historical orders
  - `get_trade_history(symbol, limit, start_time, end_time)` - Actual fills/executions
  - `wait_for_order_fill(symbol, order_id, timeout)` - Poll until filled/failed
  - `cancel_all_orders(symbol)` - Emergency order cancellation
  
- **Balance Management**:
  - `get_balance_by_currency(currency)` - Returns tuple of (free, frozen, total)
  - Enhanced `get_account_balance()` with better error handling
  
- **Helper Methods**:
  - `is_symbol_tradeable(symbol)` - Pre-trade validation check
  - Enhanced logging throughout all methods

- **Reliability Features**:
  - Retry logic with exponential backoff (max 3 attempts)
  - Rate limiting enforcement (50ms between requests)
  - Comprehensive error handling for network issues
  - Detailed logging at INFO/WARNING/ERROR levels

### Added - Testing Infrastructure
- Created `tests/test_pionex_api.py` with 12 comprehensive test cases
- Tests cover: symbols, klines, tickers, balances, orders, trade history, rate limiting, error handling
- Real API integration testing (validated with $29.04 USDT balance)
- All critical paths tested and passing

### Changed - Code Quality
- Added type hints: `Tuple[float, float, float]` for balance methods
- Improved docstrings with detailed Args/Returns sections
- Consistent error response format across all methods
- Better separation of concerns (rate limiting, signature generation)

### Technical Details
- Enhanced `lib/pionex_api.py`: ~400 lines of improved code
- Test suite: `tests/test_pionex_api.py`: 259 lines
- Authentication now 100% compliant with Pionex API specification
- Based on official docs: https://pionex-doc.gitbook.io/apidocs/

### Verified Working
✅ Market data retrieval (symbols, klines, tickers)
✅ Account balance fetching (all currencies + specific currency)
✅ Order management (place, status, history, cancel)
✅ Trade history (fills/executions)
✅ Rate limiting and retry logic
✅ Error handling and graceful degradation

## [0.2.0] - 2026-02-09

### Added - Enhanced Risk Management System
- **Input Validation**: All price/balance parameters validated before use
- **Daily Limits Integration**: Trade validation now checks daily trade count and P&L limits
- **Configurable Parameters**: Risk percentages, ATR multipliers, min/max sizes moved to config
- **High Water Mark Tracking**: Trailing stops now track peak prices for better profit locking
- **Minimum Order Sizes**: Exchange-specific quantity validation per trading pair
- **Account Percentage Limit**: Maximum 5% of account per single position
- **Comprehensive Logging**: Full audit trail for all risk management decisions
- **Position Tracking Cleanup**: Memory management for closed positions

### Changed
- `risk_manager.py`: Complete rewrite with 185 new lines of enterprise-grade safety code
- `validate_trade()`: Updated signature to require `quantity`, `trades_today`, and `account_balance`
- `calculate_trailing_stop()`: Now requires `position_id` for high water mark tracking
- `silktrader_bot.py`: Integrated new validation parameters (28 additions)
- `monitor_positions.py`: Added position tracking cleanup (14 additions)
- `pionex.json.example`: Added new configuration sections for risk management

### Added - Testing
- Created `tests/test_risk_manager.py` with 13 comprehensive test cases
- All tests passing: position sizing, validation, trailing stops, input validation
- Test coverage for all critical risk management paths

### Fixed
- Stop loss calculations now properly use configurable ATR multipliers
- Trailing stops properly track highest/lowest prices (high water mark)
- Daily loss limits properly checked before trade validation

### Technical Details
- +522 lines added, -108 lines removed across 5 files
- Test suite: 259 lines covering all risk scenarios
- Risk/reward ratio maintained at 1:1.5 (configurable)

## [0.1.0] - 2026-02-09

### Added
- Initial release
- Market scanner with technical analysis (7 indicators: EMA, RSI, MACD, ATR, Volume)
- LLM decision engine integration via OpenRouter
- Risk management system with position sizing
- Position monitoring with P&L tracking and trailing stops
- OpenClaw skills integration for modular architecture
- Support for Pionex exchange API
- Autonomous trading loop with configurable scan intervals
- Dry-run mode for safe testing
- Paper trading capability

### Core Features
- **Scanner**: Analyzes 300+ pairs, scores opportunities 0-7
- **Trader**: LLM makes BUY/WAIT decisions with confidence scoring
- **Monitor**: Real-time position tracking with automatic exits
- **Risk Manager**: 2% risk per trade, max 3 positions, $500 max position size

### Architecture
- Modular skills-based design (scanner, trader)
- Separation of concerns (API, indicators, LLM, risk management)
- JSON-based configuration and data persistence
- Comprehensive logging system

---

## Version Numbering

- **Major** (X.0.0): Breaking changes, major architecture changes
- **Minor** (0.X.0): New features, significant improvements
- **Patch** (0.0.X): Bug fixes, minor improvements

Current: v0.2.1 → Next: v0.3.0 (Exchange Integration Complete)
