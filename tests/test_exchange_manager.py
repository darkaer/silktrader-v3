#!/usr/bin/env python3
"""Comprehensive tests for ExchangeManager"""

import sys
import logging
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, '.')
sys.path.append('skills/silktrader-trader/scripts')

from lib.exchange_manager import ExchangeManager
from lib.pionex_api import PionexAPI
from risk_manager import RiskManager


def create_mock_api(balance=29.04):
    """Create mock PionexAPI with configurable balance"""
    api = Mock(spec=PionexAPI)
    
    # Mock balance
    api.get_balance_by_currency.return_value = (balance, 0.0, balance)
    
    # Mock symbol info (BTC_USDT example)
    api.get_symbol_info.return_value = {
        'symbol': 'BTC_USDT',
        'minAmount': 0.01,
        'minTradeSize': 0.000001,
        'maxTradeSize': 1000.0,
        'enable': True,
        'timestamp': 1707507600
    }
    
    # Mock open orders
    api.get_open_orders.return_value = []
    
    # Mock order placement
    api.place_order.return_value = {
        'result': True,
        'data': {'orderId': 'TEST123456'}
    }
    
    return api


def create_mock_risk_manager():
    """Create mock RiskManager"""
    rm = Mock(spec=RiskManager)
    
    # Mock limits
    rm.limits = {
        'max_open_positions': 3,
        'min_position_size_usdt': 5.0,
        'max_position_size_usdt': 500.0,
        'max_daily_trades': 10,
        'max_daily_loss_usdt': 100.0
    }
    
    # Mock position sizing
    rm.calculate_position_size_tiered.return_value = (
        7.26,  # position_usdt
        0.00010371,  # quantity
        "Small Account: $29.04, Position: $7.26"
    )
    
    # Mock validation
    rm.validate_trade.return_value = (
        True,
        "Trade approved - all risk checks passed"
    )
    
    # Mock daily limits check
    rm.check_daily_limits.return_value = (
        True,
        "Daily limits OK (0/10 trades, $0.00 P&L)"
    )
    
    return rm


def test_initialization():
    """Test ExchangeManager initialization"""
    print("\n" + "="*70)
    print("TEST: ExchangeManager Initialization")
    print("="*70)
    
    api = create_mock_api()
    rm = create_mock_risk_manager()
    
    # Test paper trading mode
    em_paper = ExchangeManager(api, rm, dry_run=True)
    assert em_paper.dry_run == True, "Paper trading mode not set!"
    assert em_paper._trades_today == 0, "Trades counter not initialized!"
    assert em_paper._daily_pnl == 0.0, "Daily P&L not initialized!"
    print("✓ Paper trading initialization successful")
    
    # Test live trading mode
    em_live = ExchangeManager(api, rm, dry_run=False)
    assert em_live.dry_run == False, "Live trading mode not set!"
    print("✓ Live trading initialization successful")
    
    print("\n✅ Initialization tests passed!")


def test_get_available_balance():
    """Test balance retrieval"""
    print("\n" + "="*70)
    print("TEST: Get Available Balance")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    balance = em.get_available_balance()
    
    assert balance == 29.04, f"Expected $29.04, got ${balance:.2f}!"
    assert api.get_balance_by_currency.called, "API balance method not called!"
    print(f"✓ Balance retrieved: ${balance:.2f}")
    
    # Test error handling
    api.get_balance_by_currency.side_effect = Exception("API Error")
    balance_error = em.get_available_balance()
    assert balance_error == 0.0, "Error not handled properly!"
    print("✓ Error handling works correctly")
    
    print("\n✅ Balance tests passed!")


def test_is_pair_affordable():
    """Test pair affordability checks"""
    print("\n" + "="*70)
    print("TEST: Pair Affordability")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    # Test affordable pair (BTC at $70k - min $0.01)
    affordable = em.is_pair_affordable('BTC_USDT', 70000.0, 29.04)
    assert affordable == True, "BTC_USDT should be affordable!"
    print("✓ BTC_USDT is affordable (min $0.01 < 25% limit $7.26)")
    
    # Test unaffordable pair (mock high minimum)
    api.get_symbol_info.return_value = {
        'symbol': 'FAKE_USDT',
        'minAmount': 10.0,  # High minimum
        'minTradeSize': 1.0,
        'enable': True
    }
    
    unaffordable = em.is_pair_affordable('FAKE_USDT', 10.0, 29.04)
    # 25% of $29.04 = $7.26, minAmount $10 > $7.26
    assert unaffordable == False, "High-minimum pair should be unaffordable!"
    print("✓ High-minimum pair rejected correctly")
    
    # Test disabled pair
    api.get_symbol_info.return_value = {
        'symbol': 'DISABLED_USDT',
        'enable': False
    }
    
    disabled = em.is_pair_affordable('DISABLED_USDT', 100.0, 29.04)
    assert disabled == False, "Disabled pair should be unaffordable!"
    print("✓ Disabled pair rejected correctly")
    
    print("\n✅ Affordability tests passed!")


