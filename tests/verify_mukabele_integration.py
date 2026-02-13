import sys
import os
import json
import shutil
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.project_manager import ProjectManager
from src.database import DatabaseManager

def test_mukabele_integration():
    print("--- Starting Mukabele Integration Verification ---")
    
    # Setup
    pm = ProjectManager()
    project_id = "IntegrationTest_Mukabele"
    
    # Clean up previous run
    if (pm.projects_dir / project_id).exists():
        shutil.rmtree(pm.projects_dir / project_id)
        
    # Clean DB entries
    conn = pm.db.get_connection()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.execute("DELETE FROM aligned_lines WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()
    
    # 1. Create Project
    print(f"Creating project...")
    # create_project returns the UUID
    created_id = pm.create_project("IntegrationTest_Mukabele", ["Test Author"], "Test Lang", "Test Subject", "Test Desc")
    print(f"  Created Project ID: {created_id}")
    
    # Update project_id variable to use the real one for subsequent calls
    project_id = created_id
    
    # 2. Seed Data (DB Only first)
    print("Seeding DB data...")
    lines = [
        {"line_no": 1, "text": "Line 1 DB", "best": {"raw": "Line 1 DB"}},
        {"line_no": 2, "text": "Line 2 DB", "best": {"raw": "Line 2 DB"}},
        {"line_no": 3, "text": "Line 3 DB", "best": {"raw": "Line 3 DB"}}
    ]
    pm.db.upsert_lines_batch(project_id, 1, lines)
    
    # 3. Test get_nusha_alignment (Should fetch from DB)
    print("Testing get_nusha_alignment (DB source)...")
    fetched = pm.get_nusha_alignment(project_id, 1)
    if len(fetched) == 3 and fetched[0]["best"]["raw"] == "Line 1 DB":
        print("  [PASS] Fetched from DB correctly.")
    else:
        print(f"  [FAIL] Fetch mismatch. Got {len(fetched)} items.")
        return

    # 4. Test Update (Dual Write)
    # First ensure file exists to test dual write
    nusha_dir = pm.get_nusha_dir(project_id, 1)
    nusha_dir.mkdir(parents=True, exist_ok=True)
    alignment_path = nusha_dir / "alignment.json"
    
    # Seed file with DIFFERENT data to verify we overwrite it or update it?
    # Logic is: update_nusha_line fetches from DB, updates, saves to DB, then writes DB-state to FS.
    # So FS should become "Line 1 Updated".
    
    print("Testing update_nusha_line...")
    success = pm.update_nusha_line(project_id, 1, 2, "Line 2 Updated")
    if not success:
        print("  [FAIL] update_nusha_line returned False")
        return
        
    # Check DB
    fetched_after = pm.get_nusha_alignment(project_id, 1)
    line_2 = next(l for l in fetched_after if l["line_no"] == 2)
    if line_2["best"]["raw"] == "Line 2 Updated":
        print("  [PASS] DB updated.")
    else:
        print(f"  [FAIL] DB not updated. Value: {line_2['best']['raw']}")
        
    # Check File
    if alignment_path.exists():
        with open(alignment_path, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        f_lines = file_data.get("aligned", [])
        f_line_2 = next((l for l in f_lines if l.get("line_no") == 2), None)
        if f_line_2 and f_line_2.get("best", {}).get("raw") == "Line 2 Updated":
             print("  [PASS] File updated (Dual Write).")
        else:
             print(f"  [FAIL] File content mismatch: {f_line_2}")
    else:
        print("  [FAIL] File not created/updated.")

    # 5. Test Delete
    print("Testing delete_nusha_line (Line 3)...")
    success = pm.delete_nusha_line(project_id, 1, 3)
    if not success:
        print("  [FAIL] delete_nusha_line returned False")
    
    # Check DB
    fetched_del = pm.get_nusha_alignment(project_id, 1)
    if len(fetched_del) == 2:
        print("  [PASS] DB row deleted.")
    else:
        print(f"  [FAIL] DB row not deleted. Count: {len(fetched_del)}")
        
    # Check File
    with open(alignment_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    if len(file_data.get("aligned", [])) == 2:
        print("  [PASS] File item deleted.")
    else:
        print("  [FAIL] File item not deleted.")

    print("--- Verification Complete ---")

if __name__ == "__main__":
    test_mukabele_integration()
