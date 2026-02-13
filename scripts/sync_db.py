import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.database import DatabaseManager
from src.services.project_manager import ProjectManager
from src.config import PROJECTS_DIR

def sync_all_projects():
    print("Starting DB Synchronization...")
    pm = ProjectManager()
    db = DatabaseManager()
    
    # Force FS read by bypassing ProjectManager methods that prefer DB
    if not PROJECTS_DIR.exists():
        print("No projects directory found.")
        return

    projects_found = 0
    for item in PROJECTS_DIR.iterdir():
        if item.is_dir():
            metadata_path = item / "metadata.json"
            if metadata_path.exists():
                projects_found += 1
                try:
                    # 1. Sync Project Metadata
                    print(f"Syncing Project: {item.name}")
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        import json
                        meta = json.load(f)
                    
                    project_id = meta.get("id", item.name)
                    pm.db.upsert_project(project_id, meta.get("name", "Untitled"), meta)
                    
                    # 2. Sync Nushas
                    nusha_configs = meta.get("nusha_configs", {})
                    nusha_names = meta.get("nusha_names", {})
                    
                    # Detect nusha folders
                    nusha_dirs = list(item.glob("nusha_*"))
                    for n_dir in nusha_dirs:
                        try:
                            parts = n_dir.name.split("_")
                            if len(parts) != 2 or not parts[1].isdigit(): continue
                            idx = int(parts[1])
                            
                            idx_str = str(idx)
                            config = nusha_configs.get(idx_str, {})
                            name = nusha_names.get(idx_str, f"Nüsha {idx}")
                            
                            pm.db.upsert_nusha(project_id, idx, name, config)
                            
                            # 3. Sync Aligned Lines
                            alignment_path = n_dir / "alignment.json"
                            if alignment_path.exists():
                                with open(alignment_path, "r", encoding="utf-8") as af:
                                    idata = json.load(af)
                                    lines = idata.get("aligned", [])
                                    if lines:
                                        print(f"  - Syncing {len(lines)} lines for Nüsha {idx}")
                                        pm.db.upsert_lines_batch(project_id, idx, lines)
                        except Exception as ne:
                            print(f"  [Error] Nusha {n_dir.name}: {ne}")

                    # 4. Sync Footnotes
                    # Footnotes are usually in project metadata or specific file?
                    # ProjectManager.get_metadata merges them from DB.
                    # Logic in PM.update_footnotes writes to metadata["footnotes"]
                    footnotes = meta.get("footnotes", [])
                    if footnotes:
                        print(f"  - Syncing {len(footnotes)} footnotes")
                        pm.db.upsert_footnotes(project_id, footnotes)

                except Exception as e:
                    print(f"[ERROR] Failed to sync project {item.name}: {e}")

    print(f"\nSync Complete. Processed {projects_found} projects.")

if __name__ == "__main__":
    sync_all_projects()
