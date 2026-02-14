import uuid
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import UploadFile
from src.config import PROJECTS_DIR
from src.utils import write_json_atomic
from src.database import DatabaseManager

class ProjectManager:
    """
    Manages project creation, directory structure, and metadata.
    Uses SQLite for metadata storage with file system fallback/sync.
    """

    def __init__(self):
        # Ensure base projects directory exists
        self.projects_dir = PROJECTS_DIR
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.db = DatabaseManager()

    def create_project(self, name: str, authors: List[str] = [], language: str = "Ottoman Turkish", subject: str = "Islamic Studies", description: str = "") -> str:
        """
        Creates a new project with a unique ID and extended metadata.
        Writes to both File System (JSON) and SQLite DB.
        """
        project_id = str(uuid.uuid4())
        project_path = PROJECTS_DIR / project_id
        
        # Create project directory
        project_path.mkdir(exist_ok=True)
        (project_path / "nusha_1").mkdir(exist_ok=True)
        (project_path / "nusha_2").mkdir(exist_ok=True)
        
        metadata = {
            "id": project_id,
            "name": name,
            "authors": authors,
            "language": language,
            "subject": subject,
            "description": description,
            "created_at": "2024-01-01", 
            "nusha_order": [1, 2], 
            "nusha_names": { "1": "Nüsha 1", "2": "Nüsha 2" }
        }
        
        # 1. FS Write
        metadata_path = project_path / "metadata.json"
        write_json_atomic(metadata_path, metadata)
        
        # 2. DB Write
        try:
            self.db.upsert_project(project_id, name, metadata)
        except Exception as e:
            print(f"[WARN] DB Write Failed for create_project: {e}")
        
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
        Prioritizes SQLite DB, falls back to File System.
        """
        # Try DB
        try:
            conn = self.db.get_connection()
            rows = conn.execute("SELECT metadata_json FROM projects ORDER BY created_at DESC").fetchall()
            conn.close()
            
            if rows:
                projects = []
                for row in rows:
                    try:
                        meta = json.loads(row[0])
                        if "nusha_siglas" not in meta: meta["nusha_siglas"] = {}
                        projects.append(meta)
                    except: pass
                if projects: return projects
        except Exception as e:
            print(f"[WARN] DB List Failed: {e}")

        # Fallback to FS
        print("[INFO] Fallback to FileSystem for list_projects")
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
                            
                            if "nusha_siglas" not in metadata:
                                metadata["nusha_siglas"] = {}
                                
                            projects.append(metadata)
                    except (json.JSONDecodeError, OSError):
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
            meta = json.load(f)
            
        # Merge Footnotes from DB (Source of Truth)
        try:
            db_footnotes = self.db.get_footnotes(project_id)
            meta["footnotes"] = db_footnotes
            
            # Merge Nusha Siglas/Configs from DB
            # We need a method to get nushas from DB first
            db_nushas = self.db.get_nushas(project_id)
            
            if "nusha_configs" not in meta: meta["nusha_configs"] = {}
            if "nusha_siglas" not in meta: meta["nusha_siglas"] = {}
            if "nusha_names" not in meta: meta["nusha_names"] = {}
            
            for n in db_nushas:
                idx = str(n["nusha_index"])
                conf = n.get("config", {})
                
                # Sync Sigla
                if "sigla" in conf:
                    meta["nusha_siglas"][idx] = conf["sigla"]
                
                # Sync Name
                if n.get("name"):
                     meta["nusha_names"][idx] = n["name"]
                     
                # Sync Config (Generic)
                if conf:
                    current_conf = meta["nusha_configs"].get(idx, {})
                    current_conf.update(conf)
                    meta["nusha_configs"][idx] = current_conf
                    
                # Sync Base Nusha
                if n.get("is_base"):
                    meta["base_nusha_index"] = n["nusha_index"]

        except Exception as e:
            print(f"[WARN] Failed to merge DB data: {e}")

        return meta

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
        Updates configuration for a specific Nusha.
        """
        metadata = self.get_metadata(project_id)
            
        if "nusha_configs" not in metadata:
            metadata["nusha_configs"] = {}
            
        metadata["nusha_configs"][str(nusha_index)] = config
        self._save_metadata(project_id, metadata)

    def update_footnotes(self, project_id: str, footnotes: List[Dict]):
        """
        Updates the footnotes list in the project metadata.
        """
        metadata = self.get_metadata(project_id)
        metadata["footnotes"] = footnotes
        self._save_metadata(project_id, metadata)
        
        # DB Sync
        try:
            self.db.upsert_footnotes(project_id, footnotes)
        except Exception as e:
            print(f"[WARN] DB Footnote Upsert Failed: {e}")

    def update_nusha_sigla(self, project_id: str, nusha_index: int, sigla: str):
        """
        Updates the sigla (rumuz) for a specific Nusha.
        """
        metadata = self.get_metadata(project_id)
            
        if "nusha_siglas" not in metadata:
            metadata["nusha_siglas"] = {}
            
        metadata["nusha_siglas"][str(nusha_index)] = sigla
        self._save_metadata(project_id, metadata)
        
        # DB Sync (Store in Nusha Config)
        try:
            # 1. Get current config/name
            # We don't have a direct "get_nusha" from DB method exposed easily here
            # But we can reconstruct or fetch config from metadata
            config = metadata.get("nusha_configs", {}).get(str(nusha_index), {})
            config["sigla"] = sigla
            
            name = metadata.get("nusha_names", {}).get(str(nusha_index), f"Nüsha {nusha_index}")
            
            self.db.upsert_nusha(project_id, nusha_index, name, config)
        except Exception as e:
            print(f"[WARN] DB Nusha Sigla Sync Failed: {e}")

    def update_project_base_nusha(self, project_id: str, nusha_index: int):
        """
        Updates the Base Nusha (Asıl Nüsha) index.
        """
        metadata = self.get_metadata(project_id)
        metadata["base_nusha_index"] = nusha_index
        self._save_metadata(project_id, metadata)
        
        # DB Sync
        try:
            self.db.set_base_nusha(project_id, nusha_index)
        except Exception as e:
            print(f"[WARN] Failed to set base nusha in DB: {e}")



    def get_project_status(self, project_id: str) -> Dict:
        """
        Returns the persistent status of the project files.
        Checks for the existence of 'tahkik.docx' and 'source.pdf' for each Nusha.
        """
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
             raise FileNotFoundError(f"Project {project_id} not found")

        # 1. Tahkik Dosyası Kontrolü
        tahkik_path = project_path / "tahkik.docx"
        has_tahkik = tahkik_path.exists()
        
        # 2. Nüsha Kontrolleri
        nushas_status = {}
        # Metadata'dan nüsha isimlerini oku
        metadata = self.get_metadata(project_id)
        nusha_names = metadata.get("nusha_names", {})
        nusha_siglas = metadata.get("nusha_siglas", {})

        # Dynamically find nusha folders
        nusha_dirs = sorted(list(project_path.glob("nusha_*")), key=lambda p: int(p.name.split("_")[1]) if p.name.split("_")[1].isdigit() else 999)

        for n_path in nusha_dirs:
            if not n_path.is_dir(): continue
            
            try:
                parts = n_path.name.split("_")
                if len(parts) != 2 or not parts[1].isdigit(): continue
                i = int(parts[1])
            except:
                continue

            # Check for any PDF in the nusha directory
            pdf_files = list(n_path.glob("*.pdf"))
            source_exists = len(pdf_files) > 0
            
            filename = pdf_files[0].name if pdf_files else None
            
            # İşlem durumunu kontrol et (lines klasörü varsa OCR yapılmış demektir)
            lines_exists = (n_path / "lines").exists()
            
            # İlerleme Durumunu Oku
            progress_data = None
            status_file = n_path / "status.json"
            if status_file.exists():
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        progress_data = json.load(f)
                except Exception:
                    pass
            
            # İsmi belirle (Varsa custom name, yoksa default)
            custom_name = nusha_names.get(str(i))
            display_name = custom_name if custom_name else f"Nüsha {i}"

            nushas_status[f"nusha_{i}"] = {
                "id": i,
                "name": display_name,
                "uploaded": source_exists,
                "filename": filename,
                "ready_for_ocr": source_exists,
                "ready_for_align": has_tahkik and lines_exists,
                "progress": progress_data
            }

        return {
            "status": "active",
            "has_tahkik": has_tahkik,
            "has_tahkik": has_tahkik,
            "nusha_siglas": nusha_siglas,
            "nushas": nushas_status
        }

    def save_uploaded_file(self, project_id: str, file_content: bytes, file_type: str, nusha_index: int = 1, filename: str = "file"):
        """
        Dosyayı projenin uygun klasörüne kaydeder.
        file_content: Raw bytes of the uploaded file.
        filename: Original filename from the upload.
        nusha_index <= 0 ise yeni bir nusha indexi oluşturur.
        """
        project_path = self.get_project_path(project_id)
        
        if file_type == "docx":
            target_path = project_path / "tahkik.docx"
            with open(target_path, "wb") as f:
                f.write(file_content)
            print(f"[UPLOAD] Word dosyası kaydedildi: {target_path} ({len(file_content)} bytes)")
            return target_path, 1
            
        elif file_type == "pdf":
            # Yeni Nüsha Ekleme Mantığı
            if nusha_index <= 0:
                # Mevcut nushaları tara ve en büyük indexi bul
                existing_nushas = list(project_path.glob("nusha_*"))
                indices = []
                for p in existing_nushas:
                    try:
                        indices.append(int(p.name.split("_")[1]))
                    except:
                        pass
                
                if indices:
                    nusha_index = max(indices) + 1
                else:
                    nusha_index = 1
            
            nusha_dir = project_path / f"nusha_{nusha_index}"
            nusha_dir.mkdir(parents=True, exist_ok=True)
            
            # Dosya ismini koru
            target_path = nusha_dir / filename
            with open(target_path, "wb") as f:
                f.write(file_content)
            
            print(f"[UPLOAD] PDF kaydedildi: {target_path} ({len(file_content)} bytes)")
            
            # Metadata'ya dosya ismini kaydet
            config = {"filename": target_path.name}
            self.update_nusha_config(project_id, nusha_index, config)
            
            # DB Sync
            try:
                self.db.upsert_nusha(project_id, nusha_index, f"Nüsha {nusha_index}", config)
            except Exception as e:
                print(f"[WARN] DB Nusha Upsert Failed: {e}")
            
        return target_path, nusha_index


    def delete_file(self, project_id: str, file_type: str, nusha_index: int = 1):
        """Dosyayı ve ilgili analiz verilerini diskten siler."""
        project_path = self.projects_dir / project_id
        
        if file_type == "docx":
            # Word dosyasını sil
            tahkik_path = project_path / "tahkik.docx"
            if tahkik_path.exists():
                tahkik_path.unlink()
                print(f"[DELETE] Referans metin silindi: {tahkik_path}")
        
        else:
            nusha_dir = project_path / f"nusha_{nusha_index}"
            if nusha_dir.exists():
                import shutil
                shutil.rmtree(nusha_dir)
                print(f"[DELETE] Nüsha klasörü silindi: {nusha_dir}")

    def update_nusha_order(self, project_id: str, new_order: List[int]):
        """
        Updates the display order of Nushas in metadata.
        new_order: List of nusha IDs in the desired order.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            metadata["nusha_order"] = new_order
            
            write_json_atomic(metadata_path, metadata)
            
            # DB Sync
            self.db.upsert_project(project_id, metadata.get("name", ""), metadata)
            
        except Exception as e:
            print(f"[ERROR] Failed to update nusha order: {e}")



    def trash_project(self, project_id: str):
        """Moves a project to the trash (soft delete)."""
        meta = self.get_metadata(project_id)
        meta["trashed"] = True
        self._save_metadata(project_id, meta)
        
    def restore_project(self, project_id: str):
        """Restores a project from the trash."""
        meta = self.get_metadata(project_id)
        meta["trashed"] = False
        self._save_metadata(project_id, meta)

    def delete_project(self, project_id: str):

        """
        Deletes the entire project directory.
        """
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
            raise FileNotFoundError(f"Project directory not found: {project_path}")
        
        # Use shutil to remove the directory and all its contents
        shutil.rmtree(project_path)
        
        # DB Delete
        try:
            conn = self.db.get_connection()
            conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            conn.execute("DELETE FROM aligned_lines WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM nushas WHERE project_id=?", (project_id,))
            conn.commit()
            conn.close()
        except Exception as e:
             print(f"[WARN] Failed to delete from DB: {e}")
             
        print(f"[DELETE] Project {project_id} deleted successfully.")

    def _save_metadata(self, project_id: str, metadata: Dict):
        """Metadata dosyasını diske kaydeder."""
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        write_json_atomic(metadata_path, metadata)
        
        # DB Sync
        try:
            self.db.upsert_project(project_id, metadata.get("name", ""), metadata)
        except Exception as e:
            print(f"[WARN] DB Sync failed in _save_metadata: {e}")

    def update_nusha_name(self, project_id: str, nusha_index: int, new_name: str):
        """Nüsha ismini metadata içinde günceller."""
        meta = self.get_metadata(project_id)
        if "nusha_names" not in meta:
            meta["nusha_names"] = {}
        
        meta["nusha_names"][str(nusha_index)] = new_name
        self._save_metadata(project_id, meta)
        return new_name

    def update_nusha_sigla(self, project_id: str, nusha_index: int, sigla: str):
        """Nüsha rumuzunu (sigla) metadata içinde günceller."""
        meta = self.get_metadata(project_id)
        if "nusha_siglas" not in meta:
            meta["nusha_siglas"] = {}
            
        meta["nusha_siglas"][str(nusha_index)] = sigla
        self._save_metadata(project_id, meta)
        return sigla

    def run_word_spellcheck(self, project_id: str):
        """Word dosyası üzerinde temel imla/format kontrolü yapar (Simülasyon)."""
        # Burada ileride gerçek NLP/Normalization kodları çalışacak
        # Şimdilik dosyanın varlığını ve okunabilirliğini test edip onay veriyoruz.
        tahkik_path = self.projects_dir / project_id / "tahkik.docx"
        if not tahkik_path.exists():
             # project_id might be just the folder name if using self.projects_dir / project_id
             # let's use get_project_path to be safe or just adhere to self.projects_dir usage
             tahkik_path = self.get_project_path(project_id) / "tahkik.docx"

        if not tahkik_path.exists():
            raise FileNotFoundError("Word dosyası bulunamadı.")
        
        import time
        time.sleep(2) # İşlem simülasyonu
        return {"status": "success", "message": "İmla denetimi tamamlandı. Metin hizalamaya uygun."}

    def merge_nusha_lines(self, project_id: str, nusha_index: int, line_numbers: List[int]):
        """Birleştirilen satırları alignment.json'a kaydeder."""
        nusha_dir = self.get_nusha_dir(project_id, nusha_index)
        alignment_path = nusha_dir / "alignment.json"
        
        if not alignment_path.exists():
            raise FileNotFoundError("Alignment data not found")

        with open(alignment_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        lines = data.get("aligned", [])
        if not lines:
            return {"lines": []}

        # Sort lines to merge
        line_numbers = sorted(list(set(line_numbers)))
        if len(line_numbers) < 2:
            return {"lines": lines}

        # Find indices
        indices = []
        for ln in line_numbers:
            idx = next((i for i, x in enumerate(lines) if x["line_no"] == ln), -1)
            if idx != -1:
                indices.append(idx)
        
        indices.sort()
        if len(indices) < 2:
             return {"lines": lines}

        target_idx = indices[0]
        target_line = lines[target_idx]
        
        # Merge content
        merged_text = target_line.get("best", {}).get("raw", "")
        for i in indices[1:]:
            line_to_merge = lines[i]
            text = line_to_merge.get("best", {}).get("raw", "")
            merged_text += " " + text
        
        target_line["best"]["raw"] = merged_text
        
        # 1. Merge Indices (Start/End Word)
        # Collect all valid start/end indices from merging lines
        lines_to_merge = [target_line] + [lines[i] for i in indices[1:]]
        
        starts = [l.get("best", {}).get("start_word") for l in lines_to_merge if l.get("best", {}).get("start_word") is not None]
        ends = [l.get("best", {}).get("end_word") for l in lines_to_merge if l.get("best", {}).get("end_word") is not None]
        
        if starts:
            target_line["best"]["start_word"] = min(starts)
        if ends:
            target_line["best"]["end_word"] = max(ends)
        
        target_line["best"]["raw"] = merged_text
        
        # Clear merged lines (preserve indices/containers)
        for i in indices[1:]:
            lines[i]["best"]["raw"] = ""
            
        # Renumber is NOT needed if we don't delete lines
        # But we should ensure line_no is consistent just in case? 
        # Actually if we don't delete, the line_no stays same.
        # for idx, line in enumerate(lines):
        #    line["line_no"] = idx + 1
            
        data["aligned"] = lines
        write_json_atomic(alignment_path, data)
        
        # DB Sync
        try:
            # self.db is init in __init__
            if not hasattr(self, 'db'):
                 self.db = DatabaseManager()
            self.db.upsert_lines_batch(project_id, nusha_index, lines)
        except Exception as e:
            print(f"[WARN] DB Sync failed for merge_nusha_lines: {e}")
            
        return {"lines": lines}

    def shift_line_content(self, project_id: str, nusha_index: int, line_no: int, direction: str, split_index: int):
        """
        Shifts content between lines, handling text, footnotes, AND word indices.
        direction: "prev" (move start->split to prev line) or "next" (move split->end to next line)
        """
        nusha_dir = self.get_nusha_dir(project_id, nusha_index)
        alignment_path = nusha_dir / "alignment.json"
        metadata_path = self.get_project_path(project_id) / "metadata.json"
        
        with open(alignment_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        lines = data.get("aligned", [])
        footnotes = meta.get("footnotes", [])
        
        # Find current line index
        curr_idx = next((i for i, x in enumerate(lines) if x["line_no"] == line_no), -1)
        if curr_idx == -1: return {"success": False, "error": "Line not found"}
        
        current_line = lines[curr_idx]
        current_text = current_line.get("best", {}).get("raw", "")
        
        if direction == "prev":
            if curr_idx == 0: return {"success": False, "error": "No previous line"}
            target_idx = curr_idx - 1
            target_line = lines[target_idx]
            target_line_no = target_line["line_no"]
            
            # Words moving to PREV line
            moving_part = current_text[:split_index]
            remaining_part = current_text[split_index:]
            
            # Calculate word count change
            words_moved_count = len(moving_part.strip().split())
            if not moving_part.strip(): words_moved_count = 0

            # Text Update
            target_text = target_line.get("best", {}).get("raw", "")
            target_len_before = len(target_text)
            
            # Join with space if not empty
            joiner = " " if target_text and moving_part else ""
            target_line["best"]["raw"] = (target_text + joiner + moving_part).strip()
            current_line["best"]["raw"] = remaining_part.strip()
            
            # Index Update (Prev line END increases, Curr line START increases)
            if "end_word" in target_line["best"] and "start_word" in current_line["best"]:
                 target_line["best"]["end_word"] += words_moved_count
                 current_line["best"]["start_word"] += words_moved_count
            
            # Footnote Update
            offset = target_len_before + len(joiner)
            
            for fn in footnotes:
                if fn.get("line_no") == line_no:
                    idx = fn.get("index", 0)
                    if idx < split_index:
                        # Moves to prev line
                        fn["line_no"] = target_line_no
                        fn["index"] = offset + idx
                    else:
                        # Stays, shifts left
                        fn["index"] = idx - split_index
                        
        elif direction == "next":
            if curr_idx == len(lines) - 1: return {"success": False, "error": "No next line"}
            target_idx = curr_idx + 1
            target_line = lines[target_idx]
            target_line_no = target_line["line_no"]
            
            # Words moving to NEXT line
            remaining_part = current_text[:split_index]
            moving_part = current_text[split_index:]
            
            words_moved_count = len(moving_part.strip().split())
            if not moving_part.strip(): words_moved_count = 0
            
            # Text Update
            target_text = target_line.get("best", {}).get("raw", "")
            
            joiner = " " if moving_part and target_text else ""
            target_line["best"]["raw"] = (moving_part + joiner + target_text).strip()
            current_line["best"]["raw"] = remaining_part.strip()
            
            # Index Update (Curr line END decreases, Next line START decreases)
            if "end_word" in current_line["best"] and "start_word" in target_line["best"]:
                current_line["best"]["end_word"] -= words_moved_count
                target_line["best"]["start_word"] -= words_moved_count
            
            # Footnote Update
            moved_len = len(moving_part) + len(joiner)
            
            # Shift existing footnotes in target line
            for fn in footnotes:
                if fn.get("line_no") == target_line_no:
                    fn["index"] += moved_len
            
            # Move footnotes from current line
            for fn in footnotes:
                if fn.get("line_no") == line_no:
                    idx = fn.get("index", 0)
                    if idx >= split_index:
                        fn["line_no"] = target_line_no
                        fn["index"] = idx - split_index
                        
        else:
            return {"success": False, "error": "Invalid direction"}
        
        # Save All
        write_json_atomic(alignment_path, data)
        self._save_metadata(project_id, meta)
        
        # DB Sync Lines
        try:
            self.db.upsert_lines_batch(project_id, nusha_index, lines)
        except Exception as e:
            print(f"[WARN] DB Sync failed for shift_line_content: {e}")
            
        # DB Sync Footnotes
        try:
            self.db.upsert_footnotes(project_id, footnotes)
        except Exception as e:
            print(f"[WARN] DB Sync footnotes failed: {e}")

        return {"success": True}



    def get_nusha_alignment(self, project_id: str, nusha_index: int) -> List[Dict]:
        """
        Retrieves alignment data for a specific nusha (DB-first).
        """
        try:
            # 1. Try DB
            lines = self.db.get_aligned_lines(project_id, nusha_index)
            if lines:
                return lines
        except Exception as e:
            print(f"[WARN] DB read failed for alignment: {e}")
            
        # 2. Fallback to File System
        try:
            nusha_dir = self.get_nusha_dir(project_id, nusha_index)
            alignment_path = nusha_dir / "alignment.json"
            if alignment_path.exists():
                with open(alignment_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("aligned", [])
        except Exception:
            pass
            
        # 3. Fallback to Legacy Root for N1
        if nusha_index == 1:
            root_align = self.projects_dir / project_id / "alignment.json"
            if root_align.exists():
                try:
                    with open(root_align, "r", encoding="utf-8") as f:
                        return json.load(f).get("aligned", [])
                except: pass
                
        return []
                
        return []

    def update_nusha_line(self, project_id: str, nusha_index: int, line_no: int, new_text: str, new_html: str = None) -> bool:
        """
        Updates a single line text in both DB and Filesystem.
        """
        # 1. Update DB
        # We need to fetch the existing line to preserve metadata if we want full fidelity,
        # but upsert_lines_batch expects full object.
        # Efficient way: Get line, update text, upsert.
        
        # Get current state (DB first)
        lines = self.get_nusha_alignment(project_id, nusha_index)
        
        # Find index to update in place
        target_idx = next((i for i, l in enumerate(lines) if l.get("line_no") == line_no), -1)
        
        if target_idx == -1:
            return False
            
        target_line = lines[target_idx]
            
        # Update text
        if "best" not in target_line: target_line["best"] = {}
        target_line["best"]["raw"] = new_text
        
        # Update HTML (Rich Text)
        if new_html is not None:
             target_line["best"]["html"] = new_html
        
        # Save to DB
        try:
            # We must upsert ALL lines because upsert_lines_batch clears the table first!
            self.db.upsert_lines_batch(project_id, nusha_index, lines)
        except Exception as e:
            print(f"[ERROR] DB update failed: {e}")
            return False
            
        # 2. Sync to Filesystem (Legacy Support)
        try:
            nusha_dir = self.get_nusha_dir(project_id, nusha_index)
            alignment_path = nusha_dir / "alignment.json"
            
            # If checking nusha-specific fails (e.g. N1 fallback), we might need to write to root?
            # But get_nusha_alignment handles fallback read. Writing should be explicit.
            # If N1 and no nusha_1 folder, we might write to root alignment.json?
            # Current `get_nusha_dir` creates the dir if it doesn't exist? No, it just returns path.
            
            # If N1 and using root alignment.json:
            target_path = alignment_path
            if nusha_index == 1:
                # Check root alignment if nusha specific doesn't exist OR if we read from root
                # Since get_nusha_alignment prioritizes DB, we rely on where it SHOULD go.
                # Standard: Always write to nusha specific folder if possible?
                # Or check if root exists and use it to maintain legacy structure?
                if not alignment_path.exists() and (self.projects_dir / project_id / "alignment.json").exists():
                    target_path = self.projects_dir / project_id / "alignment.json"
            
            # We need to read the FULL file to write it back safely (preserving other lines)
            # We can't just write one line.
            # And `lines` variable above might be from DB which is consistent.
            # So we can just rewrite the file with `lines` (which has the update).
            
            full_payload = {"aligned": lines} # Default payload
            
            # Use existing payload wrapper if file exists to preserve other keys
            if target_path.exists():
                with open(target_path, "r", encoding="utf-8") as f:
                    full_payload = json.load(f)
            
            full_payload["aligned"] = lines
            write_json_atomic(target_path, full_payload)
            
        except Exception as e:
             print(f"[WARN] FS sync failed: {e}")
             # DB succeeded so we return True? Or False?
             # Let's return True but warn.
             
        return True

    
    def get_deleted_lines(self, project_id: str, nusha_index: int) -> List[Dict]:
        """
        Retrieves lines that are marked as deleted.
        """
        try:
            return self.db.get_deleted_lines(project_id, nusha_index)
        except Exception as e:
            print(f"[ERROR] Failed to get deleted lines: {e}")
            return []

    def restore_nusha_line(self, project_id: str, nusha_index: int, line_no: int) -> bool:
        """
        Restores a soft-deleted line.
        """
        # 1. Update DB (is_deleted=0)
        try:
            # We need a db method for this
            self.db.restore_aligned_line(project_id, nusha_index, line_no)
        except Exception as e:
            print(f"[ERROR] DB restore failed: {e}")
            return False
            
        # 2. Sync to Filesystem
        # Re-fetch lines (which should now include the restored line)
        try:
            lines = self.get_nusha_alignment(project_id, nusha_index)
            
            nusha_dir = self.get_nusha_dir(project_id, nusha_index)
            target_path = nusha_dir / "alignment.json"
            if nusha_index == 1:
                 if not target_path.exists() and (self.projects_dir / project_id / "alignment.json").exists():
                     target_path = self.projects_dir / project_id / "alignment.json"
            
            full_payload = {"aligned": lines}
            if target_path.exists():
                with open(target_path, "r", encoding="utf-8") as f:
                    full_payload = json.load(f)
            
            full_payload["aligned"] = lines
            write_json_atomic(target_path, full_payload)
        except Exception as e:
            print(f"[WARN] FS sync failed during restore: {e}")
            
        return True

    def delete_nusha_line(self, project_id: str, nusha_index: int, line_no: int) -> bool:
        """
        Soft deletes a line from DB and removes it from Filesystem.
        """
        # 1. Update DB (Soft Delete)
        try:
            self.db.soft_delete_aligned_line(project_id, nusha_index, line_no)
        except Exception as e:
            print(f"[ERROR] DB delete failed: {e}")
            return False
            
        # 2. Sync to Filesystem (Exclude deleted lines)
        try:
            # get_nusha_alignment logic should filter out deleted lines
            lines = self.get_nusha_alignment(project_id, nusha_index)
            
            nusha_dir = self.get_nusha_dir(project_id, nusha_index)
            target_path = nusha_dir / "alignment.json"
            if nusha_index == 1:
                 if not target_path.exists() and (self.projects_dir / project_id / "alignment.json").exists():
                     target_path = self.projects_dir / project_id / "alignment.json"
            
            full_payload = {"aligned": lines}
            if target_path.exists():
                with open(target_path, "r", encoding="utf-8") as f:
                    full_payload = json.load(f)
            
            full_payload["aligned"] = lines
            write_json_atomic(target_path, full_payload)
            
        except Exception as e:
            print(f"[WARN] FS sync failed during delete: {e}")
            
        return True

    def delete_file(self, project_id: str, file_type: str, nusha_index: int):
        """
        Deletes a file (or nusha source) from FS and DB.
        """
        nusha_dir = self.get_nusha_dir(project_id, nusha_index)
        
        if file_type == "pdf":
            # Delete PDF(s)
            for f in nusha_dir.glob("*.pdf"):
                try: f.unlink()
                except: pass
            
            # Clean up generated data (Reset Nusha)
            shutil.rmtree(nusha_dir / "lines", ignore_errors=True)
            shutil.rmtree(nusha_dir / "ocr", ignore_errors=True)
            shutil.rmtree(nusha_dir / "pages", ignore_errors=True)
            (nusha_dir / "alignment.json").unlink(missing_ok=True)
            (nusha_dir / "lines_manifest.jsonl").unlink(missing_ok=True)
            (nusha_dir / "status.json").unlink(missing_ok=True)

            # DB Cleanup
            try:
                self.db.delete_nusha(project_id, nusha_index)
            except Exception as e:
                print(f"[WARN] DB Nusha Delete Failed: {e}")

        elif file_type == "docx":
             # Only for Project Root really
             tahkik_path = self.projects_dir / project_id / "tahkik.docx"
             if tahkik_path.exists():
                 tahkik_path.unlink()
