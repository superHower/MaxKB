# coding=utf-8
"""SQLite datasets, runs, results and final-context workflow logs."""
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .dataset import canonical, version


def now():
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS datasets (
                name TEXT, version TEXT, imported_at TEXT, cases TEXT, PRIMARY KEY (name, version));
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, dataset TEXT, version TEXT, created_at TEXT,
                status TEXT, config TEXT, report TEXT);
            CREATE TABLE IF NOT EXISTS results (
                run_id TEXT, case_id TEXT, result TEXT, PRIMARY KEY (run_id, case_id));
            CREATE TABLE IF NOT EXISTS retrieval_events (
                chat_id TEXT, chat_record_id TEXT, created_at TEXT, contexts TEXT,
                PRIMARY KEY (chat_id, chat_record_id));
        """)

    def close(self):
        self.db.close()

    def import_dataset(self, name, cases):
        digest = version(cases)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO datasets VALUES (?, ?, ?, ?)",
                            (name, digest, now(), canonical(cases)))
        return digest

    def dataset(self, name, digest=None):
        if digest:
            row = self.db.execute("SELECT version, cases FROM datasets WHERE name=? AND version=?",
                                  (name, digest)).fetchone()
        else:
            row = self.db.execute("SELECT version, cases FROM datasets WHERE name=? ORDER BY imported_at DESC LIMIT 1",
                                  (name,)).fetchone()
        if row is None:
            raise ValueError("Dataset version not found")
        return row[0], json.loads(row[1])

    def start(self, run_id, name, digest, config):
        with self.db:
            self.db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, 'running', ?, NULL)",
                            (run_id, name, digest, now(), canonical(config)))

    def save_result(self, run_id, result):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?)",
                            (run_id, result["id"], canonical(result)))

    def finish(self, run_id, report):
        with self.db:
            self.db.execute("UPDATE runs SET status=?, report=? WHERE id=?",
                            (report["status"], canonical(report), run_id))

    def baseline(self, name, digest, run_id=None):
        if run_id:
            row = self.db.execute("SELECT report FROM runs WHERE id=? AND report IS NOT NULL", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Baseline run not found or unfinished")
        else:
            row = self.db.execute("SELECT report FROM runs WHERE dataset=? AND version=? AND status='completed' "
                                  "ORDER BY created_at DESC LIMIT 1", (name, digest)).fetchone()
        return json.loads(row[0]) if row else None

    def log_context(self, chat_id, record_id, contexts):
        if not chat_id or not record_id or not isinstance(contexts, list):
            raise ValueError("chat_id, chat_record_id and contexts array required")
        for item in contexts:
            if not isinstance(item, dict) or not isinstance(item.get("content"), str):
                raise TypeError("Each context requires content text")
            if not item.get("document_id") or not item.get("paragraph_id", item.get("id")):
                raise ValueError("Each context requires document_id and paragraph_id")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO retrieval_events VALUES (?, ?, ?, ?)",
                            (chat_id, record_id, now(), canonical(contexts)))

    def contexts(self, chat_id, record_id):
        row = self.db.execute("SELECT contexts FROM retrieval_events WHERE chat_id=? AND chat_record_id=?",
                              (chat_id, record_id)).fetchone()
        return json.loads(row[0]) if row else None
