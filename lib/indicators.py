#!/usr/bin/env python3
import pandas as pd
import numpy as np
import talib
import json
import logging

# Setup logging
logger = logging.getLogger('Indicators')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

def klines_to_dataframe(klines: list) -> pd.DataFrame:
    """Convert klines list to pandas DataFrame"""
    df = pd.DataFrame(klines)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def calc_all_indicators(klines: list, config_path: str = 'credentials/pionex.json') -> dict:
    """Calculate all technical indicators using TA-Lib
    
    Args:
        klines: List of kline dicts with OHLCV data
        config_path: Path to config file with indicator params
        
    Returns:
        Dict of calculated indicators
        
    Raises:
        ValueError: If insufficient data or calculation fails
    """
    
    # Load indicator parameters
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        params = config['indicator_params']
    except Exception as e:
        raise ValueError(f"Failed to load config: {e}")
    
    # Check minimum data requirements
    # MACD slow period (26) + signal period (9) = 35 minimum
    min_candles = max(params['macd_slow'] + params['macd_signal'], params['ema_slow'], 50)
    if len(klines) < min_candles:
        raise ValueError(f"Insufficient data: {len(klines)} candles, need {min_candles}+")
    
    try:
        df = klines_to_dataframe(klines)
    except Exception as e:
        raise ValueError(f"Failed to convert klines to dataframe: {e}")
    
    # Convert to numpy arrays for TA-Lib
    try:
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)
    except Exception as e:
        raise ValueError(f"Failed to extract OHLCV arrays: {e}")
    
    # Calculate indicators with error handling
    try:
        # Calculate EMAs
        ema_fast = talib.EMA(close, timeperiod=params['ema_fast'])
        ema_slow = talib.EMA(close, timeperiod=params['ema_slow'])
        
        # Calculate RSI
        rsi = talib.RSI(close, timeperiod=params['rsi_period'])
        
        # Calculate MACD
        macd, macd_signal, macd_hist = talib.MACD(
            close,
            fastperiod=params['macd_fast'],
            slowperiod=params['macd_slow'],
            signalperiod=params['macd_signal']
        )
        
        # Calculate ATR
        atr = talib.ATR(high, low, close, timeperiod=params['atr_period'])
        
        # Calculate Volume MA
        volume_ma = talib.SMA(volume, timeperiod=params['volume_ma_period'])
        
    except Exception as e:
        raise ValueError(f"TA-Lib calculation failed: {e}")
    
    # Validate results (check for NaN in critical values)
    def safe_float(arr, idx, name):
        """Safely extract float from array, checking for NaN"""
        try:
            val = float(arr[idx])
            if np.isnan(val) or np.isinf(val):
                raise ValueError(f"{name} is NaN/inf")
            return val
        except (IndexError, TypeError) as e:
            raise ValueError(f"Failed to extract {name}: {e}")
    
    try:
        # Extract latest values
        price = safe_float(close, -1, 'price')
        ema_fast_val = safe_float(ema_fast, -1, 'ema_fast')
        ema_slow_val = safe_float(ema_slow, -1, 'ema_slow')
        rsi_val = safe_float(rsi, -1, 'rsi')
        rsi_prev_val = safe_float(rsi, -2, 'rsi_prev')
        macd_val = safe_float(macd, -1, 'macd')
        macd_signal_val = safe_float(macd_signal, -1, 'macd_signal')
        macd_hist_val = safe_float(macd_hist, -1, 'macd_hist')
        atr_val = safe_float(atr, -1, 'atr')
        volume_val = safe_float(volume, -1, 'volume')
        volume_ma_val = safe_float(volume_ma, -1, 'volume_ma')
        
        # Calculate volume ratio (protect against division by zero)
        if volume_ma_val > 0:
            volume_ratio = volume_val / volume_ma_val
        else:
            volume_ratio = 1.0
            
    except ValueError as e:
        raise ValueError(f"Indicator validation failed: {e}")
    
    # Return validated indicators
    return {
        'price': price,
        'ema_fast': ema_fast_val,
        'ema_slow': ema_slow_val,
        'rsi': rsi_val,
        'rsi_prev': rsi_prev_val,
        'macd': macd_val,
        'macd_signal': macd_signal_val,
        'macd_hist': macd_hist_val,
        'atr': atr_val,
        'volume': volume_val,
        'volume_ma': volume_ma_val,
        'volume_ratio': volume_ratio,
        'timestamp': str(df.index[-1])
    }

def score_setup(indicators: dict) -> int:
    """Score trading setup from 0-7"""
    score = 0
    
    # Trend alignment (0-2 points)
    if indicators['price'] > indicators['ema_fast'] > indicators['ema_slow']:
        score += 2  # Strong bullish trend
    elif indicators['price'] > indicators['ema_fast']:
        score += 1  # Weak bullish trend
    
    # RSI momentum (0-1 point)
    if 30 < indicators['rsi'] < 70 and indicators['rsi'] > indicators['rsi_prev']:
        score += 1  # Healthy momentum building
    
    # MACD confirmation (0-2 points)
    if indicators['macd_hist'] > 0:
        score += 1
        if indicators['macd'] > indicators['macd_signal']:
            score += 1  # Strong momentum
    
    # Volume confirmation (0-1 point)
    if indicators['volume_ratio'] > 1.2:
        score += 1  # Above-average volume
    
    # Volatility check (0-1 point)
    atr_pct = (indicators['atr'] / indicators['price']) * 100
    if 1.0 < atr_pct < 5.0:
        score += 1  # Moderate volatility (tradeable)
    
    return score

def format_indicators_for_llm(pair: str, indicators: dict, score: int) -> str:
    """Format indicator data for LLM consumption"""
    trend = "BULLISH" if indicators['price'] > indicators['ema_fast'] > indicators['ema_slow'] else \
            "WEAK BULLISH" if indicators['price'] > indicators['ema_fast'] else \
            "BEARISH"
    
    rsi_direction = "↑" if indicators['rsi'] > indicators['rsi_prev'] else "↓"
    macd_state = "bullish cross" if indicators['macd'] > indicators['macd_signal'] and indicators['macd_hist'] > 0 else \
                 "bearish cross" if indicators['macd'] < indicators['macd_signal'] else "neutral"
    
    volume_state = f"+{int((indicators['volume_ratio'] - 1) * 100)}%" if indicators['volume_ratio'] > 1 else \
                   f"{int((indicators['volume_ratio'] - 1) * 100)}%"
    
    atr_pct = (indicators['atr'] / indicators['price']) * 100
    
    return f"""{pair} (Score: {score}/7) - {trend}
Price: {indicators['price']:.4f} | EMA21: {indicators['ema_fast']:.4f} | EMA50: {indicators['ema_slow']:.4f}
RSI: {indicators['rsi']:.1f} {rsi_direction} | MACD: {macd_state} ({indicators['macd_hist']:.4f})
Volume: {volume_state} vs avg | ATR: {atr_pct:.2f}%"""
