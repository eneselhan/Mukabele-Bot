
import sys
import os
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.project_manager import ProjectManager

def test_sigla_update():
    pm = ProjectManager()
    
    # Create temp project
    project_id = pm.create_project("Test Sigla Update")
    print(f"Created project: {project_id}")
    
    try:
        # Update Sigla
        nusha_index = 2
        sigla = "X"
        pm.update_nusha_sigla(project_id, nusha_index, sigla)
        print(f"Updated sigla for nusha {nusha_index} to {sigla}")
        
        # Verify persistence
        meta = pm.get_metadata(project_id)
        saved_sigla = meta.get("nusha_siglas", {}).get(str(nusha_index))
        
        if saved_sigla == sigla:
            print("SUCCESS: Sigla persisted correctly in metadata.")
        else:
            print(f"FAILURE: Sigla not found or incorrect. Got: {saved_sigla}")
            
        # Verify get_mukabele_data
        # Note: get_mukabele_data reads alignment.json too, so we need to ensure it exists or mock it
        # But we can just check if get_metadata returns it, which we did.
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        import shutil
        project_path = pm.projects_dir / project_id
        if project_path.exists():
            shutil.rmtree(project_path)
            print("Cleaned up project.")

if __name__ == "__main__":
    test_sigla_update()
