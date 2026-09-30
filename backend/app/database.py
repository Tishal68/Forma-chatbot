import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]

@contextmanager
def connect():
    path = Path(os.getenv('DATABASE_PATH', 'data/chat.db'))
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', summary_through INTEGER NOT NULL DEFAULT 0);

        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          role TEXT NOT NULL CHECK(role IN ('user','assistant')),
          content TEXT NOT NULL, created_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'complete', model TEXT,
          sources TEXT,
          web_search INTEGER DEFAULT 0);

        CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id, id);

        CREATE TABLE IF NOT EXISTS attachments (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
          filename TEXT NOT NULL,
          content_type TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          file_path TEXT NOT NULL,
          created_at TEXT NOT NULL,
          extracted_text TEXT,
          page_count INTEGER DEFAULT 0,
          is_image INTEGER DEFAULT 0);

        CREATE INDEX IF NOT EXISTS attachments_conv ON attachments(conversation_id);
        CREATE INDEX IF NOT EXISTS attachments_msg ON attachments(message_id);
        ''')

        # Safely migrate existing tables if columns are missing
        msg_columns = [r['name'] for r in db.execute('PRAGMA table_info(messages)').fetchall()]
        if 'sources' not in msg_columns:
            db.execute('ALTER TABLE messages ADD COLUMN sources TEXT')
        if 'web_search' not in msg_columns:
            db.execute('ALTER TABLE messages ADD COLUMN web_search INTEGER DEFAULT 0')

