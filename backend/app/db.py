import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("RIAYA_DB", ROOT / "data" / "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, created_at REAL NOT NULL, lang TEXT DEFAULT 'ar');
CREATE TABLE IF NOT EXISTS consents (
  user_id TEXT NOT NULL, purpose TEXT NOT NULL, granted INTEGER NOT NULL, version TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS assessments (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, started_at REAL NOT NULL, completed_at REAL,
  answers BLOB, wearable BLOB, semen BLOB, result BLOB,
  tier TEXT, level TEXT, requires_review INTEGER DEFAULT 0, review_consent INTEGER DEFAULT 0,
  cohort TEXT, simulated INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS referrals (
  id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, level TEXT NOT NULL, status TEXT NOT NULL,
  created_at REAL NOT NULL, reviewed_at REAL, reviewer TEXT, final_level TEXT, note BLOB,
  booked_at REAL, attended_at REAL, simulated INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS shares (
  code TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  revoked INTEGER DEFAULT 0, used_by TEXT);
CREATE TABLE IF NOT EXISTS clinicians (
  username TEXT PRIMARY KEY, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, display_name TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
  ts REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT);
CREATE TABLE IF NOT EXISTS events (
  ts REAL NOT NULL, assessment_id TEXT, type TEXT NOT NULL, detail TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, sender TEXT NOT NULL, body BLOB NOT NULL, ts REAL NOT NULL, read_at REAL);
CREATE TABLE IF NOT EXISTS partner_links (
  token_hash TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, revoked INTEGER DEFAULT 0, views INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS feedback (
  assessment_id TEXT PRIMARY KEY, trust INTEGER, clarity INTEGER, comfort INTEGER, ts REAL);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA secure_delete=ON")  # deleted rows are overwritten, not just unlinked
    return con


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


MIGRATIONS = {
    "assessments": [("labs", "BLOB")],
    "referrals": [("rapid", "INTEGER DEFAULT 0"), ("due_at", "REAL"), ("video_url", "TEXT"), ("handover_at", "REAL")],
}


def init():
    with tx() as c:
        c.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols:
                if name not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def audit(actor, action, target=None):
    with tx() as c:
        c.execute("INSERT INTO audit VALUES (?,?,?,?)", (time.time(), actor, action, target))


def event(assessment_id, type_, detail=None):
    with tx() as c:
        c.execute("INSERT INTO events VALUES (?,?,?,?)", (time.time(), assessment_id, type_, detail))
