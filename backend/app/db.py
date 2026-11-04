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
CREATE TABLE IF NOT EXISTS chat_sessions (
  key_hash TEXT PRIMARY KEY, state BLOB NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS feedback (
  assessment_id TEXT PRIMARY KEY, trust INTEGER, clarity INTEGER, comfort INTEGER, ts REAL);
"""


DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))


class Row(dict):
    """Same access style for SQLite and Postgres rows: row["col"], row[0], dict(row), row.keys()."""
    def __getitem__(self, k):
        return list(self.values())[k] if isinstance(k, int) else dict.__getitem__(self, k)


class _Cur:
    def __init__(self, cur):
        self.cur = cur
        self.rowcount = cur.rowcount

    def _wrap(self, r):
        if r is None:
            return None
        if isinstance(r, sqlite3.Row):
            return Row(zip(r.keys(), tuple(r)))
        return Row({k: bytes(v) if isinstance(v, memoryview) else v for k, v in r.items()})

    def fetchone(self):
        return self._wrap(self.cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self.cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _Con:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        if PG:
            if sql.lstrip().upper().startswith("INSERT OR REPLACE INTO FEEDBACK"):
                sql = ("INSERT INTO feedback VALUES (?,?,?,?,?) ON CONFLICT (assessment_id) DO UPDATE SET "
                       "trust=EXCLUDED.trust, clarity=EXCLUDED.clarity, comfort=EXCLUDED.comfort, ts=EXCLUDED.ts")
            sql = sql.replace("?", "%s")
            cur = self.raw.cursor()
            cur.execute(sql, params)
            return _Cur(cur)
        return _Cur(self.raw.execute(sql, params))

    def columns(self, table):
        if PG:
            return {r["column_name"] for r in self.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=?", (table,)).fetchall()}
        return {r["name"] for r in self.execute(f"PRAGMA table_info({table})").fetchall()}

    def script(self, text):
        if PG:
            text = text.replace(" BLOB", " BYTEA").replace(" REAL", " DOUBLE PRECISION")
            for stmt in filter(str.strip, text.split(";")):
                self.raw.execute(stmt)
        else:
            self.raw.executescript(text)


def connect():
    if PG:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA secure_delete=ON")  # deleted rows are overwritten, not just unlinked
    return con


@contextmanager
def tx():
    raw = connect()
    try:
        yield _Con(raw)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


MIGRATIONS = {
    "assessments": [("labs", "BLOB")],
    "messages": [("audio", "BLOB"), ("mime", "TEXT"), ("seconds", "REAL")],
    "referrals": [("rapid", "INTEGER DEFAULT 0"), ("due_at", "REAL"), ("video_url", "TEXT"), ("handover_at", "REAL")],
}


def init():
    with tx() as c:
        c.script(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = c.columns(table)
            for name, decl in cols:
                if name not in have:
                    if PG:
                        decl = decl.replace("BLOB", "BYTEA").replace("REAL", "DOUBLE PRECISION")
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def audit(actor, action, target=None):
    with tx() as c:
        c.execute("INSERT INTO audit VALUES (?,?,?,?)", (time.time(), actor, action, target))


def event(assessment_id, type_, detail=None):
    with tx() as c:
        c.execute("INSERT INTO events VALUES (?,?,?,?)", (time.time(), assessment_id, type_, detail))
