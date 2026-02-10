#!/usr/bin/env python3
"""
SilkTrader v3 - Database Module
SQLite-based persistent storage for historical data, trades, and analytics
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import threading


class TradingDatabase:
    """SQLite database for trading bot historical data and analytics"""
    
    # Schema version for migrations
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str = 'data/silktrader.db'):
        """Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections (SQLite is not thread-safe by default)
        self._local = threading.local()
        
        # Initialize schema
        self._initialize_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row  # Enable dict-like access
        return self._local.connection
    
    def _initialize_schema(self):
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Schema version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Market data (OHLCV candles) for backtesting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pair, timeframe, timestamp)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_market_data_pair_time "
            "ON market_data(pair, timeframe, timestamp DESC)"
        )
        
        # Trade execution history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                pair TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                position_usdt REAL NOT NULL,
                exit_price REAL,
                realized_pnl REAL,
                pnl_percent REAL,
                stop_loss REAL,
                take_profit REAL,
                confidence_score INTEGER,
                paper_trading BOOLEAN NOT NULL,
                status TEXT NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                hold_duration_seconds INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_pair_time "
            "ON trades(pair, entry_time DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_status "
            "ON trades(status, entry_time DESC)"
        )
        
        # Scanner results and opportunity scores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                pair TEXT NOT NULL,
                score INTEGER NOT NULL,
                price REAL NOT NULL,
                reasoning TEXT,
                indicators TEXT,
                affordable BOOLEAN NOT NULL,
                selected_for_trade BOOLEAN DEFAULT 0,
                scan_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_results_time "
            "ON scan_results(scan_time DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_results_pair "
            "ON scan_results(pair, scan_time DESC)"
        )
        
        # LLM decision history for audit and improvement
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                scanner_score INTEGER NOT NULL,
                action TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                reasoning TEXT NOT NULL,
                indicators TEXT,
                model_name TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                decision_time TIMESTAMP NOT NULL,
                executed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_decisions_time "
            "ON llm_decisions(decision_time DESC)"
        )
        
        # Position snapshots for tracking open trades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                pair TEXT NOT NULL,
                current_price REAL NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                unrealized_pnl REAL NOT NULL,
                pnl_percent REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                trailing_stop REAL,
                snapshot_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_position_snapshots_trade "
            "ON position_snapshots(trade_id, snapshot_time DESC)"
        )
        
        # Daily summary statistics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                trades_count INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                total_pnl REAL NOT NULL,
                win_rate REAL NOT NULL,
                avg_win REAL,
                avg_loss REAL,
                largest_win REAL,
                largest_loss REAL,
                total_volume REAL NOT NULL,
                scans_performed INTEGER NOT NULL,
                opportunities_found INTEGER NOT NULL,
                paper_trading BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_summary_date "
            "ON daily_summary(date DESC)"
        )
        
        # Check and update schema version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        current_version = result[0] if result[0] else 0
        
        if current_version < self.SCHEMA_VERSION:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (self.SCHEMA_VERSION,)
            )
        
        conn.commit()
    
    # ==================== MARKET DATA ====================
    
    def insert_candles(self, pair: str, timeframe: str, candles: List[Dict]) -> int:
        """Insert OHLCV candles for backtesting
        
        Args:
            pair: Trading pair (e.g., 'BTC_USDT')
            timeframe: Candle timeframe (e.g., '15M', '1H')
            candles: List of candle dicts with keys: timestamp, open, high, low, close, volume
            
        Returns:
            Number of candles inserted (duplicates skipped)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        inserted = 0
        for candle in candles:
            try:
                cursor.execute("""
                    INSERT INTO market_data (pair, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pair,
                    timeframe,
                    candle['timestamp'],
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume']
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate candle, skip
                pass
        
        conn.commit()
        return inserted
    
    def get_candles(self, pair: str, timeframe: str, 
                    start_time: Optional[int] = None,
                    end_time: Optional[int] = None,
                    limit: int = 1000) -> List[Dict]:
        """Get historical candles for backtesting
        
        Args:
            pair: Trading pair
            timeframe: Candle timeframe
            start_time: Unix timestamp (optional)
            end_time: Unix timestamp (optional)
            limit: Max number of candles to return
            
        Returns:
            List of candle dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM market_data WHERE pair = ? AND timeframe = ?"
        params = [pair, timeframe]
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== TRADES ====================
    
    def insert_trade(self, trade: Dict) -> int:
        """Insert new trade entry
        
        Args:
            trade: Trade dict with required fields
            
        Returns:
            Trade database ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (
                trade_id, pair, side, order_type, entry_price, quantity, position_usdt,
                stop_loss, take_profit, confidence_score, paper_trading, status, entry_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['trade_id'],
            trade['pair'],
            trade['side'],
            trade.get('order_type', 'MARKET'),
            trade['entry_price'],
            trade['quantity'],
            trade['position_usdt'],
            trade.get('stop_loss'),
            trade.get('take_profit'),
            trade.get('confidence_score'),
            trade['paper_trading'],
            trade.get('status', 'OPEN'),
            trade['entry_time']
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def update_trade_exit(self, trade_id: str, exit_data: Dict) -> bool:
        """Update trade with exit information
        
        Args:
            trade_id: Trade identifier
            exit_data: Dict with exit_price, exit_time, realized_pnl, etc.
            
        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate hold duration if both times provided
        hold_duration = None
        if 'exit_time' in exit_data and 'entry_time' in exit_data:
            exit_dt = datetime.fromisoformat(exit_data['exit_time'])
            entry_dt = datetime.fromisoformat(exit_data['entry_time'])
            hold_duration = int((exit_dt - entry_dt).total_seconds())
        
        cursor.execute("""
            UPDATE trades SET
                exit_price = ?,
                exit_time = ?,
                realized_pnl = ?,
                pnl_percent = ?,
                status = ?,
                hold_duration_seconds = ?
            WHERE trade_id = ?
        """, (
            exit_data.get('exit_price'),
            exit_data.get('exit_time'),
            exit_data.get('realized_pnl'),
            exit_data.get('pnl_percent'),
            exit_data.get('status', 'CLOSED'),
            hold_duration,
            trade_id
        ))
        
        conn.commit()
        return cursor.rowcount > 0
    
    def get_trades(self, pair: Optional[str] = None,
                   status: Optional[str] = None,
                   paper_trading: Optional[bool] = None,
                   start_date: Optional[str] = None,
                   limit: int = 100) -> List[Dict]:
        """Query trade history
        
        Args:
            pair: Filter by trading pair
            status: Filter by status (OPEN, CLOSED, etc.)
            paper_trading: Filter by paper/live mode
            start_date: Filter trades after this date (ISO format)
            limit: Max results to return
            
        Returns:
            List of trade dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if pair:
            query += " AND pair = ?"
            params.append(pair)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if paper_trading is not None:
            query += " AND paper_trading = ?"
            params.append(paper_trading)
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)
        
        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_trade_statistics(self, paper_trading: Optional[bool] = None,
                            start_date: Optional[str] = None) -> Dict:
        """Calculate trade performance statistics
        
        Args:
            paper_trading: Filter by paper/live mode
            start_date: Calculate stats from this date
            
        Returns:
            Dict with win_rate, avg_pnl, total_pnl, etc.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                AVG(realized_pnl) as avg_pnl,
                SUM(realized_pnl) as total_pnl,
                AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END) as avg_win,
                AVG(CASE WHEN realized_pnl < 0 THEN realized_pnl END) as avg_loss,
                MAX(realized_pnl) as largest_win,
                MIN(realized_pnl) as largest_loss,
                AVG(hold_duration_seconds) as avg_hold_seconds
            FROM trades
            WHERE status = 'CLOSED' AND realized_pnl IS NOT NULL
        """
        params = []
        
        if paper_trading is not None:
            query += " AND paper_trading = ?"
            params.append(paper_trading)
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        stats = dict(row) if row else {}
        
        # Calculate win rate
        if stats.get('total_trades', 0) > 0:
            stats['win_rate'] = (stats.get('winning_trades', 0) / stats['total_trades']) * 100
        else:
            stats['win_rate'] = 0.0
        
        return stats
    
    # ==================== SCANNER RESULTS ====================
    
    def insert_scan_results(self, scan_id: str, scan_time: str, results: List[Dict]) -> int:
        """Insert scanner opportunity results
        
        Args:
            scan_id: Unique identifier for this scan
            scan_time: ISO timestamp of scan
            results: List of opportunity dicts from scanner
            
        Returns:
            Number of results inserted
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for result in results:
            cursor.execute("""
                INSERT INTO scan_results (
                    scan_id, pair, score, price, reasoning, indicators,
                    affordable, scan_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                result['pair'],
                result['score'],
                result.get('entry_price', result['indicators']['price']),
                result.get('reasoning', ''),
                json.dumps(result['indicators']),
                result.get('affordable', True),
                scan_time
            ))
        
        conn.commit()
        return len(results)
    
    def get_scan_history(self, pair: Optional[str] = None,
                         min_score: int = 0,
                         limit: int = 100) -> List[Dict]:
        """Query historical scan results
        
        Args:
            pair: Filter by trading pair
            min_score: Minimum score threshold
            limit: Max results to return
            
        Returns:
            List of scan result dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM scan_results WHERE score >= ?"
        params = [min_score]
        
        if pair:
            query += " AND pair = ?"
            params.append(pair)
        
        query += " ORDER BY scan_time DESC, score DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            # Parse indicators JSON
            if result.get('indicators'):
                result['indicators'] = json.loads(result['indicators'])
            results.append(result)
        
        return results
    
    # ==================== LLM DECISIONS ====================
    
    def insert_llm_decision(self, decision: Dict) -> int:
        """Log LLM decision for audit trail
        
        Args:
            decision: Decision dict from LLM engine
            
        Returns:
            Decision database ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO llm_decisions (
                pair, scanner_score, action, confidence, reasoning,
                indicators, model_name, decision_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision['pair'],
            decision.get('scanner_score', 0),
            decision['action'],
            decision['confidence'],
            decision['reasoning'],
            json.dumps(decision.get('indicators', {})),
            decision.get('model', 'unknown'),
            decision.get('decision_time', datetime.now().isoformat())
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_llm_decisions(self, pair: Optional[str] = None,
                          action: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
        """Query LLM decision history
        
        Args:
            pair: Filter by trading pair
            action: Filter by action (BUY, WAIT)
            limit: Max results to return
            
        Returns:
            List of decision dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM llm_decisions WHERE 1=1"
        params = []
        
        if pair:
            query += " AND pair = ?"
            params.append(pair)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY decision_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        decisions = []
        for row in cursor.fetchall():
            decision = dict(row)
            if decision.get('indicators'):
                decision['indicators'] = json.loads(decision['indicators'])
            decisions.append(decision)
        
        return decisions
    
    # ==================== POSITION SNAPSHOTS ====================
    
    def insert_position_snapshot(self, snapshot: Dict) -> int:
        """Insert position state snapshot for tracking
        
        Args:
            snapshot: Position snapshot dict
            
        Returns:
            Snapshot database ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO position_snapshots (
                trade_id, pair, current_price, entry_price, quantity,
                unrealized_pnl, pnl_percent, stop_loss, take_profit,
                trailing_stop, snapshot_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot['trade_id'],
            snapshot['pair'],
            snapshot['current_price'],
            snapshot['entry_price'],
            snapshot['quantity'],
            snapshot['unrealized_pnl'],
            snapshot['pnl_percent'],
            snapshot.get('stop_loss'),
            snapshot.get('take_profit'),
            snapshot.get('trailing_stop'),
            snapshot.get('snapshot_time', datetime.now().isoformat())
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_position_history(self, trade_id: str) -> List[Dict]:
        """Get position snapshot history for a trade
        
        Args:
            trade_id: Trade identifier
            
        Returns:
            List of snapshot dicts ordered by time
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM position_snapshots
            WHERE trade_id = ?
            ORDER BY snapshot_time ASC
        """, (trade_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== DAILY SUMMARY ====================
    
    def update_daily_summary(self, date: str, paper_trading: bool):
        """Calculate and update daily summary statistics
        
        Args:
            date: Date in YYYY-MM-DD format
            paper_trading: Whether this is paper or live trading
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate statistics from trades
        stats = self.get_trade_statistics(
            paper_trading=paper_trading,
            start_date=f"{date}T00:00:00"
        )
        
        # Count scans performed
        cursor.execute("""
            SELECT COUNT(DISTINCT scan_id) FROM scan_results
            WHERE DATE(scan_time) = ?
        """, (date,))
        scans_performed = cursor.fetchone()[0]
        
        # Count opportunities found
        cursor.execute("""
            SELECT COUNT(*) FROM scan_results
            WHERE DATE(scan_time) = ?
        """, (date,))
        opportunities_found = cursor.fetchone()[0]
        
        # Insert or update daily summary
        cursor.execute("""
            INSERT INTO daily_summary (
                date, trades_count, winning_trades, losing_trades, total_pnl,
                win_rate, avg_win, avg_loss, largest_win, largest_loss,
                total_volume, scans_performed, opportunities_found, paper_trading
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                trades_count = excluded.trades_count,
                winning_trades = excluded.winning_trades,
                losing_trades = excluded.losing_trades,
                total_pnl = excluded.total_pnl,
                win_rate = excluded.win_rate,
                avg_win = excluded.avg_win,
                avg_loss = excluded.avg_loss,
                largest_win = excluded.largest_win,
                largest_loss = excluded.largest_loss,
                scans_performed = excluded.scans_performed,
                opportunities_found = excluded.opportunities_found,
                updated_at = CURRENT_TIMESTAMP
        """, (
            date,
            stats.get('total_trades', 0),
            stats.get('winning_trades', 0),
            stats.get('losing_trades', 0),
            stats.get('total_pnl', 0.0),
            stats.get('win_rate', 0.0),
            stats.get('avg_win', 0.0),
            stats.get('avg_loss', 0.0),
            stats.get('largest_win', 0.0),
            stats.get('largest_loss', 0.0),
            0.0,  # total_volume - calculate separately if needed
            scans_performed,
            opportunities_found,
            paper_trading
        ))
        
        conn.commit()
    
    def get_daily_summaries(self, start_date: Optional[str] = None,
                           limit: int = 30) -> List[Dict]:
        """Get daily summary statistics
        
        Args:
            start_date: Get summaries from this date onwards
            limit: Max number of days to return
            
        Returns:
            List of daily summary dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM daily_summary WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== UTILITY METHODS ====================
    
    def backup_database(self, backup_path: str):
        """Create a backup of the database
        
        Args:
            backup_path: Path for backup file
        """
        import shutil
        shutil.copy2(self.db_path, backup_path)
    
    def get_database_stats(self) -> Dict:
        """Get database statistics
        
        Returns:
            Dict with table sizes and total records
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        tables = [
            'market_data', 'trades', 'scan_results',
            'llm_decisions', 'position_snapshots', 'daily_summary'
        ]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        
        # Get database file size
        db_size = Path(self.db_path).stat().st_size
        stats['database_size_mb'] = db_size / (1024 * 1024)
        
        return stats
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


if __name__ == '__main__':
    # Test database creation
    db = TradingDatabase('data/test_silktrader.db')
    print("✅ Database schema created successfully")
    print("\n📊 Database Statistics:")
    stats = db.get_database_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    db.close()
