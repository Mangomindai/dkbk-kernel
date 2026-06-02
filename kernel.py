"""
Constitutional Governance Kernel
Trust levels: TRUSTED → LIMITED → OBSERVED → SUSPICIOUS → QUARANTINED → REVOKED
"""

import time
import sqlite3


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
        "high_risk_activity": 35,
        "unauthorized_access": 40,
    }

    # Points needed for each level
    THRESHOLDS = {
        "TRUSTED": 0,
        "LIMITED": 20,
        "OBSERVED": 40,
        "SUSPICIOUS": 60,
        "QUARANTINED": 80,
        "REVOKED": 100,
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

    def get_trust_level(self, user_id: str) -> str:
        """
        Returns the current trust level for an agent.

        Levels (in order of degradation):
            TRUSTED → LIMITED → OBSERVED → SUSPICIOUS → QUARANTINED → REVOKED

        Args:
            user_id: Unique identifier for the agent.

        Returns:
            Trust level string.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT level, points FROM trust WHERE user_id=?", (user_id,)
            ).fetchone()
            if row:
                return row[0]
            self._create_user(user_id)
            return "TRUSTED"

    def get_trust_score(self, user_id: str) -> dict:
        """
        Returns full trust info: level, points, appeal status.

        Args:
            user_id: Unique identifier for the agent.

        Returns:
            Dict with level, points, appeal_status.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT level, points, appeal_status FROM trust WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if row:
                return {"level": row[0], "points": row[1], "appeal_status": row[2]}
            self._create_user(user_id)
            return {"level": "TRUSTED", "points": 0, "appeal_status": "none"}

    def _create_user(self, user_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO trust (user_id, points, level, last_updated, created_at)
                VALUES (?, 0, 'TRUSTED', ?, ?)
            """,
                (user_id, time.time(), time.time()),
            )

    def apply_penalty(self, user_id: str, violation_type: str, details: str = "") -> dict:
        """
        Applies a penalty to an agent for a policy violation.

        Args:
            user_id: Unique identifier for the agent.
            violation_type: One of the known violation keys (e.g. 'spam', 'abuse').
                            Unknown types default to 20 points.
            details: Optional details about the violation.

        Returns:
            Dict with new_points and new_level.
        """
        self._create_user(user_id)
        points = self.PENALTIES.get(violation_type, 20)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT points FROM trust WHERE user_id=?", (user_id,)
            ).fetchone()
            current_points = row[0] if row else 0
            new_points = min(current_points + points, 100)
            new_level = self._points_to_level(new_points)

            conn.execute(
                "UPDATE trust SET points=?, level=?, last_updated=? WHERE user_id=?",
                (new_points, new_level, time.time(), user_id),
            )
            conn.execute(
                """
                INSERT INTO violations (user_id, violation_type, points, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, violation_type, points, time.time(), details),
            )

        return {"new_points": new_points, "new_level": new_level}

    def upgrade_trust(self, user_id: str, reason: str = "verification_passed") -> dict:
        """
        Recovers trust for an agent (rewards good behaviour).
        Reduces penalty points by 15.

        Args:
            user_id: Unique identifier for the agent.
            reason: Reason for the trust upgrade.

        Returns:
            Dict with new_points and new_level.
        """
        self._create_user(user_id)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT points FROM trust WHERE user_id=?", (user_id,)
            ).fetchone()
            current_points = row[0] if row else 0
            new_points = max(0, current_points - 15)
            new_level = self._points_to_level(new_points)

            conn.execute(
                "UPDATE trust SET points=?, level=?, last_updated=? WHERE user_id=?",
                (new_points, new_level, time.time(), user_id),
            )
            conn.execute(
                """
                INSERT INTO violations (user_id, violation_type, points, timestamp, details)
                VALUES (?, 'trust_recovery', ?, ?, ?)
            """,
                (user_id, -15, time.time(), reason),
            )

        return {"new_points": new_points, "new_level": new_level}

    def is_allowed(self, user_id: str) -> bool:
        """
        Quick check — is this agent allowed to act?
        Returns False for QUARANTINED or REVOKED agents.

        Args:
            user_id: Unique identifier for the agent.

        Returns:
            True if agent can act, False if blocked.
        """
        level = self.get_trust_level(user_id)
        return level not in ("QUARANTINED", "REVOKED")

    def revoke(self, user_id: str, reason: str = "manual_revocation") -> dict:
        """
        Immediately revokes an agent — hard stop.

        Args:
            user_id: Unique identifier for the agent.
            reason: Reason for revocation.

        Returns:
            Dict confirming revocation.
        """
        self._create_user(user_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE trust SET points=100, level='REVOKED', last_updated=? WHERE user_id=?",
                (time.time(), user_id),
            )
            conn.execute(
                """
                INSERT INTO violations (user_id, violation_type, points, timestamp, details)
                VALUES (?, 'manual_revocation', 100, ?, ?)
            """,
                (user_id, time.time(), reason),
            )
        return {"user_id": user_id, "level": "REVOKED", "reason": reason}

    def submit_appeal(self, user_id: str, reason: str, evidence: str) -> dict:
        """
        Agent submits an appeal against a block.

        Args:
            user_id: Unique identifier for the agent.
            reason: Appeal reason.
            evidence: Supporting evidence.

        Returns:
            Dict with appeal status and review time.
        """
        self._create_user(user_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE trust SET appeal_status='pending', appeal_text=? WHERE user_id=?",
                (f"Reason: {reason}\nEvidence: {evidence}", user_id),
            )
        return {"status": "appeal_submitted", "review_time": "48 hours"}

    def get_history(self, user_id: str, limit: int = 50) -> list:
        """
        Returns the violation/recovery history for an agent.

        Args:
            user_id: Unique identifier for the agent.
            limit: Max number of records to return (default 50).

        Returns:
            List of dicts with type, points, timestamp.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT violation_type, points, timestamp, details
                FROM violations
                WHERE user_id=?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (user_id, limit),
            ).fetchall()
        return [
            {"type": r[0], "points": r[1], "timestamp": r[2], "details": r[3]}
            for r in rows
        ]

    def list_agents(self) -> list:
        """
        Returns all tracked agents and their current trust state.

        Returns:
            List of dicts with user_id, level, points.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT user_id, level, points, last_updated FROM trust ORDER BY points DESC"
            ).fetchall()
        return [
            {"user_id": r[0], "level": r[1], "points": r[2], "last_updated": r[3]}
            for r in rows
        ]

    def _points_to_level(self, points: int) -> str:
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
