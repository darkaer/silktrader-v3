import json
from datetime import datetime

class TradeLogger:
    def __init__(self, log_file='logs/trades.json'):
        self.log_file = log_file
    
    def log_trade(self, trade_data):
        """Log trade to JSON file"""
        with open(self.log_file, 'a') as f:
            trade_data['timestamp'] = datetime.now().isoformat()
            f.write(json.dumps(trade_data) + '\n')
