
import sqlite3
from pathlib import Path

DB_PATH = Path("tahkik_data/projects/tahkik_global.db")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(aligned_lines)")
    columns = cursor.fetchall()
    print("Table: aligned_lines")
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(e)
