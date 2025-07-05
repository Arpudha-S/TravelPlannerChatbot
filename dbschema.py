import sqlite3
DB_NAME = "travel_data.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )''')


    c.execute('''CREATE TABLE IF NOT EXISTS travel_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        place TEXT,
        category TEXT,
        summary TEXT,
        source TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute("INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)", ("admin", "admin123"))
    conn.commit()
    conn.close()

def save_scraped_data(place, category, summary, source):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO travel_info (place, category, summary, source)
                 VALUES (?, ?, ?, ?)''', (place, category, summary, source))
    conn.commit()
    conn.close()

def get_all_scraped_data(filter_place=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if filter_place:
        c.execute("SELECT * FROM travel_info WHERE place LIKE ?", ('%' + filter_place + '%',))
    else:
        c.execute("SELECT * FROM travel_info")
    rows = c.fetchall()
    conn.close()
    return rows

def verify_admin(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user