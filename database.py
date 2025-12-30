import sqlite3

DB_NAME = "pastebin.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS pastes (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            ttl_seconds INTEGER,
            max_views INTEGER,
            views_used INTEGER DEFAULT 0
        )
    """)
    db.commit()
