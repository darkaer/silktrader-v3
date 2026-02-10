#!/usr/bin/env python3
import requests
import hmac
import hashlib
import time
import json
import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class PionexAPI:
    """Pionex API client with authentication, retry logic, and comprehensive error handling"""
    
    def __init__(self, credentials_path: str = 'credentials/pionex.json'):
        with open(credentials_path, 'r') as f:
            self.config = json.load(f)
        
        # Support both old and new field names for backward compatibility
        self.api_key = self.config.get('api_key') or self.config.get('PIONEX_API_KEY')
        self.api_secret = self.config.get('api_secret') or self.config.get('PIONEX_API_SECRET')
        self.base_url = self.config.get('base_url', 'https://api.pionex.com')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Missing API credentials: 'api_key' and 'api_secret' required in config")
        
        self.session = requests.Session()
        
        # Setup logging
        self.logger = logging.getLogger('PionexAPI')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.05  # 50ms between requests
        
        # Symbol info caching (hybrid: in-memory + file)
        self._symbol_info_cache = {}
        self._cache_file = 'cache/symbol_info.json'
        self._cache_ttl = 86400  # 24 hours in seconds
        self._load_cache_from_file()
    
    def _load_cache_from_file(self):
        """Load cached symbol info from JSON file on startup"""
        if not os.path.exists(self._cache_file):
            self.logger.debug(f"No cache file found at {self._cache_file}")
            return
        
        try:
            with open(self._cache_file, 'r') as f:
                cached = json.load(f)
                now = time.time()
                loaded_count = 0
                
                for symbol, data in cached.items():
                    age = now - data.get('timestamp', 0)
                    if age < self._cache_ttl:
                        self._symbol_info_cache[symbol] = data
                        loaded_count += 1
                
                if loaded_count > 0:
                    self.logger.info(f"Loaded {loaded_count} cached symbol(s) from {self._cache_file}")
                    
        except Exception as e:
            self.logger.warning(f"Failed to load symbol cache: {e}")
    
    def _save_cache_to_file(self):
        """Save symbol cache to JSON file for persistence across restarts"""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._cache_file, 'w') as f:
                json.dump(self._symbol_info_cache, f, indent=2)
            self.logger.debug(f"Saved {len(self._symbol_info_cache)} symbol(s) to cache")
        except Exception as e:
            self.logger.warning(f"Failed to save symbol cache: {e}")
    
    def get_symbol_info(self, symbol: str, force_refresh: bool = False) -> Dict:
        now = time.time()
        
        if not force_refresh and symbol in self._symbol_info_cache:
            data = self._symbol_info_cache[symbol]
            age = now - data.get('timestamp', 0)
            if age < self._cache_ttl:
                return data
        
        params = {'symbol': symbol}
        result = self._request('GET', '/api/v1/common/symbols', params=params)
        
        if not result or not result.get('result'):
            return {'error': 'Failed to fetch symbol info'}
        
        symbols = result.get('data', {}).get('symbols', [])
        if not symbols:
            return {'error': f'Symbol {symbol} not found'}
        
        s = symbols[0]
        info = {
            'symbol': s.get('symbol', symbol),
            'minAmount': float(s.get('minAmount', 0)),
            'minTradeSize': float(s.get('minTradeSize', 0)),
            'maxTradeSize': float(s.get('maxTradeSize', 0)),
            'enable': bool(s.get('enable', True)),
            'timestamp': now
        }
        
        self._symbol_info_cache[symbol] = info
        self._save_cache_to_file()
        
        return info
    
    def _generate_signature(self, method: str, path: str, query: str = '', body: str = '') -> str:
        if query:
            message = f"{method}{path}?{query}{body}"
        else:
            message = f"{method}{path}{body}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                 data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        timestamp = str(int(time.time() * 1000))
        if params is None:
            params = {}
        params['timestamp'] = timestamp
        
        sorted_params = sorted(params.items())
        query = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Serialize JSON body for signature (compact format, no spaces)
        body = json.dumps(data, separators=(',', ':')) if data else ''
        
        signature = self._generate_signature(method, endpoint, query, body)
        
        headers = {
            'PIONEX-KEY': self.api_key,
            'PIONEX-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # FIXED: Send the exact body string used for signature calculation
                # instead of letting requests re-serialize it with different formatting
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=body if body else None,  # Send pre-serialized JSON string
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if not result.get('result', True):
                    error_msg = result.get('message', 'Unknown error')
                    error_code = result.get('code', 'UNKNOWN')
                    self.logger.warning(f"API error: {error_code} - {error_msg}")
                    return result
                
                return result
                
            except requests.exceptions.Timeout as e:
                last_error = e
                self.logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}): {endpoint}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if e.response else None
                
                if status_code and 400 <= status_code < 500 and status_code != 429:
                    self.logger.error(f"Client error {status_code}: {e}")
                    return {'error': str(e), 'status_code': status_code}
                
                self.logger.warning(f"HTTP error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                self.logger.warning(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        self.logger.error(f"All retry attempts failed for {endpoint}: {last_error}")
        return {'error': str(last_error), 'retries_exhausted': True}
    
    # ==================== Market Data Methods ====================
    
    def get_symbols(self, quote: str = 'USDT', min_volume: float = 0) -> List[str]:
        result = self._request('GET', '/api/v1/common/symbols', params={})
        
        if 'data' not in result:
            self.logger.warning(f"Unexpected response format: {result}")
            return []
        
        symbols = []
        
        if 'symbols' in result['data']:
            symbol_list = result['data']['symbols']
        else:
            symbol_list = result['data']
        
        for symbol in symbol_list:
            symbol_name = symbol.get('symbol', symbol.get('name', ''))
            
            if quote in symbol_name:
                status = symbol.get('status', symbol.get('symbolStatus', 'TRADING'))
                if status in ['TRADING', 'ENABLED', 'ONLINE']:
                    symbols.append(symbol_name)
        
        self.logger.info(f"Found {len(symbols)} {quote} pairs")
        return symbols
    
    def get_klines(self, symbol: str, interval: str = '15M', limit: int = 100) -> List[Dict]:
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        result = self._request('GET', '/api/v1/market/klines', params=params)
        
        if 'data' not in result or 'klines' not in result['data']:
            if 'error' not in result:
                self.logger.debug(f"No klines data for {symbol}: {result}")
            return []
        
        klines = []
        for k in result['data']['klines']:
            klines.append({
                'timestamp': k['time'],
                'open': float(k['open']),
                'high': float(k['high']),
                'low': float(k['low']),
                'close': float(k['close']),
                'volume': float(k['volume'])
            })
        
        return klines
    
    def get_24h_ticker(self, symbol: Optional[str] = None) -> Dict:
        params = {}
        if symbol:
            params['symbol'] = symbol
        result = self._request('GET', '/api/v1/market/tickers', params=params)
        
        if 'data' not in result or 'tickers' not in result['data']:
            return {}
        
        if symbol:
            for ticker in result['data']['tickers']:
                if ticker['symbol'] == symbol:
                    return ticker
            return {}
        
        return result['data']
    
    # ==================== Account Methods ====================
    
    def get_account_balance(self) -> Dict:
        result = self._request('GET', '/api/v1/account/balances', params={})
        if 'data' in result:
            return result['data']
        elif 'error' in result:
            self.logger.error(f"Failed to fetch balance: {result['error']}")
        return {}
    
    def get_balance_by_currency(self, currency: str = 'USDT') -> Tuple[float, float, float]:
        balances = self.get_account_balance()
        
        if not balances or 'balances' not in balances:
            self.logger.warning(f"No balance data available")
            return (0.0, 0.0, 0.0)
        
        for balance in balances['balances']:
            if balance.get('coin', '').upper() == currency.upper():
                free = float(balance.get('free', 0))
                frozen = float(balance.get('frozen', 0))
                total = free + frozen
                self.logger.info(f"{currency} balance: {free:.2f} free, {frozen:.2f} frozen, {total:.2f} total")
                return (free, frozen, total)
        
        self.logger.warning(f"Currency {currency} not found in balances")
        return (0.0, 0.0, 0.0)
    
    # ==================== Trading Methods ====================
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                    price: Optional[float] = None, client_order_id: Optional[str] = None) -> Dict:
        """Place order with correct parameters for each order type
        
        Pionex API requires different parameters based on order type:
        - Market SELL: use 'size' (quantity in base currency, e.g., tokens to sell)
        - Market BUY: use 'amount' (total in quote currency, e.g., USDT to spend)
        - Limit orders: use 'size' + 'price' (both BUY and SELL)
        
        Args:
            symbol: Trading pair (e.g., 'BTC_USDT')
            side: 'BUY' or 'SELL'
            order_type: 'MARKET' or 'LIMIT'
            quantity: For SELL - tokens to sell; For BUY - USDT to spend (market) or tokens to buy (limit)
            price: Price for limit orders (required for LIMIT, ignored for MARKET)
            client_order_id: Optional client order identifier
        
        Returns:
            API response dict with order details or error
        """
        data = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper()
        }
        
        # FIXED: Use correct parameter based on order type and side
        if order_type.upper() == 'MARKET':
            if side.upper() == 'SELL':
                # Market sell: use 'size' (quantity of tokens to sell)
                data['size'] = str(quantity)
            else:  # BUY
                # Market buy: use 'amount' (total USDT to spend)
                data['amount'] = str(quantity)
        else:  # LIMIT
            # Limit orders always use 'size' + 'price' for both BUY and SELL
            data['size'] = str(quantity)
            if price:
                data['price'] = str(price)
        
        if client_order_id:
            data['clientOrderId'] = client_order_id
        
        self.logger.info(f"Placing order: {side} {quantity} {symbol} @ {price or 'MARKET'}")
        result = self._request('POST', '/api/v1/trade/order', data=data)
        
        if 'data' in result and 'orderId' in result['data']:
            self.logger.info(f"Order placed successfully: {result['data']['orderId']}")
        elif 'error' in result:
            self.logger.error(f"Order placement failed: {result['error']}")
        
        return result
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        result = self._request('GET', '/api/v1/trade/order', params=params)
        
        if 'data' in result:
            order = result['data']
            status = order.get('status', 'UNKNOWN')
            filled = float(order.get('executedQty', 0))
            total = float(order.get('origQty', 0))
            self.logger.debug(f"Order {order_id} status: {status}, filled: {filled}/{total}")
            return order
        
        return {}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders for account or specific symbol
        
        Returns:
            List of open order dicts. Empty list if no orders.
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        result = self._request('GET', '/api/v1/trade/openOrders', params=params)
        
        # Handle both response formats
        data = result.get('data', [])
        
        # If data is a dict with 'orders' key, extract the orders array
        if isinstance(data, dict) and 'orders' in data:
            orders = data['orders']
        # If data is already a list, use it directly
        elif isinstance(data, list):
            orders = data
        else:
            orders = []
        
        # Log accurate count
        if orders:
            self.logger.info(f"Found {len(orders)} open order(s)" + (f" for {symbol}" if symbol else ""))
        
        return orders
    
    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100, 
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        result = self._request('GET', '/api/v1/trade/allOrders', params=params)
        
        orders = result.get('data', [])
        if orders:
            self.logger.info(f"Retrieved {len(orders)} historical orders")
        return orders
    
    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 100,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        result = self._request('GET', '/api/v1/trade/fills', params=params)
        
        trades = result.get('data', [])
        if trades:
            self.logger.info(f"Retrieved {len(trades)} trades")
        return trades
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        data = {
            'symbol': symbol,
            'orderId': order_id
        }
        self.logger.info(f"Cancelling order {order_id} on {symbol}")
        result = self._request('DELETE', '/api/v1/trade/order', data=data)
        
        if result.get('result', False):
            self.logger.info(f"Order {order_id} cancelled successfully")
        elif 'error' in result:
            self.logger.error(f"Failed to cancel order {order_id}: {result['error']}")
        
        return result
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        data = {}
        if symbol:
            data['symbol'] = symbol
            
        self.logger.warning(f"Cancelling all orders" + (f" for {symbol}" if symbol else ""))
        result = self._request('DELETE', '/api/v1/trade/openOrders', data=data)
        
        if result.get('result', False):
            self.logger.info("All orders cancelled successfully")
        
        return result
    
    # ==================== Helper Methods ====================
    
    def wait_for_order_fill(self, symbol: str, order_id: str, timeout: int = 30, 
                           poll_interval: float = 1.0) -> Tuple[bool, Dict]:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            order = self.get_order_status(symbol, order_id)
            
            if not order:
                self.logger.error(f"Could not fetch status for order {order_id}")
                return (False, {})
            
            status = order.get('status', '').upper()
            
            if status == 'FILLED':
                self.logger.info(f"Order {order_id} filled successfully")
                return (True, order)
            elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                self.logger.warning(f"Order {order_id} ended with status: {status}")
                return (False, order)
            elif status in ['NEW', 'PARTIALLY_FILLED']:
                time.sleep(poll_interval)
            else:
                self.logger.warning(f"Unknown order status: {status}")
                time.sleep(poll_interval)
        
        self.logger.warning(f"Order {order_id} timeout after {timeout}s")
        return (False, self.get_order_status(symbol, order_id))
    
    def is_symbol_tradeable(self, symbol: str) -> bool:
        symbols_data = self._request('GET', '/api/v1/common/symbols', params={})
        
        if 'data' not in symbols_data:
            return False
        
        symbol_list = symbols_data['data'].get('symbols', symbols_data['data'])
        
        for s in symbol_list:
            if s.get('symbol') == symbol:
                status = s.get('status', s.get('symbolStatus', 'UNKNOWN'))
                is_tradeable = status in ['TRADING', 'ENABLED', 'ONLINE']
                self.logger.debug(f"Symbol {symbol} status: {status}, tradeable: {is_tradeable}")
                return is_tradeable
        
        self.logger.debug(f"Symbol {symbol} not found in symbol list")
        return False
