import sys
from pathlib import Path
import json
import sqlite3
import os

# Add src to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database import DatabaseManager
from src.config import PROJECTS_DIR

def migrate_data():
    print("--- Starting Database Migration ---", flush=True)
    
    db = DatabaseManager()
    
    if not PROJECTS_DIR.exists():
        print("No projects directory found.", flush=True)
        return

    # List only directories
    projects = [p for p in PROJECTS_DIR.iterdir() if p.is_dir()]
    print(f"Found {len(projects)} project folders.", flush=True)
    
    for proj_dir in projects:
        project_id = proj_dir.name
        print(f"\nProcessing Project: {project_id}", flush=True)
        
        # Load Metadata
        meta_path = proj_dir / "metadata.json"
        if not meta_path.exists():
            print(f"  [SKIP] No metadata.json found.", flush=True)
            continue
            
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Failed to read metadata: {e}", flush=True)
            continue
            
        # A. Upsert Project
        try:
            db.upsert_project(project_id, metadata.get("name", ""), metadata)
            print(f"  [OK] Project record synced.", flush=True)
        except Exception as e:
            print(f"  [FAIL] Project upsert failed: {e}", flush=True)
            
        # B. Upsert Nushas
        nusha_configs = metadata.get("nusha_configs", {}) or {}
        nusha_names = metadata.get("nusha_names", {}) or {}
        nusha_siglas = metadata.get("nusha_siglas", {}) or {}
        
        # Identify nushas from filesystem + config
        found_nusha_indices = set()
        
        # 1. From Config
        for idx_str, config in nusha_configs.items():
            try:
                idx = int(idx_str)
                name = nusha_names.get(idx_str, f"Nüsha {idx}")
                
                # Inject Sigla
                if idx_str in nusha_siglas:
                    config["sigla"] = nusha_siglas[idx_str]
                
                db.upsert_nusha(project_id, idx, name, config)
                found_nusha_indices.add(idx)
                print(f"  [OK] Nusha {idx} (from config) synced.", flush=True)
            except Exception as e:
                 print(f"  [FAIL] Nusha {idx_str} upsert failed: {e}", flush=True)

        # 2. From Folders (if missing in config)
        nusha_dirs = list(proj_dir.glob("nusha_*"))
        for nd in nusha_dirs:
            try:
                parts = nd.name.split("_")
                if len(parts) == 2 and parts[1].isdigit():
                    idx = int(parts[1])
                    if idx not in found_nusha_indices:
                        # Infer config from files
                        pdf_files = list(nd.glob("*.pdf"))
                        filename = pdf_files[0].name if pdf_files else "unknown.pdf"
                        config = {"filename": filename}
                        
                        name = nusha_names.get(str(idx), f"Nüsha {idx}")
                        
                        # Inject Sigla
                        if str(idx) in nusha_siglas:
                            config["sigla"] = nusha_siglas[str(idx)]
                            
                        db.upsert_nusha(project_id, idx, name, config)
                        found_nusha_indices.add(idx)
                        print(f"  [OK] Nusha {idx} (from folder) synced.", flush=True)
            except Exception as e:
                print(f"  [FAIL] Folder scan for {nd.name} failed: {e}", flush=True)

        # C. Upsert Footnotes
        footnotes = metadata.get("footnotes", [])
        if footnotes:
            try:
                db.upsert_footnotes(project_id, footnotes)
                print(f"  [OK] Footnotes synced ({len(footnotes)} items).", flush=True)
            except Exception as e:
                print(f"  [FAIL] Footnotes sync failed: {e}", flush=True)
                
        # D. Upsert Aligned Lines
        # Iterate detected nusha indices
        for idx in found_nusha_indices:
            nusha_dir = proj_dir / f"nusha_{idx}"
            align_path = nusha_dir / "alignment.json"
            
            # Fallback for N1 (Legacy root alignment.json)
            if idx == 1 and not align_path.exists():
                root_align = proj_dir / "alignment.json"
                if root_align.exists():
                    align_path = root_align
            
            if align_path.exists():
                try:
                    with open(align_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    lines = data.get("aligned", [])
                    if lines:
                        db.upsert_lines_batch(project_id, idx, lines)
                        print(f"  [OK] Aligned Lines for Nusha {idx} synced ({len(lines)} lines).", flush=True)
                    else:
                        print(f"  [INFO] Nusha {idx} has empty alignment.", flush=True)
                        
                except Exception as e:
                    print(f"  [FAIL] Lines sync failed for Nusha {idx}: {e}", flush=True)

    print("\n--- Migration Completed ---", flush=True)

if __name__ == "__main__":
    migrate_data()
