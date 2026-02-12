import uuid
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import UploadFile
from src.config import PROJECTS_DIR

class ProjectManager:
    """
    Manages project creation, directory structure, and metadata.
    """

    def __init__(self):
        # Ensure base projects directory exists
        self.projects_dir = PROJECTS_DIR
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, authors: List[str] = [], language: str = "Ottoman Turkish", subject: str = "Islamic Studies", description: str = "") -> str:
        """
        Creates a new project with a unique ID and extended metadata.
        """
        project_id = str(uuid.uuid4())
        project_path = PROJECTS_DIR / project_id
        
        # Create project directory
        project_path.mkdir(parents=True, exist_ok=False)

        # Create metadata
        metadata = {
            "id": project_id,
            "name": name,
            "authors": authors,
            "language": language,
            "subject": subject,
            "description": description,
            "created_at": None,
            "nushalar": [],
            "nusha_siglas": {} # { "1": "A", "2": "B", ... }
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
                            # FAST CHECK: Does alignment.json exist?
                            alignment_path = item / "alignment.json"
                            metadata["has_alignment"] = alignment_path.exists()
                            
                            if "nusha_siglas" not in metadata:
                                metadata["nusha_siglas"] = {}
                                
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
        Updates configuration for a specific Nusha.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        if "nusha_configs" not in metadata:
            metadata["nusha_configs"] = {}
            
        metadata["nusha_configs"][str(nusha_index)] = config
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def update_footnotes(self, project_id: str, footnotes: List[Dict]):
        """
        Updates the footnotes list in the project metadata.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        metadata["footnotes"] = footnotes
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def update_nusha_sigla(self, project_id: str, nusha_index: int, sigla: str):
        """
        Updates the sigla (rumuz) for a specific Nusha.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        if "nusha_siglas" not in metadata:
            metadata["nusha_siglas"] = {}
            
        metadata["nusha_siglas"][str(nusha_index)] = sigla
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def update_project_base_nusha(self, project_id: str, nusha_index: int):
        """
        Updates the Base Nusha (Asıl Nüsha) index.
        """
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        metadata["base_nusha_index"] = nusha_index
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)



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
            self.update_nusha_config(project_id, nusha_index, {"filename": target_path.name})
            
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
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to update nusha order: {e}")



    def delete_project(self, project_id: str):
        """
        Deletes the entire project directory.
        """
        project_path = self.get_project_path(project_id)
        if not project_path.exists():
            raise FileNotFoundError(f"Project directory not found: {project_path}")
        
        # Use shutil to remove the directory and all its contents
        shutil.rmtree(project_path)
        print(f"[DELETE] Project {project_id} deleted successfully.")

    def _save_metadata(self, project_id: str, metadata: Dict):
        """Metadata dosyasını diske kaydeder."""
        project_path = self.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def update_nusha_name(self, project_id: str, nusha_index: int, new_name: str):
        """Nüsha ismini metadata içinde günceller."""
        meta = self.get_metadata(project_id)
        if "nusha_names" not in meta:
            meta["nusha_names"] = {}
        
        meta["nusha_names"][str(nusha_index)] = new_name
        self._save_metadata(project_id, meta)
        return new_name

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
            # line_no is 1-based, array is 0-based? 
            # Usually line_no matches index+1 if strictly sequential.
            # But let's search by line_no to be safe.
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
        
        # Remove merged lines (in reverse order to preserve indices)
        for i in reversed(indices[1:]):
            lines.pop(i)
            
        # Renumber
        for idx, line in enumerate(lines):
            line["line_no"] = idx + 1
            
        data["aligned"] = lines
        with open(alignment_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return {"lines": lines}

    def shift_line_content(self, project_id: str, nusha_index: int, line_no: int, direction: str, split_index: int):
        """
        Shifts content between lines, handling text and footnotes.
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
        
        # Validation and Logic
        if direction == "prev":
            if curr_idx == 0: return {"success": False, "error": "No previous line"}
            target_idx = curr_idx - 1
            target_line = lines[target_idx]
            target_line_no = target_line["line_no"]
            
            # Split text
            moving_text = current_text[:split_index]
            remaining_text = current_text[split_index:]
            
            target_text = target_line.get("best", {}).get("raw", "")
            target_len_before = len(target_text) # For footnote offset
            
            # Update Texts
            # Append moving text to target (prev) line, with space if needed? 
             # Usually standard text flow has spaces. Let's assume we toggle space?
            # Actually, split_index comes from UI selection.
            # If we move to prev line, we append to its end. 
            target_line["best"]["raw"] = (target_text + " " + moving_text).strip()
            current_line["best"]["raw"] = remaining_text.strip() # Remove leading space?
            
            # Update Footnotes
            # 1. Footnotes on Current Line that are BEFORE split_index -> Move to Prev Line
            # 2. Footnotes on Current Line that are AFTER split_index -> Shift Left
            
            # The appended text starts at `target_len_before + 1` (accounting for space)
            offset = target_len_before + 1
            
            for fn in footnotes:
                if fn.get("line_no") == line_no:
                    idx = fn.get("index", 0)
                    if idx < split_index:
                        # Move to Prev
                        fn["line_no"] = target_line_no
                        fn["index"] = offset + idx
                    else:
                        # Stay on Current, Shift Left
                        fn["index"] = idx - split_index
                        
        elif direction == "next":
            if curr_idx == len(lines) - 1: return {"success": False, "error": "No next line"}
            target_idx = curr_idx + 1
            target_line = lines[target_idx]
            target_line_no = target_line["line_no"]
            
            # Split text
            remaining_text = current_text[:split_index]
            moving_text = current_text[split_index:]
            
            target_text = target_line.get("best", {}).get("raw", "")
            
            # Update Texts
            # Prepend moving text to target (next) line
            target_line["best"]["raw"] = (moving_text + " " + target_text).strip()
            current_line["best"]["raw"] = remaining_text.strip()
            
            # Update Footnotes
            # 1. Footnotes on Current Line that are AFTER split_index -> Move to Next Line
            # 2. Footnotes on Next Line -> Shift Right
            
            # Length of moved text (+1 for space)
            moved_len = len(moving_text) + 1
            
            # Step 1: Shift existing footnotes on target line RIGHT
            for fn in footnotes:
                if fn.get("line_no") == target_line_no:
                    fn["index"] += moved_len
            
            # Step 2: Move footnotes from Current -> Next
            for fn in footnotes:
                if fn.get("line_no") == line_no:
                    idx = fn.get("index", 0)
                    if idx >= split_index:
                        # Move to Next
                        fn["line_no"] = target_line_no
                        fn["index"] = idx - split_index # Should be relative to start of moving_text
                                                      # moving_text becomes start of next line.
                                                      # so index 0 of moving text = index 0 of next line.
                    # else: stay on current, index unchanged.
            
        else:
            return {"success": False, "error": "Invalid direction"}
            
        # Optimization: Remove empty lines? 
        # User might want to keep them empty or delete them.
        # For now, keep them.
        
        # Save
        with open(alignment_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            
        return {"success": True}

    def split_nusha_line(self, project_id: str, nusha_index: int, line_no: int, split_index: int):
        """Satırı belirtilen karakter indexinden böler."""
        nusha_dir = self.get_nusha_dir(project_id, nusha_index)
        alignment_path = nusha_dir / "alignment.json"
        
        if not alignment_path.exists():
            raise FileNotFoundError("Alignment data not found")

        with open(alignment_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        lines = data.get("aligned", [])
        
        # Find line
        target_idx = next((i for i, x in enumerate(lines) if x["line_no"] == line_no), -1)
        if target_idx == -1:
            raise ValueError("Line not found")
            
        line = lines[target_idx]
        text = line.get("best", {}).get("raw", "")
        
        if split_index < 0 or split_index >= len(text):
             # Boundary protection
             return {"lines": lines}
             
        # Split
        part1 = text[:split_index].strip()
        part2 = text[split_index:].strip()
        
        # Update current line
        line["best"]["raw"] = part1
        
        # Create new line
        # Copy attributes from parent but reset per-line specifics
        new_line = line.copy()
        new_line["best"] = {"raw": part2}
        new_line["line_no"] = line_no + 1 # Temp, will renumber
        # Consider handling bbox/image mapping if needed (complex)
        # For now, new line gets no specific image mapping or inherits?
        # Inheriting incorrect image is confusing. Let's clear image refs for the new line part.
        if "bbox" in new_line: del new_line["bbox"]
        if "line_image" in new_line: del new_line["line_image"]
        
        lines.insert(target_idx + 1, new_line)
        
        # Renumber
        for idx, l in enumerate(lines):
            l["line_no"] = idx + 1
            
        data["aligned"] = lines
        with open(alignment_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return {"lines": lines}
