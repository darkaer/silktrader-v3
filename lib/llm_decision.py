#!/usr/bin/env python3
import requests
import json
import os

class LLMDecisionEngine:
    """LLM-powered trading decision engine using OpenRouter"""
    
    def __init__(self, api_key: str = None, model: str = "arcee-ai/trinity-large-preview:free"):
        """Initialize LLM decision engine
        
        Args:
            api_key: OpenRouter API key (uses OPENROUTER_API_KEY env var if not provided)
            model: Model identifier (default: arcee-ai/trinity-large-preview:free)
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def analyze_opportunity(self, pair: str, indicators: dict, score: int) -> dict:
        """Get LLM trading decision for a specific opportunity
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            indicators: Dict of technical indicators
            score: Setup quality score (0-7)
            
        Returns:
            Dict with decision:
            {
                'action': 'BUY' | 'SELL' | 'WAIT',
                'confidence': int (1-10),
                'reasoning': str
            }
        """
        prompt = self._format_analysis_prompt(pair, indicators, score)
        
        try:
            response = self._call_openrouter(prompt)
            decision = self._parse_decision(response)
            return decision
        except Exception as e:
            return {'action': 'WAIT', 'confidence': 0, 'reasoning': f'Error: {e}'}
    
    def _format_analysis_prompt(self, pair: str, indicators: dict, score: int) -> str:
        """Format compact prompt for LLM analysis
        
        Args:
            pair: Trading pair
            indicators: Technical indicators dict
            score: Setup quality score (0-7)
            
        Returns:
            Formatted prompt string
        """
        trend = "BULLISH" if indicators['price'] > indicators['ema_fast'] > indicators['ema_slow'] else "BEARISH"
        rsi_state = "overbought" if indicators['rsi'] > 70 else "oversold" if indicators['rsi'] < 30 else "neutral"
        
        prompt = f"""You are a crypto trading analyst. Analyze this setup and provide a trading decision.

PAIR: {pair}
SCORE: {score}/7
TREND: {trend}

TECHNICALS:
- Price: ${indicators['price']:.6f}
- EMA21: ${indicators['ema_fast']:.6f} | EMA50: ${indicators['ema_slow']:.6f}
- RSI: {indicators['rsi']:.1f} ({rsi_state})
- MACD Histogram: {indicators['macd_hist']:.6f}
- Volume vs Avg: {((indicators['volume_ratio'] - 1) * 100):.0f}%
- ATR: {((indicators['atr'] / indicators['price']) * 100):.2f}%

Provide your analysis in this exact format:
ACTION: [BUY/SELL/WAIT]
CONFIDENCE: [1-10]
REASONING: [One sentence explaining why]

Consider:
1. Is the trend strong and confirmed?
2. Is RSI in a healthy range (not extreme)?
3. Is volume supporting the move?
4. Is volatility acceptable for entry?"""

        return prompt
    
    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API
        
        Args:
            prompt: User prompt
            
        Returns:
            Model response text
            
        Raises:
            requests.HTTPError: If API call fails
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 200,
            'temperature': 0.3
        }
        
        response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
    
    def _parse_decision(self, response: str) -> dict:
        """Parse LLM response into structured decision
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Dict with action, confidence, reasoning
        """
        lines = response.strip().split('\n')
        decision = {
            'action': 'WAIT',
            'confidence': 5,
            'reasoning': 'Unable to parse response'
        }
        
        for line in lines:
            if line.startswith('ACTION:'):
                action = line.split(':', 1)[1].strip().upper()
                if action in ['BUY', 'SELL', 'WAIT']:
                    decision['action'] = action
            
            elif line.startswith('CONFIDENCE:'):
                try:
                    conf = int(line.split(':', 1)[1].strip().split()[0])
                    decision['confidence'] = max(1, min(10, conf))
                except:
                    pass
            
            elif line.startswith('REASONING:'):
                decision['reasoning'] = line.split(':', 1)[1].strip()
        
        return decision
