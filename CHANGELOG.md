# Changelog

All notable changes to SilkTrader v3 will be documented here.

## [Unreleased]

### Tier 0: Exchange Integration (v0.3.0) - In Planning
- Robust balance and position synchronization
- Order status and lifecycle management
- Pre-trade validation system
- Error recovery and retry logic
- Exchange manager abstraction layer

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

Current: v0.2.0 → Next: v0.3.0 (Exchange Integration)
