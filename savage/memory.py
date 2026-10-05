"""SQLite persistent memory: sessions, messages, tasks, events."""
import os, sqlite3, time, uuid
from urllib.parse import quote

# Versioned migrations (PRAGMA user_version). Append new (version, sql) entries; never edit old ones.
MIGRATIONS = [
    (1, """
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, started REAL, last_active REAL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, session_id TEXT,
  role TEXT, content TEXT, task_id TEXT);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, ts REAL, session_id TEXT, request TEXT,
  status TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, session_id TEXT,
  task_id TEXT, kind TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_msg_session ON messages(session_id, id);
"""),
    (2, """
CREATE TABLE IF NOT EXISTS skills(name TEXT PRIMARY KEY, permission TEXT, status TEXT,
  description TEXT, updated REAL);
"""),
]
LATEST = MIGRATIONS[-1][0]
REQUIRED_TABLES = {"sessions", "messages", "tasks", "events", "skills"}


def inspect(path):
    """Read-only look at a database file (never creates or modifies it)."""
    if not os.path.isfile(path):
        return {"exists": False}
    try:
        db = sqlite3.connect("file:" + quote(path) + "?mode=ro", uri=True)
        try:
            ver = db.execute("PRAGMA user_version").fetchone()[0]
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            skills = [r[0] for r in db.execute("SELECT name FROM skills")] if "skills" in tables else []
        finally:
            db.close()
    except sqlite3.Error as e:
        return {"exists": True, "error": str(e)}
    return {"exists": True, "version": ver, "tables": tables, "skills": skills,
            "missing": sorted(REQUIRED_TABLES - tables)}


MAX_CONTENT = 8000


class Memory:
    def __init__(self, cfg):
        self.path = cfg.path("memory", "savage.db")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.migrate()

    def migrate(self):
        cur = self.db.execute("PRAGMA user_version").fetchone()[0]
        if cur > LATEST:
            raise RuntimeError(f"memory database is schema v{cur}, newer than supported v{LATEST}")
        for ver, sql in MIGRATIONS:
            if ver > cur:
                self.db.executescript(sql)
                self.db.execute(f"PRAGMA user_version={int(ver)}")
        self.db.commit()

    def repair_schema(self):
        """Re-run the (idempotent CREATE IF NOT EXISTS) migrations; never drops data."""
        for _, sql in MIGRATIONS:
            self.db.executescript(sql)
        self.db.commit()

    def upsert_skill(self, name, perm, status, desc):
        self.db.execute("INSERT OR REPLACE INTO skills VALUES(?,?,?,?,?)", (name, perm, status, desc, time.time()))
        self.db.commit()

    def delete_session(self, sid):
        for t in ("messages", "tasks", "events", "sessions"):
            col = "id" if t == "sessions" else "session_id"
            self.db.execute(f"DELETE FROM {t} WHERE {col}=?", (sid,))
        self.db.commit()

    def close(self):
        self.db.close()

    def session(self, resume=True):
        """Resume the most recent session or create one."""
        if resume:
            row = self.db.execute("SELECT id FROM sessions ORDER BY last_active DESC LIMIT 1").fetchone()
            if row:
                self.touch(row[0])
                return row[0]
        sid = uuid.uuid4().hex[:8]
        now = time.time()
        self.db.execute("INSERT INTO sessions VALUES(?,?,?)", (sid, now, now))
        self.db.commit()
        return sid

    def touch(self, sid):
        self.db.execute("UPDATE sessions SET last_active=? WHERE id=?", (time.time(), sid))
        self.db.commit()

    def add_message(self, sid, role, content, task_id=None):
        self.db.execute("INSERT INTO messages(ts,session_id,role,content,task_id) VALUES(?,?,?,?,?)",
                        (time.time(), sid, role, str(content)[:MAX_CONTENT], task_id))
        self.db.commit()

    def add_task(self, sid, request):
        tid = "t-" + uuid.uuid4().hex[:8]
        self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?)",
                        (tid, time.time(), sid, request[:MAX_CONTENT], "RUNNING", None))
        self.db.commit()
        return tid

    def finish_task(self, tid, status, result):
        self.db.execute("UPDATE tasks SET status=?, result=? WHERE id=?", (status, str(result)[:MAX_CONTENT], tid))
        self.db.commit()

    def add_event(self, sid, kind, detail="", task_id=None):
        self.db.execute("INSERT INTO events(ts,session_id,task_id,kind,detail) VALUES(?,?,?,?,?)",
                        (time.time(), sid, task_id, kind, str(detail)[:1000]))
        self.db.commit()

    def history(self, sid=None, limit=10):
        q = "SELECT ts, session_id, role, content, task_id FROM messages"
        a = []
        if sid:
            q += " WHERE session_id=?"
            a.append(sid)
        q += " ORDER BY id DESC LIMIT ?"
        a.append(max(1, min(int(limit), 100)))
        return list(reversed(self.db.execute(q, a).fetchall()))

    def stats(self):
        c = lambda t: self.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        return {"path": self.path, "size_kib": round(size / 1024, 1), "sessions": c("sessions"),
                "messages": c("messages"), "tasks": c("tasks"), "events": c("events")}
