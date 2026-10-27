"""Memory: cases, decisions, corrections, rule patches and active rule versions.

`Memory` is the interface; `SqliteMemory` is the local backend. A Meterless
Gaia backend would implement the same interface (not configured: no API access).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Memory(Protocol):
    status: str

    def save_assessment(self, household_id: str, payload: dict) -> str: ...
    def latest_assessment(self, household_id: str) -> dict | None: ...
    def all_latest(self) -> dict[str, dict]: ...
    def add_correction(self, household_id: str, kind: str, target: str, value: Any, note: str) -> dict: ...
    def corrections(self, household_id: str | None = None) -> list[dict]: ...
    def save_patch(self, patch: dict) -> None: ...
    def patches(self) -> list[dict]: ...
    def set_active_rule(self, benefit: str, rule_json: dict, origin: str) -> None: ...
    def active_rules(self) -> dict[str, dict]: ...
    def get_setting(self, key: str, default: Any = None) -> Any: ...
    def set_setting(self, key: str, value: Any) -> None: ...
    def reset(self) -> None: ...


class SqliteMemory:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.memory_db)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.status = "SQLite"
        self._lock = threading.Lock()
        self._con = sqlite3.connect(self.path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._con.executescript(
            """
            CREATE TABLE IF NOT EXISTS assessments (run_id TEXT PRIMARY KEY, household_id TEXT, created_at TEXT, payload TEXT);
            CREATE INDEX IF NOT EXISTS ix_assess_hh ON assessments(household_id, created_at);
            CREATE TABLE IF NOT EXISTS corrections (id TEXT PRIMARY KEY, household_id TEXT, kind TEXT, target TEXT,
                value TEXT, note TEXT, author TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS patches (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS active_rules (benefit TEXT PRIMARY KEY, rule TEXT, origin TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        self._con.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._con.execute(sql, args)
            rows = cur.fetchall()
            self._con.commit()
            return rows

    def save_assessment(self, household_id: str, payload: dict) -> str:
        run_id = payload.get("run_id") or uuid.uuid4().hex[:12]
        self._exec("INSERT OR REPLACE INTO assessments VALUES (?,?,?,?)",
                   (run_id, household_id, _now(), json.dumps(payload, default=str)))
        return run_id

    def latest_assessment(self, household_id: str) -> dict | None:
        rows = self._exec("SELECT payload FROM assessments WHERE household_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (household_id,))
        return json.loads(rows[0]["payload"]) if rows else None

    def all_latest(self) -> dict[str, dict]:
        rows = self._exec(
            "SELECT a.household_id, a.payload FROM assessments a JOIN (SELECT household_id, MAX(rowid) r FROM assessments GROUP BY household_id) m ON a.rowid = m.r")
        return {r["household_id"]: json.loads(r["payload"]) for r in rows}

    def add_correction(self, household_id: str, kind: str, target: str, value: Any, note: str, author: str = "caseworker") -> dict:
        c = {"id": uuid.uuid4().hex[:10], "household_id": household_id, "kind": kind, "target": target, "value": value,
             "note": note, "author": author, "created_at": _now()}
        self._exec("INSERT INTO corrections VALUES (?,?,?,?,?,?,?,?)",
                   (c["id"], household_id, kind, target, json.dumps(value), note, author, c["created_at"]))
        return c

    def corrections(self, household_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM corrections", ()
        if household_id:
            sql, args = sql + " WHERE household_id=?", (household_id,)
        rows = self._exec(sql + " ORDER BY created_at, rowid", args)
        return [{**dict(r), "value": json.loads(r["value"])} for r in rows]

    def save_patch(self, patch: dict) -> None:
        self._exec("INSERT OR REPLACE INTO patches VALUES (?,?,?)", (patch["id"], _now(), json.dumps(patch, default=str)))

    def patches(self) -> list[dict]:
        return [json.loads(r["payload"]) for r in self._exec("SELECT payload FROM patches ORDER BY created_at DESC, rowid DESC")]

    def set_active_rule(self, benefit: str, rule_json: dict, origin: str) -> None:
        self._exec("INSERT OR REPLACE INTO active_rules VALUES (?,?,?,?)", (benefit, json.dumps(rule_json), origin, _now()))

    def active_rules(self) -> dict[str, dict]:
        return {r["benefit"]: {"rule": json.loads(r["rule"]), "origin": r["origin"], "updated_at": r["updated_at"]}
                for r in self._exec("SELECT * FROM active_rules")}

    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._exec("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_setting(self, key: str, value: Any) -> None:
        self._exec("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def reset(self) -> None:
        for t in ("assessments", "corrections", "patches", "active_rules"):
            self._exec(f"DELETE FROM {t}")


_memory: SqliteMemory | None = None


def get_memory() -> SqliteMemory:
    global _memory
    if _memory is None:
        _memory = SqliteMemory()
        if settings.memory_backend == "gaia":
            _memory.status = "SQLite (Gaia requested but not configured)"
    return _memory
