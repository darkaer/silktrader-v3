#!/usr/bin/env python3
"""
Market Scanner for SilkTrader v3
Scans all USDT pairs on Pionex and scores trading opportunities
"""
import sys
import time
import json
import logging
from typing import List, Dict, Tuple
from datetime import datetime

# Add project paths
sys.path.insert(0, '.')
sys.path.append('skills/silktrader-trader/scripts')

from lib.pionex_api import PionexAPI
from lib.indicators import calc_all_indicators, score_setup
from lib.exchange_manager import ExchangeManager
from risk_manager import RiskManager


class MarketScanner:
    """Scans crypto markets for high-probability trading setups"""
    
    def __init__(self, api: PionexAPI, exchange_manager: ExchangeManager = None, config_path: str = 'credentials/pionex.json'):
        """Initialize market scanner
        
        Args:
            api: Initialized PionexAPI client
            exchange_manager: Optional ExchangeManager for affordability checks
            config_path: Path to config file (for timeframe setting)
        """
        self.api = api
        self.exchange_manager = exchange_manager
        
        # Load config for scanner settings
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Get timeframe from config
        self.timeframe = self.config.get('scanner_config', {}).get('timeframe', '15M')
        
        # Setup logging
        self.logger = logging.getLogger('MarketScanner')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.logger.info(f"MarketScanner initialized (timeframe={self.timeframe})")
    
    def get_usdt_pairs(self) -> List[str]:
        """Get all tradeable USDT pairs from Pionex
        
        Returns:
            List of symbol names (e.g., ['BTC_USDT', 'ETH_USDT', ...])
        """
        try:
            # API returns List[str] of enabled USDT pairs (already filtered)
            symbols = self.api.get_symbols(quote='USDT')
            
            self.logger.info(f"Found {len(symbols)} tradeable USDT pairs")
            return sorted(symbols)
            
        except Exception as e:
            self.logger.error(f"Failed to get USDT pairs: {e}")
            return []
    
    def fetch_klines(self, pair: str, interval: str = None, limit: int = 100) -> List[Dict]:
        """Fetch kline data for a pair
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            interval: Timeframe ('1M', '5M', '15M', '30M', '60M', '4H', '8H', '12H', '1D') - uses self.timeframe if None
            limit: Number of candles to fetch (max 500)
            
        Returns:
            List of kline dicts or empty list on error
        """
        if interval is None:
            interval = self.timeframe
            
        try:
            klines = self.api.get_klines(pair, interval, limit)
            return klines
        except Exception as e:
            self.logger.debug(f"Failed to fetch klines for {pair}: {e}")
            return []
    
    def score_opportunity(self, pair: str, indicators: Dict) -> Tuple[int, str]:
        """Enhanced scoring system (0-100 scale)
        
        Args:
            pair: Trading pair
            indicators: Dict of calculated indicators
            
        Returns:
            Tuple of (score, reasoning)
        """
        # Base score from indicators.py (0-7)
        base_score = score_setup(indicators)
        
        # Convert to 0-100 scale with bonuses
        score = base_score * 10  # 0-70 base
        reasons = []
        
        # Trend strength bonus (0-15 points)
        ema_diff_pct = ((indicators['ema_fast'] - indicators['ema_slow']) / indicators['ema_slow']) * 100
        if ema_diff_pct > 2.0:
            score += 15
            reasons.append("Strong uptrend (EMA spread >2%)")
        elif ema_diff_pct > 1.0:
            score += 10
            reasons.append("Moderate uptrend")
        elif ema_diff_pct > 0.5:
            score += 5
            reasons.append("Weak uptrend")
        
        # RSI position bonus (0-10 points)
        rsi = indicators['rsi']
        if 40 < rsi < 60:
            score += 10
            reasons.append("RSI neutral zone (ideal entry)")
        elif 30 < rsi < 40:
            score += 7
            reasons.append("RSI oversold recovery")
        elif 60 < rsi < 70:
            score += 5
            reasons.append("RSI in strength zone")
        
        # Volume surge bonus (0-5 points)
        vol_ratio = indicators['volume_ratio']
        if vol_ratio > 2.0:
            score += 5
            reasons.append(f"Volume surge +{int((vol_ratio-1)*100)}%")
        elif vol_ratio > 1.5:
            score += 3
            reasons.append(f"Above-avg volume +{int((vol_ratio-1)*100)}%")
        
        # Cap at 100
        score = min(100, score)
        
        reasoning = " | ".join(reasons) if reasons else "Standard setup"
        return score, reasoning
    
    def scan_markets(self, top_n: int = 5, min_score: int = 50, 
                    check_affordability: bool = True) -> List[Dict]:
        """Scan all markets and return top opportunities
        
        Args:
            top_n: Number of top opportunities to return
            min_score: Minimum score threshold (0-100)
            check_affordability: Filter by account affordability
            
        Returns:
            List of opportunity dicts sorted by score (highest first)
        """
        self.logger.info(f"Starting market scan (top_n={top_n}, min_score={min_score})")
        start_time = time.time()
        
        # Get all USDT pairs
        pairs = self.get_usdt_pairs()
        if not pairs:
            self.logger.error("No pairs found to scan")
            return []
        
        self.logger.info(f"Scanning {len(pairs)} pairs...")
        
        opportunities = []
        scanned = 0
        errors = 0
        
        # Track filtering reasons
        filter_stats = {
            'no_klines': 0,
            'insufficient_data': 0,
            'indicator_error': 0,
            'low_score': 0,
            'not_affordable': 0
        }
        
        # Get balance once for affordability checks
        balance = 0.0
        if check_affordability and self.exchange_manager:
            balance = self.exchange_manager.get_available_balance()
            self.logger.info(f"Available balance for affordability checks: ${balance:.2f}")
        
        for i, pair in enumerate(pairs, 1):
            try:
                # Fetch klines using configured timeframe
                klines = self.fetch_klines(pair, limit=100)
                
                if not klines:
                    filter_stats['no_klines'] += 1
                    continue
                
                if len(klines) < 50:
                    # Not enough data
                    filter_stats['insufficient_data'] += 1
                    self.logger.debug(f"{pair}: Only {len(klines)} candles, need 50+")
                    continue
                
                # Calculate indicators
                try:
                    indicators = calc_all_indicators(klines)
                except Exception as ind_err:
                    filter_stats['indicator_error'] += 1
                    self.logger.debug(f"{pair}: Indicator calculation failed: {ind_err}")
                    continue
                
                # Score opportunity
                score, reasoning = self.score_opportunity(pair, indicators)
                
                # Log score for debugging (even if filtered)
                if i <= 10 or score >= min_score:
                    self.logger.debug(f"{pair}: Score {score}/100 - {reasoning[:50]}")
                
                # Filter by minimum score
                if score < min_score:
                    filter_stats['low_score'] += 1
                    continue
                
                # Check affordability
                affordable = True
                if check_affordability and self.exchange_manager and balance > 0:
                    affordable = self.exchange_manager.is_pair_affordable(
                        pair, 
                        indicators['price'], 
                        balance
                    )
                    
                    if not affordable:
                        filter_stats['not_affordable'] += 1
                        self.logger.debug(f"{pair}: Not affordable at ${indicators['price']:.6f} with ${balance:.2f} balance")
                        continue
                
                # Create opportunity dict
                opportunity = {
                    'pair': pair,
                    'score': score,
                    'confidence': score,  # Alias for ExchangeManager compatibility
                    'entry_price': indicators['price'],
                    'indicators': indicators,
                    'reasoning': reasoning,
                    'affordable': affordable,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                opportunities.append(opportunity)
                scanned += 1
                
                self.logger.info(f"✅ {pair}: Score {score}/100 - {reasoning[:50]}")
                
                # Log progress every 50 pairs
                if i % 50 == 0:
                    self.logger.info(
                        f"Progress: {i}/{len(pairs)} pairs scanned, "
                        f"{len(opportunities)} opportunities found"
                    )
                
            except Exception as e:
                errors += 1
                self.logger.debug(f"Error scanning {pair}: {e}")
                continue
        
        # Sort by score (highest first)
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # Get top N
        top_opportunities = opportunities[:top_n]
        
        # Calculate stats
        elapsed = time.time() - start_time
        
        # Log detailed filtering stats
        self.logger.info(
            f"Scan complete: {scanned}/{len(pairs)} pairs analyzed, "
            f"{len(opportunities)} passed filters, "
            f"returning top {len(top_opportunities)}, "
            f"{errors} errors, "
            f"took {elapsed:.1f}s"
        )
        
        self.logger.info(
            f"Filter breakdown: "
            f"no_klines={filter_stats['no_klines']}, "
            f"insufficient_data={filter_stats['insufficient_data']}, "
            f"indicator_error={filter_stats['indicator_error']}, "
            f"low_score={filter_stats['low_score']}, "
            f"not_affordable={filter_stats['not_affordable']}"
        )
        
        return top_opportunities
    
    def format_opportunity(self, opp: Dict) -> str:
        """Format opportunity for display
        
        Args:
            opp: Opportunity dict from scan_markets()
            
        Returns:
            Formatted string
        """
        ind = opp['indicators']
        
        trend = "BULLISH" if ind['price'] > ind['ema_fast'] > ind['ema_slow'] else \
                "WEAK BULL" if ind['price'] > ind['ema_fast'] else "BEARISH"
        
        return f"""
────────────────────────────────────────────────────────────────
{opp['pair']} - Score: {opp['score']}/100 ({trend})
────────────────────────────────────────────────────────────────
Entry Price: ${ind['price']:.6f}
EMA Fast/Slow: ${ind['ema_fast']:.6f} / ${ind['ema_slow']:.6f}
RSI: {ind['rsi']:.1f} (prev: {ind['rsi_prev']:.1f})
MACD: {ind['macd']:.6f} | Signal: {ind['macd_signal']:.6f} | Hist: {ind['macd_hist']:.6f}
Volume: {ind['volume']:.2f} ({ind['volume_ratio']:.2f}x average)
ATR: {ind['atr']:.6f} ({(ind['atr']/ind['price']*100):.2f}% of price)
Affordable: {'✅ YES' if opp['affordable'] else '❌ NO'}
Reasoning: {opp['reasoning']}
Timestamp: {opp['timestamp']}
"""


if __name__ == '__main__':
    """Test market scanner"""
    import argparse
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='SilkTrader v3 Market Scanner')
    parser.add_argument('--top-n', type=int, default=5, help='Number of top opportunities to return')
    parser.add_argument('--min-score', type=int, default=50, help='Minimum score threshold (0-100)')
    parser.add_argument('--no-affordability', action='store_true', help='Skip affordability checks')
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("SilkTrader v3 - Market Scanner Test")
    print("="*80)
    
    try:
        # Initialize components
        api = PionexAPI('credentials/pionex.json')
        
        # Initialize exchange manager for affordability checks (unless disabled)
        exchange_manager = None
        if not args.no_affordability:
            risk_manager = RiskManager('credentials/pionex.json')
            exchange_manager = ExchangeManager(api, risk_manager, dry_run=True)
        
        # Initialize scanner
        scanner = MarketScanner(api, exchange_manager)
        
        # Scan markets
        print(f"\nScanning markets (top {args.top_n}, min score {args.min_score})...\n")
        opportunities = scanner.scan_markets(
            top_n=args.top_n,
            min_score=args.min_score,
            check_affordability=not args.no_affordability
        )
        
        # Display results
        if opportunities:
            print(f"\n{'='*80}")
            print(f"TOP {len(opportunities)} OPPORTUNITIES")
            print(f"{'='*80}")
            
            for i, opp in enumerate(opportunities, 1):
                print(scanner.format_opportunity(opp))
        else:
            print("\n⚠️  No opportunities found matching criteria")
            print(f"   - Minimum score: {args.min_score}/100")
            print(f"   - Affordability checks: {'enabled' if not args.no_affordability else 'disabled'}")
        
        print("\n" + "="*80)
        print("Scan Complete")
        print("="*80)
        
    except FileNotFoundError:
        print("\n❌ ERROR: credentials/pionex.json not found!")
        print("Please create it from credentials/pionex.json.example")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
