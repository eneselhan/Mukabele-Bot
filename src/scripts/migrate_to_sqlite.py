import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import PROJECTS_DIR
from src.database import DatabaseManager
from src.services.project_manager import ProjectManager

def migrate_all_projects():
    print("--- MIGRATION START: JSON -> SQLite ---")
    
    db = DatabaseManager() # Will create tahkik_global.db
    pm = ProjectManager()
    
    projects = pm.list_projects()
    print(f"Found {len(projects)} projects to migrate.")
    
    success_count = 0
    fail_count = 0
    
    for proj_meta in projects:
        project_id = proj_meta.get("id")
        name = proj_meta.get("name", "Unknown Project")
        
        print(f"Migrating Project: {name} ({project_id})...")
        
        try:
            # 1. Upsert Project Metadata
            db.upsert_project(project_id, name, proj_meta)
            
            # 2. Iterate Nushas
            # In old system, we just check nusha_1, nusha_2 folders manually or via metadata
            # Let's check directories
            proj_path = pm.get_project_path(project_id)
            nusha_dirs = list(proj_path.glob("nusha_*"))
            
            for n_dir in nusha_dirs:
                try:
                    # Extract index
                    idx = int(n_dir.name.split("_")[1])
                except:
                    continue
                    
                print(f"  -> Processing Nusha {idx}...")
                
                # 3. Read alignment.json
                align_path = n_dir / "alignment.json"
                if align_path.exists():
                    with open(align_path, "r", encoding="utf-8") as f:
                        align_data = json.load(f)
                        
                    lines = align_data.get("aligned", [])
                    print(f"     Found {len(lines)} aligned lines.")
                    
                    # 4. Upsert Lines to DB
                    db.upsert_lines_batch(project_id, idx, lines)
                    print("     Lines inserted to DB.")
                else:
                    print("     No alignment.json found.")
                    
            success_count += 1
            print(f"Project {project_id} Done.\n")
            
        except Exception as e:
            print(f"FAILED to migrate {project_id}: {e}")
            fail_count += 1
            import traceback
            traceback.print_exc()

    print("--- MIGRATION COMPLETED ---")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Database: {db.db_path}")

if __name__ == "__main__":
    migrate_all_projects()
