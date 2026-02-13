import requests
import json
import sqlite3
from pathlib import Path
import sys
import os

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import PROJECTS_DIR

API_URL = "http://127.0.0.1:8000/api/projects"
DB_PATH = PROJECTS_DIR / "tahkik_global.db"

def verify_nusha_delete():
    print("--- Starting Nusha Delete Verification ---", flush=True)
    print(f"Using DB Path: {DB_PATH}", flush=True)
    
    # 1. Create Project
    headers = {"Content-Type": "application/json"}

    payload = {
        "name": "Nusha Delete Test",
        "authors": ["Tester"],
        "language": "Ottoman",
        "subject": "Test",
        "description": "Temp"
    }
    
    res = requests.post(API_URL, json=payload, headers=headers)
    if res.status_code != 200:
        print("Create failed", flush=True)
        return
    
    project_id = res.json()["id"]
    print(f"Created Project: {project_id}", flush=True)
    
    # 2. Simulate Nusha in DB
    print("Inserting fake nusha into DB...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO nushas (project_id, nusha_index, name) VALUES (?, ?, ?)", (project_id, 1, "Fake Nusha"))
        conn.execute("INSERT INTO aligned_lines (project_id, nusha_index, line_no, ref_text, ocr_text) VALUES (?, ?, ?, ?, ?)", 
                     (project_id, 1, 1, "Ref", "OCR"))
        conn.commit()
    finally:
        conn.close()
        
    # Verify insertion
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM nushas WHERE project_id=? AND nusha_index=?", (project_id, 1)).fetchone()
    conn.close()
    if not row:
        print("FAILED: Manual DB insertion failed.", flush=True)
        return
    print("Fake nusha inserted.", flush=True)

    # 3. Call Delete Nusha API
    print("Calling DELETE /files (pdf)...", flush=True)
    del_url = f"{API_URL}/{project_id}/files?file_type=pdf&nusha_index=1"
    res = requests.delete(del_url)
    if res.status_code != 200:
        print(f"FAILED: Delete API failed: {res.text}", flush=True)
        return
    print("Delete API returned success.", flush=True)
    
    # 4. Verify Gone from DB
    conn = sqlite3.connect(DB_PATH)
    nusha_row = conn.execute("SELECT * FROM nushas WHERE project_id=? AND nusha_index=?", (project_id, 1)).fetchone()
    lines_row = conn.execute("SELECT * FROM aligned_lines WHERE project_id=? AND nusha_index=?", (project_id, 1)).fetchone()
    conn.close()
    
    if nusha_row:
        print("FAILED: Nusha still exists in DB 'nushas' table.", flush=True)
    elif lines_row:
        print("FAILED: Aligned lines still exist in DB 'aligned_lines' table.", flush=True)
    else:
        print("SUCCESS: Nusha and Lines removed from DB.", flush=True)
        
    # Cleanup Project
    requests.delete(f"{API_URL}/{project_id}")
    print("Project cleaned up.", flush=True)

if __name__ == "__main__":
    verify_nusha_delete()
