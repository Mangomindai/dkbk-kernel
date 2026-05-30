"""
Constitutional Governance Kernel
Trust levels: TRUSTED → LIMITED → OBSERVED → SUSPICIOUS → QUARANTINED → REVOKED
"""

import time
import sqlite3
from datetime import datetime, timedelta

class TrustEngine:
    LEVELS = ["TRUSTED", "LIMITED", "OBSERVED", "SUSPICIOUS", "QUARANTINED", "REVOKED"]
    
    # Penalty points per violation type
    PENALTIES = {
        "drug_listing": 40,
        "fake_verification": 50,
        "spam": 20,
        "hate_speech": 60,
        "abuse": 30,
        "multiple_flags": 25,
        "high_risk_activity": 35
    }
    
    # Points needed for each level
    THRESHOLDS = {
        "TRUSTED": 0,
        "LIMITED": 20,
        "OBSERVED": 40,
        "SUSPICIOUS": 60,
        "QUARANTINED": 80,
        "REVOKED": 100
    }
    
    def __init__(self, db_path="trust.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trust (
                    user_id TEXT PRIMARY KEY,
                    points INTEGER DEFAULT 0,
                    level TEXT DEFAULT 'TRUSTED',
                    last_updated REAL,
                    appeal_status TEXT DEFAULT 'none',
                    appeal_text TEXT,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    violation_type TEXT,
                    points INTEGER,
                    timestamp REAL,
                    details TEXT
                )
            """)
    
    def get_trust_level(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT level, points FROM trust WHERE user_id=?", (user_id,)).fetchone()
            if row:
                return row[0]
            # New user starts at TRUSTED
            self._create_user(user_id)
            return "TRUSTED"
    
    def _create_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trust (user_id, points, level, last_updated, created_at)
                VALUES (?, 0, 'TRUSTED', ?, ?)
            """, (user_id, time.time(), time.time()))
    
    def apply_penalty(self, user_id, violation_type):
        points = self.PENALTIES.get(violation_type, 20)
        
        with sqlite3.connect(self.db_path) as conn:
            # Get current points
            row = conn.execute("SELECT points FROM trust WHERE user_id=?", (user_id,)).fetchone()
            current_points = row[0] if row else 0
            new_points = min(current_points + points, 100)
            
            # Determine new level
            new_level = self._points_to_level(new_points)
            
            conn.execute("""
                UPDATE trust SET points=?, level=?, last_updated=?
                WHERE user_id=?
            """, (new_points, new_level, time.time(), user_id))
            
            conn.execute("""
                INSERT INTO violations (user_id, violation_type, points, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, violation_type, points, time.time(), ""))
        
        return {"new_points": new_points, "new_level": new_level}
    
    def upgrade_trust(self, user_id, reason="verification_passed"):
        """Reduce penalty points over time (trust recovery)"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT points FROM trust WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                return
            
            current_points = row[0]
            new_points = max(0, current_points - 15)  # Recovery after good behavior
            
            new_level = self._points_to_level(new_points)
            
            conn.execute("""
                UPDATE trust SET points=?, level=?, last_updated=?
                WHERE user_id=?
            """, (new_points, new_level, time.time(), user_id))
            
            conn.execute("""
                INSERT INTO violations (user_id, violation_type, points, timestamp, details)
                VALUES (?, 'trust_recovery', ?, ?, ?)
            """, (user_id, -15, time.time(), reason))
    
    def _points_to_level(self, points):
        if points >= 100:
            return "REVOKED"
        elif points >= 80:
            return "QUARANTINED"
        elif points >= 60:
            return "SUSPICIOUS"
        elif points >= 40:
            return "OBSERVED"
        elif points >= 20:
            return "LIMITED"
        else:
            return "TRUSTED"
    
    def submit_appeal(self, user_id, reason, evidence):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE trust SET appeal_status='pending', appeal_text=?
                WHERE user_id=?
            """, (f"Reason: {reason}\nEvidence: {evidence}", user_id))
        
        return {"status": "appeal_submitted", "review_time": "48 hours"}
    
    def get_history(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT violation_type, points, timestamp FROM violations
                WHERE user_id=? ORDER BY timestamp DESC LIMIT 50
            """, (user_id,)).fetchall()
        
        return [{"type": r[0], "points": r[1], "timestamp": r[2]} for r in rows]