#!/usr/bin/env python3
import sys
sys.path.append('lib')
import os

from pionex_api import PionexAPI
from indicators import calc_all_indicators, score_setup
from llm_decision import LLMDecisionEngine

# Set your OpenRouter API key
# Option 1: Set environment variable
# export OPENROUTER_API_KEY="your-key-here"
# Option 2: Pass directly (less secure)
llm = LLMDecisionEngine(api_key=os.getenv('OPENROUTER_API_KEY'))

# Get a test opportunity
api = PionexAPI()
klines = api.get_klines('ACE_USDT', '15M', 100)
indicators = calc_all_indicators(klines)
score = score_setup(indicators)

print(f"Testing LLM decision for ACE_USDT (Score: {score}/7)\n")

# Get LLM decision
decision = llm.analyze_opportunity('ACE_USDT', indicators, score)

print("=" * 60)
print("LLM DECISION:")
print("=" * 60)
print(f"Action: {decision['action']}")
print(f"Confidence: {decision['confidence']}/10")
print(f"Reasoning: {decision['reasoning']}")
print("=" * 60)
