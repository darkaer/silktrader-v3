#!/usr/bin/env python3
import pandas as pd
import numpy as np
import talib
import json

def klines_to_dataframe(klines: list) -> pd.DataFrame:
    """Convert klines list to pandas DataFrame"""
    df = pd.DataFrame(klines)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def calc_all_indicators(klines: list, config_path: str = 'credentials/pionex.json') -> dict:
    """Calculate all technical indicators using TA-Lib"""
    
    # Load indicator parameters
    with open(config_path, 'r') as f:
        config = json.load(f)
    params = config['indicator_params']
    
    df = klines_to_dataframe(klines)
    
    # Convert to numpy arrays for TA-Lib
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values
    
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
    volume_ratio = volume[-1] / volume_ma[-1] if volume_ma[-1] != 0 else 1.0
    
    # Get latest and previous values
    return {
        'price': float(close[-1]),
        'ema_fast': float(ema_fast[-1]),
        'ema_slow': float(ema_slow[-1]),
        'rsi': float(rsi[-1]),
        'rsi_prev': float(rsi[-2]),
        'macd': float(macd[-1]),
        'macd_signal': float(macd_signal[-1]),
        'macd_hist': float(macd_hist[-1]),
        'atr': float(atr[-1]),
        'volume': float(volume[-1]),
        'volume_ma': float(volume_ma[-1]),
        'volume_ratio': float(volume_ratio),
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
