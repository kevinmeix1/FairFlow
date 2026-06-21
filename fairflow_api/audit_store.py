from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import GuardianDecision


DEFAULT_DB_PATH = Path(os.getenv("FAIRFLOW_AUDIT_DB", "data/fairflow_audits.sqlite3"))


class AuditLedger:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_reports (
                    audit_hash TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    category TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_action TEXT NOT NULL,
                    fairness_score REAL NOT NULL,
                    generated_at TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_reports_stored_at ON audit_reports(stored_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_reports_symbol ON audit_reports(symbol)")

    def store_decision(self, decision: GuardianDecision) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_reports (
                    audit_hash,
                    symbol,
                    category,
                    scenario,
                    source,
                    status,
                    final_action,
                    fairness_score,
                    generated_at,
                    stored_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.audit_hash,
                    decision.symbol,
                    decision.category,
                    decision.scenario,
                    decision.source,
                    decision.status,
                    decision.final_action,
                    decision.fairness_passport.score,
                    decision.generated_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                    decision.model_dump_json(),
                ),
            )

    def get_decision(self, audit_hash: str) -> GuardianDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM audit_reports WHERE audit_hash = ?",
                (audit_hash,),
            ).fetchone()
        if not row:
            return None
        return GuardianDecision.model_validate_json(row["payload_json"])

    def list_decisions(self, limit: int = 20) -> list[GuardianDecision]:
        bounded_limit = max(1, min(200, limit))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM audit_reports
                ORDER BY stored_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [GuardianDecision.model_validate_json(row["payload_json"]) for row in reversed(rows)]

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM audit_reports").fetchone()
        return int(row["count"]) if row else 0
