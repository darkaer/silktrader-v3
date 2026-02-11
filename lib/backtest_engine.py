#!/usr/bin/env python3
"""
SilkTrader v3 - Backtesting Engine
Replay historical market data to validate trading strategies
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import json

sys.path.append('lib')
sys.path.append('skills/silktrader-trader/scripts')

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup
from risk_manager import RiskManager


class BacktestEngine:
    """Backtesting engine with realistic trade simulation"""
    
    def __init__(self, config_path='credentials/pionex.json', 
                 initial_balance=1000.0,
                 trading_fee_percent=0.05,
                 slippage_percent=0.1):
        """Initialize backtest engine
        
        Args:
            config_path: Path to configuration file
            initial_balance: Starting USDT balance
            trading_fee_percent: Trading fee per trade (Pionex: 0.05%)
            slippage_percent: Average slippage (0.1% realistic)
        """
        self.api = PionexAPI(config_path)
        self.risk_mgr = RiskManager(config_path)
        
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Trading parameters
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trading_fee = trading_fee_percent / 100
        self.slippage = slippage_percent / 100
        
        # Risk limits
        risk_limits = self.config.get('risk_limits', {})
        self.max_position_size = risk_limits.get('max_position_size_usdt', 500)
        self.max_positions = risk_limits.get('max_open_positions', 3)
        self.stop_loss_pct = risk_limits.get('stop_loss_percent', 3.0)
        self.take_profit_pct = risk_limits.get('take_profit_percent', 6.0)
        
        # Scanner config
        scanner_config = self.config.get('scanner_config', {})
        self.min_score = scanner_config.get('min_score', 5)
        self.timeframe = scanner_config.get('timeframe', '15M')
        
        # State tracking
        self.positions = []
        self.closed_trades = []
        self.daily_trades = {}
        self.current_date = None
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        
        print(f"\n{'='*70}")
        print(f"🔬 SilkTrader v3 - Backtesting Engine")
        print(f"{'='*70}")
        print(f"Initial Balance: ${initial_balance:.2f} USDT")
        print(f"Trading Fee: {trading_fee_percent}%")
        print(f"Slippage: {slippage_percent}%")
        print(f"Max Position Size: ${self.max_position_size:.2f}")
        print(f"Max Positions: {self.max_positions}")
        print(f"Stop Loss: {self.stop_loss_pct}%")
        print(f"Take Profit: {self.take_profit_pct}%")
        print(f"Min Scanner Score: {self.min_score}/7")
        print(f"Timeframe: {self.timeframe}")
        print(f"{'='*70}\n")
    
    def _get_klines_with_fallback(self, pair: str, timeframe: str) -> List[Dict]:
        """Get klines with progressive fallback on limit errors
        
        Args:
            pair: Trading pair
            timeframe: Candle timeframe
            
        Returns:
            List of klines in chronological order (oldest first), or empty list if all attempts fail
        """
        # Try progressively smaller limits if API rejects request
        limits_to_try = [500, 200, 100]
        
        for limit in limits_to_try:
            try:
                klines = self.api.get_klines(pair, timeframe, limit)
                if klines and len(klines) > 0:
                    # Pionex API returns klines in reverse order (newest first)
                    # Reverse them for chronological backtesting
                    klines.reverse()
                    return klines
            except Exception as e:
                # If it's not a limit error, stop trying
                error_str = str(e).lower()
                if 'limit' not in error_str and 'parameter' not in error_str:
                    break
                continue
        
        return []
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                               pair: str) -> float:
        """Calculate position size based on risk management
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            pair: Trading pair
            
        Returns:
            Position size in base currency (e.g., BTC quantity)
        """
        # Use tiered position sizing similar to live trading
        risk_per_trade = 0.02  # 2% risk per trade
        
        # Tiered sizing based on account balance
        if self.balance < 50:
            position_usdt = self.balance * 0.20  # 20% for small accounts
        elif self.balance < 200:
            position_usdt = self.balance * 0.15  # 15% for medium accounts
        else:
            position_usdt = self.balance * 0.10  # 10% for larger accounts
        
        # Cap at max position size
        position_usdt = min(position_usdt, self.max_position_size)
        
        # Calculate quantity
        quantity = position_usdt / entry_price
        
        return quantity
    
    def apply_trading_costs(self, price: float, quantity: float, 
                           side: str = 'BUY') -> Tuple[float, float]:
        """Apply realistic trading costs (fees + slippage)
        
        Args:
            price: Base price
            quantity: Trade quantity
            side: BUY or SELL
            
        Returns:
            Tuple of (actual_price, total_cost_usdt)
        """
        # Slippage: BUY pays more, SELL gets less
        if side == 'BUY':
            slippage_factor = 1 + self.slippage
        else:  # SELL
            slippage_factor = 1 - self.slippage
        
        actual_price = price * slippage_factor
        position_value = actual_price * quantity
        
        # Trading fee (both sides)
        fee = position_value * self.trading_fee
        
        # Total cost
        if side == 'BUY':
            total_cost = position_value + fee
        else:  # SELL
            total_cost = position_value - fee
        
        return actual_price, total_cost
    
    def open_position(self, pair: str, entry_price: float, 
                     score: int, indicators: Dict, 
                     timestamp: int) -> Optional[Dict]:
        """Open new position with risk management
        
        Args:
            pair: Trading pair
            entry_price: Entry price
            score: Scanner score
            indicators: Technical indicators
            timestamp: Entry timestamp (ms)
            
        Returns:
            Position dict if opened, None if rejected
        """
        # Check position limit
        if len(self.positions) >= self.max_positions:
            return None
        
        # Check if already in this pair
        if any(p['pair'] == pair for p in self.positions):
            return None
        
        # Calculate stop loss and take profit
        stop_loss = entry_price * (1 - self.stop_loss_pct / 100)
        take_profit = entry_price * (1 + self.take_profit_pct / 100)
        
        # Calculate position size
        quantity = self.calculate_position_size(entry_price, stop_loss, pair)
        
        # Apply trading costs
        actual_entry, total_cost = self.apply_trading_costs(
            entry_price, quantity, 'BUY'
        )
        
        # Check if we have enough balance
        if total_cost > self.balance:
            return None
        
        # Create position
        position = {
            'pair': pair,
            'entry_price': actual_entry,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_timestamp': timestamp,
            'entry_time': datetime.fromtimestamp(timestamp/1000).isoformat(),
            'score': score,
            'position_value': total_cost,
            'trailing_stop': stop_loss,
            'trailing_active': False,
            'highest_price': actual_entry
        }
        
        # Deduct from balance
        self.balance -= total_cost
        self.positions.append(position)
        
        return position
    
    def close_position(self, position: Dict, exit_price: float, 
                      reason: str, timestamp: int) -> Dict:
        """Close position and calculate P&L
        
        Args:
            position: Position dict
            exit_price: Exit price
            reason: Exit reason (STOP_LOSS, TAKE_PROFIT, etc.)
            timestamp: Exit timestamp (ms)
            
        Returns:
            Closed trade dict with P&L
        """
        # Apply trading costs for exit
        actual_exit, proceeds = self.apply_trading_costs(
            exit_price, position['quantity'], 'SELL'
        )
        
        # Calculate P&L
        pnl_usdt = proceeds - position['position_value']
        pnl_pct = (pnl_usdt / position['position_value']) * 100
        
        # Add proceeds to balance
        self.balance += proceeds
        
        # Calculate hold duration
        duration_seconds = (timestamp - position['entry_timestamp']) / 1000
        duration_hours = duration_seconds / 3600
        
        # Create closed trade record
        trade = {
            'pair': position['pair'],
            'entry_price': position['entry_price'],
            'exit_price': actual_exit,
            'quantity': position['quantity'],
            'entry_time': position['entry_time'],
            'exit_time': datetime.fromtimestamp(timestamp/1000).isoformat(),
            'hold_duration_hours': duration_hours,
            'pnl_usdt': pnl_usdt,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'score': position['score'],
            'position_value': position['position_value']
        }
        
        # Update statistics
        self.total_trades += 1
        self.total_pnl += pnl_usdt
        
        if pnl_usdt > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Track daily trades
        trade_date = datetime.fromtimestamp(timestamp/1000).date().isoformat()
        if trade_date not in self.daily_trades:
            self.daily_trades[trade_date] = []
        self.daily_trades[trade_date].append(trade)
        
        # Update max drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        else:
            drawdown = (self.peak_balance - self.balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, drawdown)
        
        self.closed_trades.append(trade)
        self.positions.remove(position)
        
        return trade
    
    def update_trailing_stop(self, position: Dict, current_price: float):
        """Update trailing stop for position
        
        Args:
            position: Position dict
            current_price: Current market price
        """
        # Activation threshold (3% profit)
        activation_threshold = position['entry_price'] * 1.03
        
        # Track highest price
        if current_price > position['highest_price']:
            position['highest_price'] = current_price
        
        # Activate trailing stop if in profit
        if not position['trailing_active'] and current_price >= activation_threshold:
            position['trailing_active'] = True
            # Trail 1.5% below highest price
            position['trailing_stop'] = position['highest_price'] * 0.985
        
        # Update trailing stop if active
        elif position['trailing_active']:
            new_stop = position['highest_price'] * 0.985
            if new_stop > position['trailing_stop']:
                position['trailing_stop'] = new_stop
    
    def check_exits(self, current_candle: Dict) -> List[Dict]:
        """Check all positions for exit conditions
        
        Args:
            current_candle: Current OHLCV candle
            
        Returns:
            List of closed trade dicts
        """
        closed = []
        positions_to_close = []
        
        for position in self.positions:
            # Update trailing stop
            self.update_trailing_stop(position, current_candle['close'])
            
            # Check stop loss (use low of candle)
            if current_candle['low'] <= position['trailing_stop']:
                exit_price = position['trailing_stop']
                reason = 'TRAILING_STOP' if position['trailing_active'] else 'STOP_LOSS'
                positions_to_close.append((position, exit_price, reason))
            
            # Check take profit (use high of candle)
            elif current_candle['high'] >= position['take_profit']:
                exit_price = position['take_profit']
                positions_to_close.append((position, exit_price, 'TAKE_PROFIT'))
        
        # Close positions
        for position, exit_price, reason in positions_to_close:
            trade = self.close_position(
                position, exit_price, reason, current_candle['timestamp']
            )
            closed.append(trade)
        
        return closed
    
    def scan_for_opportunities(self, pair: str, klines: List[Dict]) -> Optional[Tuple[int, Dict]]:
        """Scan pair for trading opportunity
        
        Args:
            pair: Trading pair
            klines: List of OHLCV candles (at least 100)
            
        Returns:
            Tuple of (score, indicators) if opportunity found, None otherwise
        """
        try:
            # Need enough data for indicators
            if len(klines) < 50:
                return None
            
            # Calculate indicators
            indicators = calc_all_indicators(klines)
            score = score_setup(indicators)
            
            # Check if meets minimum score
            if score >= self.min_score:
                return (score, indicators)
            
        except Exception as e:
            # Silently skip errors
            pass
        
        return None
    
    def run_backtest(self, pairs: List[str], start_date: str, end_date: str,
                    scan_interval_hours: int = 1) -> Dict:
        """Run backtest on historical data
        
        Args:
            pairs: List of trading pairs to backtest
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            scan_interval_hours: Hours between scans (1 = scan every hour)
            
        Returns:
            Dict with backtest results and metrics
        """
        print(f"🚀 Starting backtest: {start_date} to {end_date}")
        print(f"   Pairs: {len(pairs)}")
        print(f"   Scan interval: Every {scan_interval_hours} hour(s)\n")
        
        # Convert dates to timestamps
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Calculate total time period
        total_days = (end_dt - start_dt).days
        
        # Download historical data for all pairs
        print("📊 Downloading historical data...")
        pair_data = {}
        failed_pairs = []
        
        for i, pair in enumerate(pairs, 1):
            print(f"   [{i}/{len(pairs)}] {pair}...", end=' ', flush=True)
            
            # Use fallback method for getting klines (returns in chronological order)
            klines = self._get_klines_with_fallback(pair, self.timeframe)
            
            if len(klines) >= 100:
                pair_data[pair] = klines
                print(f"✓ {len(klines)} candles")
            else:
                failed_pairs.append(pair)
                print(f"⚠️  Insufficient data")
            
            # Rate limiting
            time.sleep(0.1)
        
        print(f"\n✓ Loaded data for {len(pair_data)} pairs")
        if failed_pairs:
            print(f"⚠️  Failed to load: {', '.join(failed_pairs)}")
        print()
        
        if not pair_data:
            print("❌ No data available for backtest")
            print("\n💡 Tip: Try using major pairs instead:")
            print("   python backtest.py --quick-test 3d --pairs BTC_USDT,ETH_USDT,BNB_USDT,SOL_USDT\n")
            return {}
        
        # Find common time range across all pairs
        # Klines are now in chronological order: klines[0] = oldest, klines[-1] = newest
        earliest_time = max(klines[0]['timestamp'] for klines in pair_data.values())
        latest_time = min(klines[-1]['timestamp'] for klines in pair_data.values())
        
        print(f"📅 Data available from {datetime.fromtimestamp(earliest_time/1000)} to {datetime.fromtimestamp(latest_time/1000)}")
        
        # Convert timeframe to milliseconds
        timeframe_ms = self._timeframe_to_ms(self.timeframe)
        scan_interval_ms = scan_interval_hours * 60 * 60 * 1000
        
        # Main backtest loop
        current_time = earliest_time
        last_scan_time = earliest_time
        scan_count = 0
        
        print(f"\n{'='*70}")
        print(f"🔬 Running backtest simulation...")
        print(f"{'='*70}\n")
        
        while current_time <= latest_time:
            # Check if it's time to scan
            if current_time >= last_scan_time + scan_interval_ms:
                scan_count += 1
                
                # Progress update
                progress = ((current_time - earliest_time) / (latest_time - earliest_time)) * 100
                print(f"[{progress:.1f}%] {datetime.fromtimestamp(current_time/1000).strftime('%Y-%m-%d %H:%M')} | "
                      f"Balance: ${self.balance:.2f} | Positions: {len(self.positions)} | Trades: {self.total_trades}")
                
                # Scan all pairs for opportunities
                for pair, klines in pair_data.items():
                    # Get historical data up to current_time
                    historical = [k for k in klines if k['timestamp'] <= current_time]
                    
                    if len(historical) < 100:
                        continue
                    
                    # Use last 100 candles for analysis
                    recent_klines = historical[-100:]
                    
                    # Scan for opportunity
                    result = self.scan_for_opportunities(pair, recent_klines)
                    
                    if result:
                        score, indicators = result
                        
                        # Try to open position
                        position = self.open_position(
                            pair, 
                            indicators['price'],
                            score,
                            indicators,
                            current_time
                        )
                        
                        if position:
                            print(f"   🟢 ENTRY: {pair} @ ${position['entry_price']:.6f} | Score: {score}/7")
                
                last_scan_time = current_time
            
            # Check exits for all open positions
            for pair, klines in pair_data.items():
                if not any(p['pair'] == pair for p in self.positions):
                    continue
                
                # Get current candle
                current_candles = [k for k in klines if k['timestamp'] == current_time]
                
                if current_candles:
                    current_candle = current_candles[0]
                    
                    # Check exit conditions
                    closed_trades = self.check_exits(current_candle)
                    
                    for trade in closed_trades:
                        status = "✅" if trade['pnl_usdt'] > 0 else "❌"
                        print(f"   {status} EXIT: {trade['pair']} | P&L: ${trade['pnl_usdt']:+.2f} ({trade['pnl_pct']:+.2f}%) | {trade['reason']}")
            
            # Advance time
            current_time += timeframe_ms
        
        # Close any remaining positions at end of backtest
        print(f"\n📊 Backtest complete, closing remaining positions...")
        for position in list(self.positions):
            # Get final price from last candle
            final_klines = [k for k in pair_data[position['pair']] if k['timestamp'] <= latest_time]
            if final_klines:
                final_price = final_klines[-1]['close']
                trade = self.close_position(position, final_price, 'BACKTEST_END', latest_time)
                status = "✅" if trade['pnl_usdt'] > 0 else "❌"
                print(f"   {status} {trade['pair']} | P&L: ${trade['pnl_usdt']:+.2f} ({trade['pnl_pct']:+.2f}%)")
        
        # Calculate final metrics
        results = self._calculate_metrics()
        results['scans_performed'] = scan_count
        
        return results
    
    def _timeframe_to_ms(self, timeframe: str) -> int:
        """Convert timeframe string to milliseconds"""
        units = {
            'M': 60 * 1000,
            'H': 60 * 60 * 1000,
            'D': 24 * 60 * 60 * 1000
        }
        
        if timeframe[-1] in units:
            value = int(timeframe[:-1])
            return value * units[timeframe[-1]]
        
        return 15 * 60 * 1000  # Default 15M
    
    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        # Win rate
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        # Average P&L
        avg_pnl = self.total_pnl / self.total_trades if self.total_trades > 0 else 0
        
        # Win/Loss averages
        winning_pnls = [t['pnl_usdt'] for t in self.closed_trades if t['pnl_usdt'] > 0]
        losing_pnls = [t['pnl_usdt'] for t in self.closed_trades if t['pnl_usdt'] < 0]
        
        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
        
        # Profit factor
        total_wins = sum(winning_pnls)
        total_losses = abs(sum(losing_pnls))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Return on investment
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        # Average hold time
        avg_hold_hours = sum(t['hold_duration_hours'] for t in self.closed_trades) / len(self.closed_trades) if self.closed_trades else 0
        
        # Best/worst trades
        best_trade = max(self.closed_trades, key=lambda t: t['pnl_usdt']) if self.closed_trades else None
        worst_trade = min(self.closed_trades, key=lambda t: t['pnl_usdt']) if self.closed_trades else None
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_pnl': self.total_pnl,
            'roi_percent': roi,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown * 100,
            'avg_hold_hours': avg_hold_hours,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'daily_trades': self.daily_trades,
            'all_trades': self.closed_trades
        }
    
    def print_results(self, results: Dict):
        """Print backtest results in formatted way"""
        print(f"\n{'='*70}")
        print(f"📈 BACKTEST RESULTS")
        print(f"{'='*70}")
        
        print(f"\n💰 Financial Performance:")
        print(f"   Initial Balance: ${results['initial_balance']:.2f}")
        print(f"   Final Balance: ${results['final_balance']:.2f}")
        print(f"   Total P&L: ${results['total_pnl']:+.2f}")
        print(f"   ROI: {results['roi_percent']:+.2f}%")
        print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")
        
        print(f"\n📊 Trading Statistics:")
        print(f"   Total Trades: {results['total_trades']}")
        print(f"   Winning Trades: {results['winning_trades']}")
        print(f"   Losing Trades: {results['losing_trades']}")
        print(f"   Win Rate: {results['win_rate']:.2f}%")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        
        print(f"\n💵 P&L Breakdown:")
        print(f"   Average P&L: ${results['avg_pnl']:+.2f}")
        print(f"   Average Win: ${results['avg_win']:+.2f}")
        print(f"   Average Loss: ${results['avg_loss']:+.2f}")
        
        print(f"\n⏱️  Timing:")
        print(f"   Average Hold Time: {results['avg_hold_hours']:.1f} hours")
        
        if results['best_trade']:
            print(f"\n🏆 Best Trade:")
            bt = results['best_trade']
            print(f"   {bt['pair']}: ${bt['pnl_usdt']:+.2f} ({bt['pnl_pct']:+.2f}%)")
        
        if results['worst_trade']:
            print(f"\n💔 Worst Trade:")
            wt = results['worst_trade']
            print(f"   {wt['pair']}: ${wt['pnl_usdt']:+.2f} ({wt['pnl_pct']:+.2f}%)")
        
        # Daily breakdown
        if results['daily_trades']:
            print(f"\n📅 Daily Performance:")
            for date in sorted(results['daily_trades'].keys()):
                trades = results['daily_trades'][date]
                daily_pnl = sum(t['pnl_usdt'] for t in trades)
                wins = len([t for t in trades if t['pnl_usdt'] > 0])
                losses = len([t for t in trades if t['pnl_usdt'] < 0])
                print(f"   {date}: {len(trades)} trades, ${daily_pnl:+.2f} ({wins}W/{losses}L)")
        
        print(f"\n{'='*70}\n")
