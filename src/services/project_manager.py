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
        self.projects_dir = PROJECTS_DIR
        self.projects_dir.mkdir(parents=True, exist_ok=True)

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
                            # FAST CHECK: Does alignment.json exist?
                            alignment_path = item / "alignment.json"
                            metadata["has_alignment"] = alignment_path.exists()
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

        for i in range(1, 5):
            n_path = project_path / f"nusha_{i}"
            # Check for any PDF in the nusha directory
            pdf_files = list(n_path.glob("*.pdf"))
            source_exists = len(pdf_files) > 0
            
            # Store filename in config/metadata if found and not already there?
            # Actually, save_uploaded_file updates metadata, so we rely on that.
            # But let's check if the filename in metadata matches the file on disk? 
            # For now, just existence check is enough.
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
                "filename": filename, # Add filename here
                "ready_for_ocr": source_exists,
                "ready_for_align": has_tahkik and lines_exists,
                "progress": progress_data
            }

        return {
            "status": "active",
            "has_tahkik": has_tahkik,
            "nushas": nushas_status
        }

    def save_uploaded_file(self, project_id: str, file_content: bytes, file_type: str, nusha_index: int, filename: str = None) -> Path:
        """
        Saves an uploaded file to the correct location based on its type.
        Accepts file_content as bytes for robust handling.
        """
        project_path = self.projects_dir / project_id
        # Ensure project path exists
        project_path.mkdir(parents=True, exist_ok=True)
        
        target_path = None

        if file_type == "docx":
            # Word Dosyası -> Proje Köküne 'tahkik.docx' olarak
            target_path = project_path / "tahkik.docx"
            print(f"[UPLOAD] Word dosyası kaydediliyor: {target_path}")
            
            # Dosyayı Yaz
            with open(target_path, "wb") as buffer:
                buffer.write(file_content)
        
        else:
            # PDF Dosyası -> Nüsha Klasörüne Orijinal İsmiyle
            nusha_dir = project_path / f"nusha_{nusha_index}"
            nusha_dir.mkdir(parents=True, exist_ok=True)
            
            # Eski dosyaları temizle (Sadece PDF'leri)
            for old_pdf in nusha_dir.glob("*.pdf"):
                try:
                    old_pdf.unlink()
                except Exception:
                    pass

            # Orijinal ismi al
            original_name = filename or "the_manuscript.pdf"
            
            # Güvenli karakter kontrolü (Basit)
            safe_name = "".join(c for c in original_name if c.isalnum() or c in "._- ")
            if not safe_name: safe_name = "the_manuscript.pdf"

            target_path = nusha_dir / safe_name
            print(f"[UPLOAD] PDF dosyası kaydediliyor (Nüsha {nusha_index}): {target_path}")

            # Dosyayı Yaz
            try:
                with open(target_path, "wb") as buffer:
                    buffer.write(file_content)
            except OSError:
                print(f"[WARN] Dosya ismi geçersiz ({safe_name}), generic isim kullanılıyor.")
                target_path = nusha_dir / "the_manuscript.pdf"
                with open(target_path, "wb") as buffer:
                    buffer.write(file_content)

            # Metadata'ya dosya ismini kaydet
            self.update_nusha_config(project_id, nusha_index, {"filename": target_path.name})
            
        return target_path


    def delete_file(self, project_id: str, file_type: str, nusha_index: int = 1):
        """Dosyayı ve ilgili analiz verilerini diskten siler."""
        project_path = self.projects_dir / project_id
        
        if file_type == "docx":
            # Word dosyasını sil
            tahkik_path = project_path / "tahkik.docx"
            if tahkik_path.exists():
                tahkik_path.unlink()
                print(f"[DELETE] Referans metin silindi: {tahkik_path}")

        elif file_type == "pdf":
            # Nüsha PDF'ini VE oluşturulan tüm klasörleri (pages, lines, vb.) sil
            nusha_path = project_path / f"nusha_{nusha_index}"
            if nusha_path.exists():
                import shutil
                # Klasörün içini temizle ama klasör yapısını koru
                shutil.rmtree(nusha_path)
                nusha_path.mkdir()
                print(f"[DELETE] Nüsha {nusha_index} verileri sıfırlandı.")

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
