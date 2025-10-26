# storage_sqlite.py
import sqlite3
import json
from datetime import datetime
from typing import Optional, List

DB_PATH = "workpolish_records.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    session_id TEXT,
    input_text TEXT,
    language TEXT,
    context TEXT,
    tone TEXT,
    model TEXT,
    subject TEXT,
    polished_text TEXT,
    notes TEXT,
    input_len INTEGER,
    output_len INTEGER
);
"""

INSERT_SQL = """
INSERT INTO records (
    timestamp, session_id, input_text, language, context, tone,
    model, subject, polished_text, notes, input_len, output_len
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

def init_db(path: str = DB_PATH):
    """
    Initialize SQLite DB and return a connection object.
    `check_same_thread=False` helps when Streamlit spins multiple threads.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(CREATE_SQL)
    conn.commit()
    return conn

def save_record(conn,
                session_id: str,
                input_text: str,
                language: str,
                context: str,
                tone: str,
                model: str,
                subject: Optional[str],
                polished_text: str,
                notes: Optional[List[str]]):
    """
    Save one interaction record to the DB.
    notes is stored as a JSON string.
    """
    ts = datetime.utcnow().isoformat()
    notes_json = json.dumps(notes or [], ensure_ascii=False)
    input_len = len(input_text or "")
    output_len = len(polished_text or "")
    conn.execute(INSERT_SQL, (
        ts, session_id, input_text, language, context, tone,
        model, subject or "", polished_text or "", notes_json, input_len, output_len
    ))
    conn.commit()