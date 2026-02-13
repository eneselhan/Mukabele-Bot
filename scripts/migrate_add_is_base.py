
import sqlite3
from pathlib import Path

DB_PATH = Path("tahkik_data/projects/tahkik_global.db")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check if column exists
    cursor.execute("PRAGMA table_info(nushas)")
    columns = [col[1] for col in cursor.fetchall()]
    if "is_base" not in columns:
        print("Adding is_base column...")
        cursor.execute("ALTER TABLE nushas ADD COLUMN is_base BOOLEAN DEFAULT 0")
        conn.commit()
        print("Column added.")
    else:
        print("Column is_base already exists.")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
