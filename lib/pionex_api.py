#!/usr/bin/env python3
import requests
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class PionexAPI:
    """Pionex API client with authentication, retry logic, and comprehensive error handling"""
    
    def __init__(self, credentials_path: str = 'credentials/pionex.json'):
        with open(credentials_path, 'r') as f:
            self.config = json.load(f)
        
        self.api_key = self.config['PIONEX_API_KEY']
        self.api_secret = self.config['PIONEX_API_SECRET']
        self.base_url = self.config['base_url']
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
        
    def _generate_signature(self, method: str, path: str, query: str = '', body: str = '') -> str:
        \"\"\"Generate Pionex API signature according to official spec
        
        Format: METHOD + PATH + ? + SORTED_QUERY (if query exists) + BODY (if POST/DELETE)
        
        See: https://pionex-doc.gitbook.io/apidocs/restful/general/authentication
        \"\"\"
        # Build the message to sign
        if query:
            message = f\"{method}{path}?{query}{body}\"
        else:
            message = f\"{method}{path}{body}\"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _rate_limit(self):
        \"\"\"Enforce rate limiting between requests\"\"\"
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                 data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        \"\"\"Make authenticated request to Pionex API with retry logic
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            max_retries: Maximum number of retry attempts
            
        Returns:
            API response as dictionary
        \"\"\"
        self._rate_limit()
        
        url = f\"{self.base_url}{endpoint}\"
        
        # Add timestamp to query params for authentication
        timestamp = str(int(time.time() * 1000))
        if params is None:
            params = {}
        params['timestamp'] = timestamp
        
        # Sort parameters by key for signature (required by Pionex)
        sorted_params = sorted(params.items())
        query = '&'.join([f\"{k}={v}\" for k, v in sorted_params])
        
        # Build body string for POST/DELETE
        body = json.dumps(data) if data else ''
        
        # Generate signature
        signature = self._generate_signature(method, endpoint, query, body)
        
        headers = {
            'PIONEX-KEY': self.api_key,
            'PIONEX-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                # Check for API-level errors
                if not result.get('result', True):
                    error_msg = result.get('message', 'Unknown error')
                    error_code = result.get('code', 'UNKNOWN')
                    self.logger.warning(f\"API error: {error_code} - {error_msg}\")
                    return result
                
                return result
                
            except requests.exceptions.Timeout as e:
                last_error = e
                self.logger.warning(f\"Request timeout (attempt {attempt + 1}/{max_retries}): {endpoint}\")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if e.response else None
                
                # Don't retry on 4xx client errors (except 429 rate limit)
                if status_code and 400 <= status_code < 500 and status_code != 429:
                    self.logger.error(f\"Client error {status_code}: {e}\")
                    return {'error': str(e), 'status_code': status_code}
                
                self.logger.warning(f\"HTTP error (attempt {attempt + 1}/{max_retries}): {e}\")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                self.logger.warning(f\"Request error (attempt {attempt + 1}/{max_retries}): {e}\")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # All retries failed
        self.logger.error(f\"All retry attempts failed for {endpoint}: {last_error}\")
        return {'error': str(last_error), 'retries_exhausted': True}
    
    # ==================== Market Data Methods ====================
    
    def get_symbols(self, quote: str = 'USDT', min_volume: float = 0) -> List[str]:
        \"\"\"Get all trading pairs
        
        Args:
            quote: Quote currency to filter by (e.g., 'USDT')
            min_volume: Minimum 24h volume filter (not implemented yet)
            
        Returns:
            List of symbol names
        \"\"\"
        result = self._request('GET', '/api/v1/common/symbols', params={})
        
        if 'data' not in result:
            self.logger.warning(f\"Unexpected response format: {result}\")
            return []
        
        symbols = []
        
        # Handle different response structures
        if 'symbols' in result['data']:
            symbol_list = result['data']['symbols']
        else:
            symbol_list = result['data']
        
        for symbol in symbol_list:
            # Get symbol name (could be 'symbol' or 'name' field)
            symbol_name = symbol.get('symbol', symbol.get('name', ''))
            
            # Check if it matches our quote currency
            if quote in symbol_name:
                # Check status if field exists, otherwise assume it's tradeable
                status = symbol.get('status', symbol.get('symbolStatus', 'TRADING'))
                if status in ['TRADING', 'ENABLED', 'ONLINE']:
                    symbols.append(symbol_name)
        
        self.logger.info(f\"Found {len(symbols)} {quote} pairs\")
        return symbols
    
    def get_klines(self, symbol: str, interval: str = '15M', limit: int = 100) -> List[Dict]:
        \"\"\"Get OHLCV candlestick data
        
        Args:
            symbol: Trading pair (e.g., 'BTC_USDT')
            interval: Timeframe (1M, 5M, 15M, 30M, 60M, 4H, 8H, 12H, 1D)
            limit: Number of candles to fetch
            
        Returns:
            List of kline dictionaries with OHLCV data
        \"\"\"
        params = {
            'symbol': symbol,
            'interval': interval.upper(),
            'limit': limit
        }
        result = self._request('GET', '/api/v1/market/klines', params=params)
        
        if 'data' not in result or 'klines' not in result['data']:
            if 'error' not in result:
                self.logger.debug(f\"No klines data for {symbol}: {result}\")
            return []
        
        # Convert to structured format
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
        \"\"\"Get 24-hour price statistics
        
        Args:
            symbol: Trading pair (optional, returns all if not specified)
            
        Returns:
            Ticker data dictionary
        \"\"\"
        params = {}
        if symbol:
            params['symbol'] = symbol
        result = self._request('GET', '/api/v1/market/tickers', params=params)
        
        if 'data' not in result or 'tickers' not in result['data']:
            return {}
        
        # If specific symbol requested, return first match
        if symbol:
            for ticker in result['data']['tickers']:
                if ticker['symbol'] == symbol:
                    return ticker
            return {}
        
        return result['data']
    
    # ==================== Account Methods ====================
    
    def get_account_balance(self) -> Dict:
        \"\"\"Get account balance with all currencies
        
        Returns:
            Dictionary with balance data for all currencies
        \"\"\"
        result = self._request('GET', '/api/v1/account/balances', params={})
        if 'data' in result:
            return result['data']
        elif 'error' in result:
            self.logger.error(f\"Failed to fetch balance: {result['error']}\")
        return {}
    
    def get_balance_by_currency(self, currency: str = 'USDT') -> Tuple[float, float, float]:
        \"\"\"Get balance for a specific currency
        
        Args:
            currency: Currency code (e.g., 'USDT', 'BTC')
            
        Returns:
            Tuple of (free, frozen, total) balance
        \"\"\"
        balances = self.get_account_balance()
        
        if not balances or 'balances' not in balances:
            self.logger.warning(f\"No balance data available\")
            return (0.0, 0.0, 0.0)
        
        for balance in balances['balances']:
            if balance.get('coin', '').upper() == currency.upper():
                free = float(balance.get('free', 0))
                frozen = float(balance.get('frozen', 0))  # Pionex uses 'frozen' not 'locked'
                total = free + frozen
                self.logger.info(f\"{currency} balance: {free:.2f} free, {frozen:.2f} frozen, {total:.2f} total\")
                return (free, frozen, total)
        
        self.logger.warning(f\"Currency {currency} not found in balances\")
        return (0.0, 0.0, 0.0)
    
    # ==================== Trading Methods ====================
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                    price: Optional[float] = None, client_order_id: Optional[str] = None) -> Dict:
        \"\"\"Place a new order
        
        Args:
            symbol: Trading pair (e.g., 'BTC_USDT')
            side: 'BUY' or 'SELL'
            order_type: 'LIMIT' or 'MARKET'
            quantity: Order quantity in base currency
            price: Limit price (required for LIMIT orders)
            client_order_id: Optional custom order ID for tracking
            
        Returns:
            Order result with orderId and status
        \"\"\"
        data = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'amount': str(quantity)
        }
        
        if price and order_type.upper() == 'LIMIT':
            data['price'] = str(price)
        
        if client_order_id:
            data['clientOrderId'] = client_order_id
        
        self.logger.info(f\"Placing order: {side} {quantity} {symbol} @ {price or 'MARKET'}\")
        result = self._request('POST', '/api/v1/trade/order', data=data)
        
        if 'data' in result and 'orderId' in result['data']:
            self.logger.info(f\"Order placed successfully: {result['data']['orderId']}\")
        elif 'error' in result:
            self.logger.error(f\"Order placement failed: {result['error']}\")
        
        return result
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        \"\"\"Get status of a specific order
        
        Args:
            symbol: Trading pair
            order_id: Order ID to query
            
        Returns:
            Order details including status, filled amount, etc.
        \"\"\"
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
            self.logger.debug(f\"Order {order_id} status: {status}, filled: {filled}/{total}\")
            return order
        
        return {}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        \"\"\"Get all open orders
        
        Args:
            symbol: Filter by trading pair (optional)
            
        Returns:
            List of open order dictionaries
        \"\"\"
        params = {}
        if symbol:
            params['symbol'] = symbol
        result = self._request('GET', '/api/v1/trade/openOrders', params=params)
        
        orders = result.get('data', [])
        if orders:
            self.logger.info(f\"Found {len(orders)} open orders\" + (f\" for {symbol}\" if symbol else \"\"))
        return orders
    
    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100, 
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        \"\"\"Get historical orders (both open and closed)
        
        Args:
            symbol: Filter by trading pair (optional)
            limit: Maximum number of orders to return
            start_time: Start timestamp in milliseconds (optional)
            end_time: End timestamp in milliseconds (optional)
            
        Returns:
            List of historical order dictionaries
        \"\"\"
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
            self.logger.info(f\"Retrieved {len(orders)} historical orders\")
        return orders
    
    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 100,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        \"\"\"Get trade history (actual fills/executions)
        
        Args:
            symbol: Filter by trading pair (optional)
            limit: Maximum number of trades to return
            start_time: Start timestamp in milliseconds (optional)
            end_time: End timestamp in milliseconds (optional)
            
        Returns:
            List of trade dictionaries with fill prices and quantities
        \"\"\"
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        # Use correct Pionex endpoint for fills
        result = self._request('GET', '/api/v1/trade/fills', params=params)
        
        trades = result.get('data', [])
        if trades:
            self.logger.info(f\"Retrieved {len(trades)} trades\")
        return trades
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        \"\"\"Cancel an open order
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
            
        Returns:
            Cancellation result
        \"\"\"
        data = {
            'symbol': symbol,
            'orderId': order_id
        }
        self.logger.info(f\"Cancelling order {order_id} on {symbol}\")
        result = self._request('DELETE', '/api/v1/trade/order', data=data)
        
        if result.get('result', False):
            self.logger.info(f\"Order {order_id} cancelled successfully\")
        elif 'error' in result:
            self.logger.error(f\"Failed to cancel order {order_id}: {result['error']}\")
        
        return result
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        \"\"\"Cancel all open orders
        
        Args:
            symbol: Filter by trading pair (optional, cancels all if not specified)
            
        Returns:
            Cancellation result
        \"\"\"
        data = {}
        if symbol:
            data['symbol'] = symbol
            
        self.logger.warning(f\"Cancelling all orders\" + (f\" for {symbol}\" if symbol else \"\"))
        result = self._request('DELETE', '/api/v1/trade/openOrders', data=data)
        
        if result.get('result', False):
            self.logger.info(\"All orders cancelled successfully\")
        
        return result
    
    # ==================== Helper Methods ====================
    
    def wait_for_order_fill(self, symbol: str, order_id: str, timeout: int = 30, 
                           poll_interval: float = 1.0) -> Tuple[bool, Dict]:
        \"\"\"Wait for an order to fill (or fail)
        
        Args:
            symbol: Trading pair
            order_id: Order ID to monitor
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Tuple of (success, order_data)
        \"\"\"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            order = self.get_order_status(symbol, order_id)
            
            if not order:
                self.logger.error(f\"Could not fetch status for order {order_id}\")
                return (False, {})
            
            status = order.get('status', '').upper()
            
            if status == 'FILLED':
                self.logger.info(f\"Order {order_id} filled successfully\")
                return (True, order)
            elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                self.logger.warning(f\"Order {order_id} ended with status: {status}\")
                return (False, order)
            elif status in ['NEW', 'PARTIALLY_FILLED']:
                time.sleep(poll_interval)
            else:
                self.logger.warning(f\"Unknown order status: {status}\")
                time.sleep(poll_interval)
        
        self.logger.warning(f\"Order {order_id} timeout after {timeout}s\")
        return (False, self.get_order_status(symbol, order_id))
    
    def is_symbol_tradeable(self, symbol: str) -> bool:
        \"\"\"Check if a trading pair is currently tradeable
        
        Args:
            symbol: Trading pair to check
            
        Returns:
            True if tradeable, False otherwise
        \"\"\"
        symbols_data = self._request('GET', '/api/v1/common/symbols', params={})
        
        if 'data' not in symbols_data:
            return False
        
        symbol_list = symbols_data['data'].get('symbols', symbols_data['data'])
        
        for s in symbol_list:
            if s.get('symbol') == symbol:
                status = s.get('status', s.get('symbolStatus', 'UNKNOWN'))
                is_tradeable = status in ['TRADING', 'ENABLED', 'ONLINE']
                self.logger.debug(f\"Symbol {symbol} status: {status}, tradeable: {is_tradeable}\")
                return is_tradeable
        
        self.logger.debug(f\"Symbol {symbol} not found in symbol list\")
        return False
