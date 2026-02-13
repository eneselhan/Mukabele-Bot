
import sqlite3
from pathlib import Path

DB_PATH = Path("tahkik_data/projects/tahkik_global.db")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:")
    for t in tables:
        print(t[0])
    conn.close()
except Exception as e:
    print(e)
