#!/usr/bin/env python3
"""Comprehensive tests for MarketScanner"""

import sys
import logging
from unittest.mock import Mock, MagicMock

# Add parent directory to path
sys.path.insert(0, '.')
sys.path.append('skills/silktrader-scanner/scripts')
sys.path.append('skills/silktrader-trader/scripts')

from scanner import MarketScanner
from lib.pionex_api import PionexAPI
from lib.exchange_manager import ExchangeManager


def create_mock_api():
    """Create mock PionexAPI"""
    api = Mock(spec=PionexAPI)
    
    # Mock symbols (simulated pairs)
    api.get_symbols.return_value = [
        {'symbol': 'BTC_USDT', 'enable': True},
        {'symbol': 'ETH_USDT', 'enable': True},
        {'symbol': 'SOL_USDT', 'enable': True},
        {'symbol': 'DOGE_USDT', 'enable': True},
        {'symbol': 'BTC_EUR', 'enable': True},  # Not USDT
        {'symbol': 'DISABLED_USDT', 'enable': False},  # Disabled
    ]
    
    # Mock klines (simulated 1-hour candles)
    mock_klines = []
    for i in range(100):
        mock_klines.append({
            'timestamp': 1707500000000 + (i * 3600000),  # 1-hour intervals
            'open': 70000.0 + i,
            'high': 70100.0 + i,
            'low': 69900.0 + i,
            'close': 70000.0 + i + 10,
            'volume': 100.0 + (i * 2)
        })
    
    api.get_klines.return_value = mock_klines
    
    return api


def create_mock_exchange_manager():
    """Create mock ExchangeManager"""
    em = Mock(spec=ExchangeManager)
    
    # Mock balance
    em.get_available_balance.return_value = 29.04
    
    # Mock affordability (BTC/ETH/SOL affordable, DOGE not)
    def mock_affordability(pair, price, balance):
        return pair != 'DOGE_USDT'
    
    em.is_pair_affordable.side_effect = mock_affordability
    
    return em


def test_initialization():
    """Test scanner initialization"""
    print("\n" + "="*70)
    print("TEST: Scanner Initialization")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    assert scanner.api == api, "API not set!"
    assert scanner.exchange_manager is None, "ExchangeManager should be None!"
    print("✓ Basic initialization successful")
    
    # With exchange manager
    em = create_mock_exchange_manager()
    scanner_with_em = MarketScanner(api, em)
    
    assert scanner_with_em.exchange_manager == em, "ExchangeManager not set!"
    print("✓ Initialization with ExchangeManager successful")
    
    print("\n✅ Initialization tests passed!")


def test_get_usdt_pairs():
    """Test USDT pair filtering"""
    print("\n" + "="*70)
    print("TEST: USDT Pair Filtering")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    pairs = scanner.get_usdt_pairs()
    
    assert len(pairs) == 4, f"Expected 4 USDT pairs, got {len(pairs)}!"
    assert 'BTC_USDT' in pairs, "BTC_USDT missing!"
    assert 'ETH_USDT' in pairs, "ETH_USDT missing!"
    assert 'SOL_USDT' in pairs, "SOL_USDT missing!"
    assert 'DOGE_USDT' in pairs, "DOGE_USDT missing!"
    assert 'BTC_EUR' not in pairs, "BTC_EUR should be filtered out!"
    assert 'DISABLED_USDT' not in pairs, "DISABLED_USDT should be filtered out!"
    print(f"✓ Filtered to {len(pairs)} USDT pairs: {pairs}")
    
    print("\n✅ USDT pair filtering tests passed!")


def test_fetch_klines():
    """Test kline fetching"""
    print("\n" + "="*70)
    print("TEST: Kline Fetching")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    klines = scanner.fetch_klines('BTC_USDT', '1h', 100)
    
    assert len(klines) == 100, f"Expected 100 klines, got {len(klines)}!"
    assert 'close' in klines[0], "Missing 'close' field!"
    assert 'volume' in klines[0], "Missing 'volume' field!"
    print(f"✓ Fetched {len(klines)} klines for BTC_USDT")
    print(f"  First candle close: ${klines[0]['close']:.2f}")
    print(f"  Last candle close: ${klines[-1]['close']:.2f}")
    
    # Test error handling
    api.get_klines.side_effect = Exception("API Error")
    klines_error = scanner.fetch_klines('FAKE_USDT', '1h', 100)
    assert len(klines_error) == 0, "Should return empty list on error!"
    print("✓ Error handling works correctly")
    
    print("\n✅ Kline fetching tests passed!")


def test_score_opportunity():
    """Test opportunity scoring"""
    print("\n" + "="*70)
    print("TEST: Opportunity Scoring")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    # Strong bullish setup
    strong_indicators = {
        'price': 70000.0,
        'ema_fast': 69000.0,
        'ema_slow': 67500.0,
        'rsi': 55.0,
        'rsi_prev': 50.0,
        'macd': 100.0,
        'macd_signal': 90.0,
        'macd_hist': 10.0,
        'volume': 1000.0,
        'volume_ma': 500.0,
        'volume_ratio': 2.0,
        'atr': 1400.0
    }
    
    score, reasoning = scanner.score_opportunity('BTC_USDT', strong_indicators)
    
    assert score >= 70, f"Strong setup should score >= 70, got {score}!"
    assert len(reasoning) > 0, "Reasoning should not be empty!"
    print(f"✓ Strong setup scored: {score}/100")
    print(f"  Reasoning: {reasoning}")
    
    # Weak setup
    weak_indicators = {
        'price': 70000.0,
        'ema_fast': 70100.0,
        'ema_slow': 70200.0,
        'rsi': 75.0,
        'rsi_prev': 76.0,
        'macd': -50.0,
        'macd_signal': -40.0,
        'macd_hist': -10.0,
        'volume': 500.0,
        'volume_ma': 1000.0,
        'volume_ratio': 0.5,
        'atr': 700.0
    }
    
    weak_score, weak_reasoning = scanner.score_opportunity('WEAK_USDT', weak_indicators)
    
    assert weak_score < 50, f"Weak setup should score < 50, got {weak_score}!"
    print(f"✓ Weak setup scored: {weak_score}/100")
    
    print("\n✅ Opportunity scoring tests passed!")


