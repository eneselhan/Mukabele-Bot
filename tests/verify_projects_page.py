import requests
import json
import time
from pathlib import Path

API_URL = "http://127.0.0.1:8000/api/projects"

def test_project_lifecycle():
    print("--- Starting Project Lifecycle Verification ---")
    
    # 1. Create Project
    headers = {"Content-Type": "application/json"}
    payload = {
        "name": "Lifecycle Test Project",
        "authors": ["Test Bot"],
        "language": "Ottoman Turkish",
        "subject": "Testing",
        "description": "A temporary project for verification."
    }
    
    print(f"[1] Creating project...")
    try:
        res = requests.post(API_URL, json=payload, headers=headers)
        if res.status_code != 200:
            print(f"FAILED: Create project failed. {res.text}")
            return
        
        data = res.json()
        project_id = data["id"]
        print(f"SUCCESS: Project created with ID {project_id}")
    except Exception as e:
        print(f"FAILED: Connection Error: {e}")
        return

    # 2. Verify Active List
    print(f"[2] Checking Active List...")
    res = requests.get(API_URL)
    projects = res.json()
    found = any(p["id"] == project_id for p in projects)
    if not found:
        print("FAILED: Project not found in active list (trashed=False).")
        return
    print("SUCCESS: Project found in active list.")
    
    # 3. Trash Project
    print(f"[3] Trashing Project {project_id}...")
    trash_url = f"{API_URL}/{project_id}/trash"
    res = requests.post(trash_url)
    if res.status_code != 200:
        print(f"FAILED: Trash failed. {res.text}")
        return
    print("SUCCESS: Trash request accepted.")
    
    # 4. Verify NOT in Active List
    print(f"[4] Verifying removal from Active List...")
    res = requests.get(API_URL)
    projects = res.json()
    if any(p["id"] == project_id for p in projects):
        print("FAILED: Project still visible in active list after trash.")
        # Attempt manual cleanup if test fails here
        requests.delete(f"{API_URL}/{project_id}")
        return
    print("SUCCESS: Project removed from active list.")
    
    # 5. Verify IN Trashed List
    print(f"[5] Verifying presence in Trashed List...")
    res = requests.get(API_URL, params={"trashed": "true"})
    projects = res.json()
    found_in_trash = any(p["id"] == project_id for p in projects)
    if not found_in_trash:
        print("FAILED: Project not found in trashed list.")
        requests.delete(f"{API_URL}/{project_id}")
        return
    print("SUCCESS: Project found in trashed list.")
    
    # 6. Restore Project
    print(f"[6] Restoring Project...")
    restore_url = f"{API_URL}/{project_id}/restore"
    res = requests.post(restore_url)
    if res.status_code != 200:
         print(f"FAILED: Restore failed. {res.text}")
         return
    print("SUCCESS: Restore request accepted.")
    
    # 7. Verify Active List Again
    print(f"[7] Verifying return to Active List...")
    res = requests.get(API_URL)
    if not any(p["id"] == project_id for p in res.json()):
        print("FAILED: Project not in active list after restore.")
        return
    print("SUCCESS: Project back in active list.")
    
    # 8. Permanent Delete
    print(f"[8] Permanently Deleting Project...")
    del_url = f"{API_URL}/{project_id}"
    res = requests.delete(del_url)
    if res.status_code != 200:
        print(f"FAILED: Delete failed. {res.text}")
        return
    print("SUCCESS: Project deleted.")
    
    # 9. Verify Gone Forever
    print(f"[9] Verifying Final Cleanup...")
    res = requests.get(API_URL)
    active = res.json()
    res = requests.get(API_URL, params={"trashed": "true"})
    trashed = res.json()
    
    if any(p["id"] == project_id for p in active) or any(p["id"] == project_id for p in trashed):
        print("FAILED: Project still exists somewhere.")
        return
        
    print("SUCCESS: Project completely removed.")
    print("--- Verification Completed Successfully ---")

if __name__ == "__main__":
    test_project_lifecycle()
