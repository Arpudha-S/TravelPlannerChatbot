import sqlite3
from datetime import datetime

CHAT_HISTORY_DB = "chat_history.db"
PERSISTENT_CHAT_ENABLED = True

def init_chat_db():
    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_input TEXT,
            bot_response TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_chat(session_id, user_input, bot_response):
    if not PERSISTENT_CHAT_ENABLED:
        return
    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (session_id, user_input, bot_response, timestamp) VALUES (?, ?, ?, ?)",
              (session_id, user_input, bot_response, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_chat_history(session_id):
    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute("SELECT user_input, bot_response, timestamp FROM chat_history WHERE session_id = ? ORDER BY timestamp", (session_id,))
    history = c.fetchall()
    conn.close()
    return history

def list_all_sessions():
    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute("SELECT DISTINCT session_id FROM chat_history")
    sessions = [row[0] for row in c.fetchall()]
    conn.close()
    return sessions