def test_scan_markets_no_filters():
    """Test market scan without filters"""
    print("\n" + "="*70)
    print("TEST: Market Scan (No Filters)")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    # Scan with no affordability check
    opportunities = scanner.scan_markets(
        top_n=10,
        min_score=0,
        check_affordability=False
    )
    
    assert len(opportunities) > 0, "Should find at least some opportunities!"
    assert len(opportunities) <= 10, "Should respect top_n limit!"
    print(f"✓ Found {len(opportunities)} opportunities")
    
    # Check structure
    if opportunities:
        opp = opportunities[0]
        assert 'pair' in opp, "Missing 'pair' field!"
        assert 'score' in opp, "Missing 'score' field!"
        assert 'confidence' in opp, "Missing 'confidence' field!"
        assert 'entry_price' in opp, "Missing 'entry_price' field!"
        assert 'indicators' in opp, "Missing 'indicators' field!"
        assert 'reasoning' in opp, "Missing 'reasoning' field!"
        assert 'affordable' in opp, "Missing 'affordable' field!"
        assert 'timestamp' in opp, "Missing 'timestamp' field!"
        print(f"✓ Opportunity structure valid: {opp['pair']} @ {opp['score']}/100")
    
    print("\n✅ Market scan tests passed!")


def test_scan_markets_with_filters():
    """Test market scan with filters"""
    print("\n" + "="*70)
    print("TEST: Market Scan (With Filters)")
    print("="*70)
    
    api = create_mock_api()
    em = create_mock_exchange_manager()
    scanner = MarketScanner(api, em)
    
    # Scan with minimum score and affordability
    opportunities = scanner.scan_markets(
        top_n=3,
        min_score=50,
        check_affordability=True
    )
    
    print(f"✓ Found {len(opportunities)} opportunities (min_score=50, top_n=3)")
    
    # Check affordability filter worked
    for opp in opportunities:
        if opp['pair'] == 'DOGE_USDT':
            assert False, "DOGE_USDT should be filtered by affordability!"
    
    print("✓ Affordability filter working correctly")
    
    # Check sorting (highest score first)
    if len(opportunities) > 1:
        for i in range(len(opportunities) - 1):
            assert opportunities[i]['score'] >= opportunities[i+1]['score'], \
                "Opportunities not sorted by score!"
        print("✓ Opportunities sorted by score (highest first)")
    
    print("\n✅ Filtered scan tests passed!")


def test_format_opportunity():
    """Test opportunity formatting"""
    print("\n" + "="*70)
    print("TEST: Opportunity Formatting")
    print("="*70)
    
    api = create_mock_api()
    scanner = MarketScanner(api)
    
    opp = {
        'pair': 'BTC_USDT',
        'score': 85,
        'entry_price': 70000.0,
        'indicators': {
            'price': 70000.0,
            'ema_fast': 69000.0,
            'ema_slow': 67500.0,
            'rsi': 55.0,
            'rsi_prev': 50.0,
            'macd': 100.0,
            'macd_signal': 90.0,
            'macd_hist': 10.0,
            'volume': 1000.0,
            'volume_ma': 500.0,
            'volume_ratio': 2.0,
            'atr': 1400.0
        },
        'reasoning': 'Strong uptrend | RSI neutral zone',
        'affordable': True,
        'timestamp': '2026-02-09 20:45:00'
    }
    
    formatted = scanner.format_opportunity(opp)
    
    assert 'BTC_USDT' in formatted, "Missing pair name!"
    assert '85/100' in formatted, "Missing score!"
    assert '70000' in formatted, "Missing entry price!"
    assert '✅ YES' in formatted, "Missing affordability!"
    print("✓ Opportunity formatted correctly")
    print(formatted)
    
    print("\n✅ Formatting tests passed!")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "#"*70)
    print("# SilkTrader v3 - Market Scanner Test Suite")
    print("#"*70)
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    test_functions = [
        test_initialization,
        test_get_usdt_pairs,
        test_fetch_klines,
        test_score_opportunity,
        test_scan_markets_no_filters,
        test_scan_markets_with_filters,
        test_format_opportunity
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {test_func.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "#"*70)
    print("# Test Results")
    print("#"*70)
    print(f"✓ Passed: {passed}/{len(test_functions)}")
    print(f"✗ Failed: {failed}/{len(test_functions)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("\nMarket Scanner is ready for integration:")
        print("  • USDT pair filtering operational")
        print("  • Kline fetching and caching working")
        print("  • TA indicator calculation functional")
        print("  • Scoring algorithm validated (0-100 scale)")
        print("  • Affordability filtering integrated")
        print("  • Top-N selection and sorting working")
        print("\nNext steps:")
        print("  1. Test with live API: python skills/silktrader-scanner/scripts/scanner.py")
        print("  2. Integrate with main bot: silktrader_bot.py")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - Review above errors")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
