from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import Connection, connect


SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    watch INTEGER DEFAULT 0,
    last_etag TEXT,
    last_poll_at TEXT,
    patrol_interval_hours INTEGER DEFAULT 12,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    trigger TEXT,
    status TEXT DEFAULT 'pending',
    session_id TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT NOT NULL,
    line TEXT NOT NULL,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_events (
    repo_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT,
    processed_at TEXT NOT NULL,
    UNIQUE(repo_id, event_id)
);

CREATE TABLE IF NOT EXISTS patrol_budget (
    repo_id TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    issues_filed INTEGER DEFAULT 0,
    max_issues INTEGER DEFAULT 5,
    window_hours INTEGER DEFAULT 12
);

CREATE TABLE IF NOT EXISTS webhook_config (
    repo_id TEXT PRIMARY KEY,
    webhook_secret TEXT NOT NULL,
    webhook_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    received_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS installations (
    installation_id TEXT PRIMARY KEY,
    account_login TEXT NOT NULL,
    account_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Migrations: columns added after initial schema
_MIGRATIONS = [
    "ALTER TABLE repos ADD COLUMN watch INTEGER DEFAULT 0",
    "ALTER TABLE repos ADD COLUMN last_etag TEXT",
    "ALTER TABLE repos ADD COLUMN last_poll_at TEXT",
    "ALTER TABLE repos ADD COLUMN patrol_interval_hours INTEGER DEFAULT 12",
    "ALTER TABLE activities ADD COLUMN requires_approval INTEGER DEFAULT 0",
    "ALTER TABLE activities ADD COLUMN approval_comment_url TEXT",
    "ALTER TABLE activities ADD COLUMN approved_by TEXT",
    "ALTER TABLE activities ADD COLUMN approved_at TEXT",
    "ALTER TABLE activities ADD COLUMN cost_usd REAL",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(
        self,
        db_path: Path | None = None,
        db_url: str | None = None,
    ) -> None:
        if db_url:
            self._db: Connection = connect(db_url)
        elif db_path:
            self._db = connect(str(db_path))
        else:
            self._db = connect()
        self._db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Apply schema migrations idempotently (ignore errors for existing columns)."""
        for migration in _MIGRATIONS:
            try:
                self._db.execute(migration)
                self._db.commit()
            except Exception:
                pass  # Column already exists

    # --- repos ---

    def add_repo(self, repo_id: str, repo_url: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO repos (id, repo_url, created_at) VALUES (?, ?, ?)",
            (repo_id, repo_url, _now()),
        )
        self._db.commit()

    def get_repo(self, repo_id: str) -> dict | None:
        return self._db.execute_one("SELECT * FROM repos WHERE id = ?", (repo_id,))

    def list_repos(self) -> list[dict]:
        return self._db.execute("SELECT * FROM repos ORDER BY created_at")

    def list_watched_repos(self) -> list[dict]:
        return self._db.execute("SELECT * FROM repos WHERE watch = 1 ORDER BY created_at")

    def update_repo(self, repo_id: str, **fields: object) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (repo_id,)
        self._db.execute(f"UPDATE repos SET {set_clause} WHERE id = ?", values)
        self._db.commit()

    # --- activities ---

    def add_activity(self, repo_id: str, kind: str, trigger: str | None = None) -> str:
        activity_id = str(uuid.uuid4())
        now = _now()
        self._db.execute(
            """INSERT INTO activities
               (id, repo_id, kind, trigger, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (activity_id, repo_id, kind, trigger, now, now),
        )
        self._db.commit()
        return activity_id

    def get_activity(self, activity_id: str) -> dict | None:
        return self._db.execute_one(
            "SELECT * FROM activities WHERE id = ?", (activity_id,)
        )

    def update_activity(self, activity_id: str, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (activity_id,)
        self._db.execute(f"UPDATE activities SET {set_clause} WHERE id = ?", values)
        self._db.commit()

    def get_pending_activities(self) -> list[dict]:
        return self._db.execute(
            "SELECT * FROM activities WHERE status = 'pending' ORDER BY created_at"
        )

    def get_running_activities(self) -> list[dict]:
        return self._db.execute(
            "SELECT * FROM activities WHERE status = 'running' ORDER BY created_at"
        )

    def list_activities(self, repo_id: str | None = None) -> list[dict]:
        if repo_id is not None:
            return self._db.execute(
                "SELECT * FROM activities WHERE repo_id = ? ORDER BY created_at",
                (repo_id,),
            )
        return self._db.execute("SELECT * FROM activities ORDER BY created_at")

    def get_stats(self) -> dict:
        """Return aggregate stats for the dashboard."""
        repos_total = (self._db.execute_one("SELECT COUNT(*) as c FROM repos") or {}).get("c", 0)
        repos_watched = (self._db.execute_one("SELECT COUNT(*) as c FROM repos WHERE watch=1") or {}).get("c", 0)

        rows = self._db.execute(
            "SELECT status, COUNT(*) as cnt, SUM(COALESCE(cost_usd,0)) as cost FROM activities GROUP BY status"
        )
        by_status: dict[str, int] = {}
        total_cost: float = 0.0
        for row in rows:
            by_status[row["status"]] = row["cnt"]
            total_cost += row["cost"] or 0.0

        kind_rows = self._db.execute(
            "SELECT kind, COUNT(*) as cnt FROM activities GROUP BY kind ORDER BY cnt DESC"
        )
        by_kind = {r["kind"]: r["cnt"] for r in kind_rows}

        recent = self._db.execute(
            "SELECT * FROM activities ORDER BY updated_at DESC LIMIT 20"
        )

        return {
            "repos": {"total": repos_total, "watched": repos_watched},
            "activities": {
                "by_status": by_status,
                "by_kind": by_kind,
                "total": sum(by_status.values()),
            },
            "cost_usd": round(total_cost, 4),
            "recent_activities": recent,
        }

    def get_repo_stats(self, repo_id: str) -> dict | None:
        """Return per-repo stats for the dashboard."""
        repo = self._db.execute_one("SELECT * FROM repos WHERE id=?", (repo_id,))
        if repo is None:
            return None

        rows = self._db.execute(
            "SELECT status, COUNT(*) as cnt, SUM(COALESCE(cost_usd,0)) as cost "
            "FROM activities WHERE repo_id=? GROUP BY status",
            (repo_id,),
        )
        by_status: dict[str, int] = {}
        total_cost: float = 0.0
        for row in rows:
            by_status[row["status"]] = row["cnt"]
            total_cost += row["cost"] or 0.0

        recent = self._db.execute(
            "SELECT * FROM activities WHERE repo_id=? ORDER BY updated_at DESC LIMIT 10",
            (repo_id,),
        )

        return {
            "repo": repo,
            "activities": {
                "by_status": by_status,
                "total": sum(by_status.values()),
            },
            "cost_usd": round(total_cost, 4),
            "recent_activities": recent,
        }

    def mark_crashed_activities_failed(self) -> int:
        """On daemon startup, mark any status=running activities as failed (previous crash)."""
        rows_before = self._db.execute(
            "SELECT COUNT(*) as c FROM activities WHERE status = 'running'"
        )
        count = (rows_before[0] if rows_before else {}).get("c", 0)
        self._db.execute(
            "UPDATE activities SET status = 'failed', "
            "summary = 'Interrupted (daemon restarted)', updated_at = ? "
            "WHERE status = 'running'",
            (_now(),),
        )
        self._db.commit()
        return count

    # --- logs ---

    def add_log(self, activity_id: str, line: str) -> None:
        self._db.execute(
            "INSERT INTO logs (activity_id, line, ts) VALUES (?, ?, ?)",
            (activity_id, line, _now()),
        )
        self._db.commit()

    def add_logs_batch(self, activity_id: str, lines: list[str]) -> None:
        """Batch-insert log lines for better I/O performance."""
        if not lines:
            return
        now = _now()
        self._db.executemany(
            "INSERT INTO logs (activity_id, line, ts) VALUES (?, ?, ?)",
            [(activity_id, line, now) for line in lines],
        )
        self._db.commit()

    def get_logs(self, activity_id: str) -> list[dict]:
        return self._db.execute(
            "SELECT * FROM logs WHERE activity_id = ? ORDER BY id",
            (activity_id,),
        )

    # --- processed events ---

    def is_event_processed(self, repo_id: str, event_id: str) -> bool:
        row = self._db.execute_one(
            "SELECT 1 as found FROM processed_events WHERE repo_id = ? AND event_id = ?",
            (repo_id, event_id),
        )
        return row is not None

    def mark_event_processed(self, repo_id: str, event_id: str, event_type: str) -> None:
        self._db.execute(
            """INSERT OR IGNORE INTO processed_events
               (repo_id, event_id, event_type, processed_at)
               VALUES (?, ?, ?, ?)""",
            (repo_id, event_id, event_type, _now()),
        )
        self._db.commit()

    # --- patrol budget ---

    def get_patrol_budget(self, repo_id: str) -> int:
        """Return remaining issues budget for this patrol window. Resets when window expires."""
        row = self._db.execute_one(
            "SELECT * FROM patrol_budget WHERE repo_id = ?", (repo_id,)
        )
        if row is None:
            return 5  # Default budget for new repos

        window_start = datetime.fromisoformat(row["window_start"])
        window_hours = row["window_hours"]
        elapsed_hours = (datetime.now(timezone.utc) - window_start).total_seconds() / 3600

        if elapsed_hours >= window_hours:
            self._db.execute(
                "UPDATE patrol_budget SET window_start = ?, issues_filed = 0 WHERE repo_id = ?",
                (_now(), repo_id),
            )
            self._db.commit()
            return row["max_issues"]

        return max(0, row["max_issues"] - row["issues_filed"])

    def init_patrol_budget(self, repo_id: str, max_issues: int = 5, window_hours: int = 12) -> None:
        """Initialize patrol budget for a repo (idempotent)."""
        self._db.execute(
            """INSERT OR IGNORE INTO patrol_budget
               (repo_id, window_start, issues_filed, max_issues, window_hours)
               VALUES (?, ?, 0, ?, ?)""",
            (repo_id, _now(), max_issues, window_hours),
        )
        self._db.commit()

    def decrement_patrol_budget(self, repo_id: str) -> None:
        """Record that one issue was filed in the current patrol window."""
        self._db.execute(
            "UPDATE patrol_budget SET issues_filed = issues_filed + 1 WHERE repo_id = ?",
            (repo_id,),
        )
        self._db.commit()

    # --- approval workflow ---

    def get_pending_approval_activities(self) -> list[dict]:
        """Get activities waiting for human approval."""
        return self._db.execute(
            """SELECT * FROM activities
               WHERE status = 'pending' AND requires_approval = 1
               ORDER BY created_at"""
        )

    # --- webhook management ---

    def add_webhook_config(self, repo_id: str, secret: str, webhook_id: str | None = None) -> None:
        """Store webhook configuration for a repo."""
        self._db.execute(
            """INSERT OR REPLACE INTO webhook_config
               (repo_id, webhook_secret, webhook_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (repo_id, secret, webhook_id, _now()),
        )
        self._db.commit()

    def get_webhook_config(self, repo_id: str) -> dict | None:
        """Get webhook configuration for a repo."""
        return self._db.execute_one(
            "SELECT * FROM webhook_config WHERE repo_id = ?", (repo_id,)
        )

    def add_webhook_event(
        self, event_id: str, repo_id: str, event_type: str, payload: str | None = None
    ) -> None:
        """Record a received webhook event."""
        self._db.execute(
            """INSERT OR IGNORE INTO webhook_events
               (event_id, repo_id, event_type, payload, received_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, repo_id, event_type, payload, _now()),
        )
        self._db.commit()

    def is_webhook_event_processed(self, event_id: str) -> bool:
        """Check if a webhook event has been processed."""
        row = self._db.execute_one(
            "SELECT processed FROM webhook_events WHERE event_id = ?", (event_id,)
        )
        return row is not None and row["processed"] == 1

    def mark_webhook_event_processed(self, event_id: str) -> None:
        """Mark a webhook event as processed."""
        self._db.execute(
            "UPDATE webhook_events SET processed = 1 WHERE event_id = ?", (event_id,)
        )
        self._db.commit()

    # --- GitHub App installations ---

    def add_installation(
        self,
        installation_id: str,
        account_login: str,
        account_type: str,
    ) -> None:
        """Record a GitHub App installation."""
        self._db.execute(
            """INSERT OR REPLACE INTO installations
               (installation_id, account_login, account_type, created_at)
               VALUES (?, ?, ?, ?)""",
            (installation_id, account_login, account_type, _now()),
        )
        self._db.commit()

    def get_installation(self, installation_id: str) -> dict | None:
        """Get a GitHub App installation record."""
        return self._db.execute_one(
            "SELECT * FROM installations WHERE installation_id = ?", (installation_id,)
        )

    def delete_installation(self, installation_id: str) -> None:
        """Remove a GitHub App installation record."""
        self._db.execute(
            "DELETE FROM installations WHERE installation_id = ?", (installation_id,)
        )
        self._db.commit()