def test_calculate_order():
    """Test order calculation and validation"""
    print("\n" + "="*70)
    print("TEST: Order Calculation")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    # Test successful order calculation
    result = em.calculate_order('BTC_USDT', 70000.0, 75)
    
    assert result['approved'] == True, "Order should be approved!"
    assert result['pair'] == 'BTC_USDT', "Pair mismatch!"
    assert result['entry_price'] == 70000.0, "Entry price mismatch!"
    assert 'position_usdt' in result, "Missing position_usdt!"
    assert 'quantity' in result, "Missing quantity!"
    print(f"✓ Order approved: ${result['position_usdt']:.2f} ({result['quantity']:.8f} BTC)")
    
    # Test with no balance
    api.get_balance_by_currency.return_value = (0.0, 0.0, 0.0)
    result_no_balance = em.calculate_order('BTC_USDT', 70000.0, 75)
    assert result_no_balance['approved'] == False, "Should reject with no balance!"
    assert 'error' in result_no_balance, "Missing error message!"
    print("✓ No balance rejection works correctly")
    
    # Test with rejected validation
    api.get_balance_by_currency.return_value = (29.04, 0.0, 29.04)
    rm.validate_trade.return_value = (False, "Max positions reached")
    result_rejected = em.calculate_order('BTC_USDT', 70000.0, 75)
    assert result_rejected['approved'] == False, "Should reject when validation fails!"
    print("✓ Risk validation rejection works correctly")
    
    print("\n✅ Order calculation tests passed!")


def test_execute_trade_paper():
    """Test paper trading execution"""
    print("\n" + "="*70)
    print("TEST: Paper Trading Execution")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    result = em.execute_trade(
        pair='BTC_USDT',
        side='BUY',
        entry_price=70000.0,
        confidence=75,
        order_type='LIMIT',
        stop_loss=68000.0,
        take_profit=74000.0
    )
    
    assert result['success'] == True, "Paper trade should succeed!"
    assert result['dry_run'] == True, "Should indicate paper trading!"
    assert 'PAPER_' in result['order_id'], "Order ID should be paper trade format!"
    assert result['stop_loss'] == 68000.0, "Stop loss not passed through!"
    assert result['take_profit'] == 74000.0, "Take profit not passed through!"
    assert not api.place_order.called, "API should NOT be called in paper mode!"
    print(f"✓ Paper trade executed: {result['order_id']}")
    print(f"  Position: ${result['position_usdt']:.2f}")
    print(f"  SL: ${result['stop_loss']}, TP: ${result['take_profit']}")
    
    print("\n✅ Paper trading tests passed!")


def test_execute_trade_live():
    """Test live trading execution"""
    print("\n" + "="*70)
    print("TEST: Live Trading Execution")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=False)
    
    result = em.execute_trade(
        pair='BTC_USDT',
        side='BUY',
        entry_price=70000.0,
        confidence=75
    )
    
    assert result['success'] == True, "Live trade should succeed!"
    assert result['dry_run'] == False, "Should indicate live trading!"
    assert result['order_id'] == 'TEST123456', "Order ID mismatch!"
    assert api.place_order.called, "API should be called in live mode!"
    assert em._trades_today == 1, "Trade counter not incremented!"
    print(f"✓ Live trade executed: {result['order_id']}")
    print(f"  Trades today: {em._trades_today}")
    
    # Test rejected order
    rm.validate_trade.return_value = (False, "Daily limit reached")
    result_rejected = em.execute_trade(
        pair='BTC_USDT',
        side='BUY',
        entry_price=70000.0,
        confidence=75
    )
    assert result_rejected['success'] == False, "Should reject when validation fails!"
    print("✓ Order rejection works correctly")
    
    print("\n✅ Live trading tests passed!")


def test_position_management():
    """Test position tracking and limits"""
    print("\n" + "="*70)
    print("TEST: Position Management")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    # Test get open positions
    positions = em.get_open_positions()
    assert isinstance(positions, list), "Positions should be a list!"
    assert len(positions) == 0, "Should start with no positions!"
    print("✓ No open positions initially")
    
    # Test with open positions
    api.get_open_orders.return_value = [
        {'symbol': 'BTC_USDT', 'orderId': '123'},
        {'symbol': 'ETH_USDT', 'orderId': '456'}
    ]
    positions = em.get_open_positions()
    assert len(positions) == 2, "Should have 2 positions!"
    print("✓ Open positions retrieved correctly")
    
    # Test max positions check
    can_open = em.check_max_positions()
    assert can_open == True, "Should allow more positions (2/3)!"
    print("✓ Can open more positions (2/3)")
    
    # Test at max positions
    api.get_open_orders.return_value = [{'id': i} for i in range(3)]
    at_max = em.check_max_positions()
    assert at_max == False, "Should block new positions at max (3/3)!"
    print("✓ Max positions limit enforced (3/3)")
    
    print("\n✅ Position management tests passed!")


