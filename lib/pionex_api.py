#!/usr/bin/env python3
import requests
import hmac
import hashlib
import time
import json
from typing import Dict, List, Optional
from datetime import datetime

class PionexAPI:
    """Pionex API client with authentication and rate limiting"""
    
    def __init__(self, credentials_path: str = 'credentials/pionex.json'):
        with open(credentials_path, 'r') as f:
            self.config = json.load(f)
        
        self.api_key = self.config['PIONEX_API_KEY']
        self.api_secret = self.config['PIONEX_API_SECRET']
        self.base_url = self.config['base_url']
        self.session = requests.Session()
        
    def _generate_signature(self, method: str, path: str, query: str = '', body: str = '') -> tuple:
        """Generate Pionex API signature"""
        timestamp = str(int(time.time() * 1000))
        message = f"{method}{path}{query}{timestamp}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return timestamp, signature
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Pionex API"""
        url = f"{self.base_url}{endpoint}"
        query = '&'.join([f"{k}={v}" for k, v in (params or {}).items()])
        body = json.dumps(data) if data else ''
        
        timestamp, signature = self._generate_signature(method, endpoint, query, body)
        
        headers = {
            'PIONEX-KEY': self.api_key,
            'PIONEX-SIGNATURE': signature,
            'PIONEX-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        
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
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return {'error': str(e)}
    
    def get_symbols(self, quote: str = 'USDT', min_volume: float = 0) -> List[str]:
        """Get all trading pairs"""
        result = self._request('GET', '/api/v1/common/symbols')
        
        if 'data' not in result:
            print(f"API Response: {result}")
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
        
        return symbols
    
    def get_klines(self, symbol: str, interval: str = '15M', limit: int = 100) -> List[Dict]:
        """Get OHLCV candlestick data
        
        Intervals: 1M, 5M, 15M, 30M, 60M, 4H, 8H, 12H, 1D
        """
        params = {
            'symbol': symbol,
            'interval': interval.upper(),
            'limit': limit
        }
        result = self._request('GET', '/api/v1/market/klines', params=params)
        
        if 'data' not in result or 'klines' not in result['data']:
            print(f"Klines error: {result}")
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
    
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        result = self._request('GET', '/api/v1/account/balances')
        return result.get('data', {})
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict:
        """Place a new order"""
        data = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'amount': str(quantity)
        }
        
        if price and order_type.upper() == 'LIMIT':
            data['price'] = str(price)
        
        result = self._request('POST', '/api/v1/trade/order', data=data)
        return result
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {'symbol': symbol} if symbol else {}
        result = self._request('GET', '/api/v1/trade/openOrders', params=params)
        return result.get('data', [])
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an order"""
        data = {
            'symbol': symbol,
            'orderId': order_id
        }
        result = self._request('DELETE', '/api/v1/trade/order', data=data)
        return result
    
    def get_24h_ticker(self, symbol: Optional[str] = None) -> Dict:
        """Get 24-hour price statistics"""
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
