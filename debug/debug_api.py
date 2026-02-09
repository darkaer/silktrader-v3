#!/usr/bin/env python3
import sys
sys.path.append('lib')
from pionex_api import PionexAPI
import json

api = PionexAPI()
result = api._request('GET', '/api/v1/common/symbols')

print("API Response Structure:")
print(json.dumps(result, indent=2))

if 'data' in result and result['data']:
    if isinstance(result['data'], list):
        print("\nFirst symbol example:")
        print(json.dumps(result['data'][0], indent=2))
    elif 'symbols' in result['data']:
        print("\nFirst symbol example:")
        print(json.dumps(result['data']['symbols'][0], indent=2))