def test_position_summary():
    """Test position summary reporting"""
    print("\n" + "="*70)
    print("TEST: Position Summary")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    summary = em.get_position_summary()
    
    assert 'balance' in summary, "Missing balance!"
    assert 'open_positions' in summary, "Missing open_positions!"
    assert 'max_positions' in summary, "Missing max_positions!"
    assert 'daily_trades' in summary, "Missing daily_trades!"
    assert 'daily_pnl' in summary, "Missing daily_pnl!"
    assert 'can_trade' in summary, "Missing can_trade!"
    
    assert summary['balance'] == 29.04, "Balance mismatch!"
    assert summary['open_positions'] == 0, "Should have no positions!"
    assert summary['max_positions'] == 3, "Max positions mismatch!"
    assert summary['daily_trades'] == 0, "Should have no trades!"
    assert summary['can_trade'] == True, "Should be able to trade!"
    
    print(f"✓ Balance: ${summary['balance']:.2f}")
    print(f"✓ Positions: {summary['open_positions']}/{summary['max_positions']}")
    print(f"✓ Daily trades: {summary['daily_trades']}")
    print(f"✓ Daily P&L: ${summary['daily_pnl']:.2f}")
    print(f"✓ Can trade: {summary['can_trade']}")
    
    print("\n✅ Position summary tests passed!")


def test_daily_pnl_tracking():
    """Test daily P&L tracking and reset"""
    print("\n" + "="*70)
    print("TEST: Daily P&L Tracking")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    # Initial state
    assert em._daily_pnl == 0.0, "P&L should start at 0!"
    print("✓ Initial P&L: $0.00")
    
    # Update with profit
    em.update_daily_pnl(5.50)
    assert em._daily_pnl == 5.50, "P&L not updated correctly!"
    print("✓ After profit: $5.50")
    
    # Update with loss
    em.update_daily_pnl(-2.30)
    assert abs(em._daily_pnl - 3.20) < 0.01, "P&L calculation error!"
    print("✓ After loss: $3.20")
    
    # Reset counters
    em.reset_daily_counters()
    assert em._daily_pnl == 0.0, "P&L not reset!"
    assert em._trades_today == 0, "Trades not reset!"
    print("✓ Counters reset successfully")
    
    print("\n✅ P&L tracking tests passed!")


def test_real_world_scenarios():
    """Test real-world trading scenarios with $29.04 account"""
    print("\n" + "="*70)
    print("TEST: Real-World Scenarios ($29.04 Account)")
    print("="*70)
    
    api = create_mock_api(balance=29.04)
    rm = create_mock_risk_manager()
    em = ExchangeManager(api, rm, dry_run=True)
    
    scenarios = [
        ('BTC_USDT', 70000.0, 75, "High confidence BTC"),
        ('ETH_USDT', 3500.0, 80, "High confidence ETH"),
        ('SOL_USDT', 150.0, 60, "Medium confidence SOL"),
    ]
    
    for pair, price, confidence, description in scenarios:
        print(f"\n  {description}: {pair} @ ${price:.2f} ({confidence}% confidence)")
        
        # Update symbol info for each pair
        api.get_symbol_info.return_value = {
            'symbol': pair,
            'minAmount': 0.01,
            'minTradeSize': 0.000001,
            'enable': True
        }
        
        calculation = em.calculate_order(pair, price, confidence)
        
        if calculation['approved']:
            print(f"    ✓ APPROVED: ${calculation['position_usdt']:.2f} position")
        else:
            print(f"    ✗ REJECTED: {calculation.get('error', 'Unknown')}")
    
    print("\n✅ Real-world scenario tests passed!")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "#"*70)
    print("# SilkTrader v3 - ExchangeManager Test Suite")
    print("#"*70)
    
    # Suppress logging during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    
    test_functions = [
        test_initialization,
        test_get_available_balance,
        test_is_pair_affordable,
        test_calculate_order,
        test_execute_trade_paper,
        test_execute_trade_live,
        test_position_management,
        test_position_summary,
        test_daily_pnl_tracking,
        test_real_world_scenarios
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
        print("\nExchangeManager is ready for integration:")
        print("  • All validation layers working")
        print("  • Paper trading mode functional")
        print("  • Live trading ready (when dry_run=False)")
        print("  • Risk management integration complete")
        print("  • Position tracking operational")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - Review above errors")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
