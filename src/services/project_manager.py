import uuid
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from src.config import PROJECTS_DIR

class ProjectManager:
    """
    Manages project creation, directory structure, and metadata.
    """

    def __init__(self):
        # Ensure base projects directory exists
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str) -> str:
        """
        Creates a new project with a unique ID.
        Sets up the directory structure and saves initial metadata.
        """
        project_id = str(uuid.uuid4())
        project_path = PROJECTS_DIR / project_id
        
        # Create project directory
        project_path.mkdir(parents=True, exist_ok=False)

        # Create metadata
        metadata = {
            "id": project_id,
            "name": name,
            "created_at": None, # Could add timestamp if needed, but keeping it simple as per spec
            "nushalar": []
        }
        
        # Save metadata.json
        metadata_path = project_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return project_id

    def get_project_path(self, project_id: str) -> Path:
        """
        Returns the absolute path to the project directory.
        """
        return PROJECTS_DIR / project_id

    def get_nusha_dir(self, project_id: str, nusha_index: int) -> Path:
        """
        Returns the path for a specific nusha directory (e.g., nusha_1).
        Creates it if it doesn't exist.
        """
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
            raise FileNotFoundError(f"Project {project_id} not found.")

        nusha_dir_name = f"nusha_{nusha_index}" # Using snake_case as implied by standard python conventions, or should I stick to something else? 
        # User said: "get_nusha_dir... İlgili nüshanın (1, 2, 3...) klasör yolunu döner"
        # I will use "nusha_{index}" as a clean directory name.
        
        nusha_path = project_path / nusha_dir_name
        nusha_path.mkdir(exist_ok=True)
        
        return nusha_path

    def list_projects(self) -> List[Dict]:
        """
        Scans the projects directory and returns a list of project metadata.
        """
        projects = []
        if not PROJECTS_DIR.exists():
            return projects

        for item in PROJECTS_DIR.iterdir():
            if item.is_dir():
                metadata_path = item / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            projects.append(metadata)
                    except (json.JSONDecodeError, OSError):
                        # Skip malformed projects
                        continue
        return projects

    def get_metadata(self, project_id: str) -> Dict:
        """
        Reads and returns the metadata for a specific project.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found for project {project_id}")
            
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_nusha_config(self, project_id: str, nusha_index: int) -> Dict:
        """
        Retrieves configuration for a specific Nusha, e.g., DPI settings.
        Returns empty dict if no config exists.
        """
        metadata = self.get_metadata(project_id)
        # Check if 'nusha_configs' key exists, if not return empty
        nusha_configs = metadata.get("nusha_configs", {})
        return nusha_configs.get(str(nusha_index), {})

    def update_nusha_config(self, project_id: str, nusha_index: int, config: Dict):
        """
        Updates the configuration for a specific Nusha in metadata.json.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        if not metadata_path.exists():
             raise FileNotFoundError(f"Metadata not found for project {project_id}")

        # Load existing
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Initialize if missing
        if "nusha_configs" not in metadata:
            metadata["nusha_configs"] = {}
            
        # Update specific nusha config
        # We merge with existing config to not lose other settings
        current_config = metadata["nusha_configs"].get(str(nusha_index), {})
        current_config.update(config)
        
        metadata["nusha_configs"][str(nusha_index)] = current_config
        
        # Save back
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
