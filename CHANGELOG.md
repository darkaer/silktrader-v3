# SilkTrader v3 - Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Telegram notifications for trade execution
- Backtesting framework with historical data
- Multi-exchange support (Binance, OKX)
- Kelly Criterion position sizing (v0.4.0+ after 50+ trades)
- Advanced market scanner with ML scoring

---

## [0.2.3] - 2026-02-09

### Added
- **ExchangeManager**: High-level trading interface (`lib/exchange_manager.py`)
  - Combines PionexAPI + RiskManager for validated order execution
  - Paper trading mode via `dry_run` flag for safe testing
  - Position affordability validation against exchange minimums
  - Order calculation with comprehensive validation pipeline
  - Daily P&L tracking and trade counter
  - Position summary reporting
  - Max positions enforcement (3 concurrent)
  - Stop-loss reference passing (managed by position monitor)

- **Test Suite**: `tests/test_exchange_manager.py` (10 comprehensive tests)
  - All tests passing with $29.04 account
  - Paper & live trading modes tested
  - Real-world scenario validation

### Technical Details
- Integration with tiered position sizing
- Defense-in-depth: 3 validation layers
- Cached symbol info usage
- Comprehensive logging

**See**: [Release Notes v0.2.3](docs/RELEASE_NOTES_v0.2.3.md)

---

## [0.2.2] - 2026-02-09
### Added
- Symbol info caching (24h TTL)

## [0.2.1] - 2026-02-09
### Fixed
- INVALID_TIMESTAMP authentication error
### Added
- Order lifecycle management
- Enhanced balance management
- Test suite with 12 tests

**See**: [Release Notes v0.2.1](docs/RELEASE_NOTES_v0.2.1.md)
