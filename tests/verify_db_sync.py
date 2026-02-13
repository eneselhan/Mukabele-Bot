import sys
import json
import shutil
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.project_manager import ProjectManager
from src.database import DatabaseManager

def test_db_sync():
    print("--- STARTING DB SYNC VERIFICATION ---")
    pm = ProjectManager()
    db = DatabaseManager()
    
    # 1. Create Project
    print("> Creating Project...")
    pid = pm.create_project("DB Test Project", authors=["Tester"])
    print(f"  Project ID: {pid}")
    
    # Verify FS
    proj_path = pm.get_project_path(pid)
    meta_path = proj_path / "metadata.json"
    if not meta_path.exists():
        print("  [FAIL] FS Metadata not created.")
        return
    else:
        print("  [PASS] FS Metadata created.")
        
    # Verify DB
    conn = db.get_connection()
    row = conn.execute("SELECT name FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    
    if row and row[0] == "DB Test Project":
        print("  [PASS] DB Project created.")
    else:
        print(f"  [FAIL] DB Project not found or name mismatch. Row: {row}")
        
    # 2. Update Metadata (Nusha Name)
    print("\n> Updating Nusha Name...")
    pm.update_nusha_name(pid, 1, "Updated Nusha 1")
    
    # Verify FS
    with open(meta_path, "r") as f:
        meta = json.load(f)
    if meta["nusha_names"]["1"] == "Updated Nusha 1":
        print("  [PASS] FS Metadata updated.")
    else:
        print("  [FAIL] FS Metadata not updated.")
        
    # Verify DB
    conn = db.get_connection()
    row = conn.execute("SELECT metadata_json FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    
    db_meta = json.loads(row[0])
    if db_meta["nusha_names"]["1"] == "Updated Nusha 1":
        print("  [PASS] DB Metadata updated.")
    else:
        print("  [FAIL] DB Metadata not updated.")

    # 3. Clean up
    print("\n> Cleaning up...")
    pm.delete_project(pid)
    
    if not proj_path.exists():
        print("  [PASS] FS Deleted.")
    
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        print("  [PASS] DB Deleted.")
    else:
        print("  [FAIL] DB Not Deleted.")

    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    test_db_sync()
