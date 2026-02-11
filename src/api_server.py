from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn
import os

import json
import shutil
from pathlib import Path

# Fix for Silent Crash (PyTorch/Kraken Thread Conflict)
os.environ["OMP_NUM_THREADS"] = "1"

# New Architecture Services
from src.services.project_manager import ProjectManager
from src.config import BASE_DIR
from src.services.manuscript_engine import ManuscriptEngine
from src.config import PROJECTS_DIR
from src.services.alignment_service import AlignmentService
from src.services.tts_service import TTSService

# --- GLOBAL STATE ---
# Track current job status
GLOBAL_STATUS = {
    "busy": False,
    "project_id": None,
    "nusha_index": None,
    "step": "idle",
    "message": "Sistem Hazır",
    "progress": 0
}

app = FastAPI(title="Tahkik-Bot V2 API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STATIC FILES ---
# Mount projects folder to /media to serve images/audio
app.mount("/media", StaticFiles(directory=PROJECTS_DIR), name="media")

# Mount tahkik_data folder to /tahkik_data to serve other static assets
app.mount("/tahkik_data", StaticFiles(directory=BASE_DIR / "tahkik_data"), name="tahkik_data")


# --- DATA MODELS ---
class CreateProjectRequest(BaseModel):
    name: str
    authors: Optional[List[str]] = []
    language: Optional[str] = "Ottoman Turkish"
    subject: Optional[str] = "Islamic Studies"
    description: Optional[str] = ""

class ProcessRequest(BaseModel):
    step: str # 'images', 'ocr', 'align', 'full'
    nusha_index: int = 1
    dpi: int = 300

class UpdateLineRequest(BaseModel):
    line_no: int
    new_text: str
    nusha_index: int = 1

class TTSRequest(BaseModel):
    ssml: Optional[str] = None
    tokens: Optional[List[str]] = None
    language_code: Optional[str] = "ar-XA"
    gender: Optional[str] = "MALE"
    voice_name: Optional[str] = None
    speaking_rate: Optional[float] = 1.0
    action: Optional[str] = None
    page_key: Optional[str] = None
    archive_path: Optional[str] = None
    nusha_id: Optional[int] = 1
    token_start: Optional[int] = 0
    reset_log: Optional[bool] = False


# --- SERVICES ---
project_manager = ProjectManager()
alignment_service = AlignmentService()
tts_service = TTSService()


# --- BACKGROUND WORKER ---
def background_task_runner(project_id: str, step: str, nusha_index: int, dpi: int = 300):
    global GLOBAL_STATUS
    GLOBAL_STATUS.update({
        "busy": True,
        "project_id": project_id,
        "nusha_index": nusha_index,
        "step": step,
        "message": f"{step.upper()} işlemi başlatılıyor...",
        "progress": 5
    })

    try:
        engine = ManuscriptEngine(project_id)
        
        # 1. Pipeline Execution (PDF -> Segmentation -> OCR)
        if step in ["ocr", "full"]:
             # This runs convert_pdf_to_images, run_line_segmentation, and run_ocr in sequence
             GLOBAL_STATUS["message"] = "Tam süreç başlatılıyor (PDF -> Segmentasyon -> OCR)..."
             res = engine.run_full_pipeline(nusha_index, dpi=dpi)
             if not res["success"]: raise RuntimeError(res.get("error"))

        # (Existing logic for individual steps is now redundant for 'ocr' but kept if needed for granularity or specific 'images' requests)
        elif step == "images":
             GLOBAL_STATUS["message"] = "PDF -> Resim dönüştürülüyor..."
             GLOBAL_STATUS["progress"] = 10
             res = engine.convert_pdf_to_images(nusha_index, dpi=dpi)
             if not res["success"]: raise RuntimeError(res.get("error"))

        elif step == "segmentation":
             GLOBAL_STATUS["message"] = "Sayfa yapısı analiz ediliyor (Segmentasyon)..."
             GLOBAL_STATUS["progress"] = 30
             res = engine.run_line_segmentation(nusha_index)
             if not res["success"]: raise RuntimeError(res.get("error"))

        elif step == "ocr_only":
             GLOBAL_STATUS["message"] = "Metin tanıma (OCR) yapılıyor..."
             GLOBAL_STATUS["progress"] = 50
             res = engine.run_ocr(nusha_index)
             if not res["success"]: raise RuntimeError(res.get("error"))

        # 4. Alignment
        if step in ["align", "full"]:
            GLOBAL_STATUS["message"] = "Metin hizalama (Alignment) yapılıyor..."
            GLOBAL_STATUS["progress"] = 80
            res = engine.align_manuscript(nusha_index)
            if not res["success"]: raise RuntimeError(res.get("error"))

        GLOBAL_STATUS.update({
            "busy": False,
            "step": "idle",
            "message": "İşlem Başarıyla Tamamlandı",
            "progress": 100
        })

    except Exception as e:
        print(f"Background Task Error: {e}")
        GLOBAL_STATUS.update({
            "busy": False,
            "step": "error",
            "message": f"Hata oluştu: {str(e)}",
            "progress": 0
        })


# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"status": "Tahkik-Bot V2 API is running"}

@app.get("/api/projects")
def list_projects(trashed: bool = False):
    all_projects = project_manager.list_projects()
    return [p for p in all_projects if p.get("trashed", False) == trashed]

@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    try:
        pid = project_manager.create_project(
            name=req.name,
            authors=req.authors,
            language=req.language,
            subject=req.subject,
            description=req.description
        )
        return {"id": pid, "name": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    try:
        return project_manager.get_metadata(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    """Permanently deletes a project from disk."""
    try:
        project_manager.delete_project(project_id)
        return {"status": "success", "message": f"Project {project_id} permanently deleted."}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/trash")
def trash_project(project_id: str):
    """Soft-delete: marks a project as trashed."""
    try:
        metadata = project_manager.get_metadata(project_id)
        metadata["trashed"] = True
        project_path = project_manager.get_project_path(project_id)
        with open(project_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "Proje çöp kutusuna taşındı."}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/restore")
def restore_project(project_id: str):
    """Restores a trashed project."""
    try:
        metadata = project_manager.get_metadata(project_id)
        metadata["trashed"] = False
        project_path = project_manager.get_project_path(project_id)
        with open(project_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "Proje geri yüklendi."}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    authors: Optional[List[str]] = None
    language: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None

@app.put("/api/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest):
    try:
        metadata = project_manager.get_metadata(project_id)
        if req.name is not None: metadata["name"] = req.name
        if req.authors is not None: metadata["authors"] = req.authors
        if req.language is not None: metadata["language"] = req.language
        if req.subject is not None: metadata["subject"] = req.subject
        if req.description is not None: metadata["description"] = req.description
        
        project_path = project_manager.get_project_path(project_id)
        metadata_path = project_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "metadata": metadata}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateNameRequest(BaseModel):
    name: str

@app.put("/api/projects/{project_id}/nusha/{nusha_index}/name")
def update_nusha_name(project_id: str, nusha_index: int, req: UpdateNameRequest):
    project_manager.update_nusha_name(project_id, nusha_index, req.name)
    return {"status": "success", "name": req.name}

class UpdateOrderRequest(BaseModel):
    order: List[int]

@app.post("/api/projects/{project_id}/order")
def update_project_order(project_id: str, req: UpdateOrderRequest):
    try:
        project_manager.update_nusha_order(project_id, req.order)
        return {"status": "success", "order": req.order}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/word/spellcheck")
def run_spellcheck(project_id: str):
    try:
        result = project_manager.run_word_spellcheck(project_id)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/api/projects/{project_id}/files")
def delete_project_file(project_id: str, file_type: str, nusha_index: int = 1):
    try:
        project_manager.delete_file(project_id, file_type, nusha_index)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/projects/{project_id}/upload")
async def upload_file(
    project_id: str, 
    files: List[UploadFile] = File(...), 
    file_type: str = Form(...),  # 'docx' veya 'pdf'
    nusha_index: int = Form(1),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Dosya uzantısını kontrol et
    if file_type == "docx":
         if len(files) > 1:
             raise HTTPException(status_code=400, detail="Sadece tek bir Word dosyası yükleyebilirsiniz.")
         if not files[0].filename.endswith(".docx"):
            raise HTTPException(status_code=400, detail="Sadece .docx yükleyebilirsiniz")
    
    saved_paths = []
    try:
        current_nusha_index = nusha_index

        for file in files:
            # Robust upload: Read file content first
            content = await file.read()
            
            # Note: We pass bytes content to the manager
            file_path, used_index = project_manager.save_uploaded_file(
                project_id=project_id, 
                file_content=content, 
                file_type=file_type, 
                nusha_index=current_nusha_index, 
                filename=file.filename
            )
            saved_paths.append(str(file_path))

            # If we are in "New Nusha" mode (index <= 0)
            if file_type != "docx" and nusha_index <= 0:
                 # The manager calculated a new index for us (used_index)
                 # For the NEXT file in this batch, we want it to be used_index + 1
                 current_nusha_index = used_index + 1

        return {"status": "success", "paths": saved_paths}
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/process")
async def process_project(
    project_id: str, 
    req: ProcessRequest, 
    background_tasks: BackgroundTasks
):
    if GLOBAL_STATUS["busy"]:
         raise HTTPException(status_code=400, detail="Sistem şu an meşgul.")
    
    # Pre-flight Check: Ensure tahkik.docx exists for alignment steps
    if req.step in ["align", "full"]:
        try:
             # project_id should be just the ID string here
             tahkik_path = project_manager.projects_dir / project_id / "tahkik.docx"
             if not tahkik_path.exists():
                 raise HTTPException(status_code=400, detail="Önce Word dosyası (tahkik.docx) yüklemelisiniz.")
        except Exception:
             pass # Let the engine handle other errors or pass through check if path construction fails

    background_tasks.add_task(background_task_runner, project_id, req.step, req.nusha_index, req.dpi)
    return {"ok": True, "message": f"{req.step} işlemi kuyruğa alındı."}

@app.get("/api/projects/{project_id}/status")
def get_status(project_id: str):
    # 1. Get Persistent File Status from Disk
    try:
        file_status = project_manager.get_project_status(project_id)
    except Exception:
        file_status = {"has_tahkik": False, "nushas": {}}

    # 2. Get Ephemeral Process Status (Global Variable)
    process_status = {
        "busy": False,
        "step": "idle",
        "message": "Hazır",
        "progress": 0,
        "active_nusha": None
    }
    
    # If the global status is busy with THIS project, override process status
    if GLOBAL_STATUS["project_id"] == project_id:
        process_status = {
            "busy": GLOBAL_STATUS["busy"],
            "step": GLOBAL_STATUS["step"],
            "message": GLOBAL_STATUS["message"],
            "progress": GLOBAL_STATUS["progress"],
            "active_nusha": GLOBAL_STATUS["nusha_index"]
        }

    # 3. Merge and Return
    return {
        **process_status,
        **file_status
    }

@app.get("/api/projects/{project_id}/nusha/{nusha_index}/pipeline/status")
def get_pipeline_status(project_id: str, nusha_index: int):
    """
    Returns the granular status of each pipeline step for a specific Nusha.
    Detects completion based on filesystem checks.
    """
    try:
        nusha_dir = project_manager.get_nusha_dir(project_id, nusha_index)
        
        # Check Word file for alignment prerequisite
        tahkik_path = project_manager.projects_dir / project_id / "tahkik.docx"
        has_reference = tahkik_path.exists()
        
        # Step 1: Pages (PDF → Images)
        pages_dir = nusha_dir / "pages"
        pages_completed = pages_dir.exists() and len(list(pages_dir.glob("*.png"))) > 0
        pages_count = len(list(pages_dir.glob("*.png"))) if pages_completed else 0
        
        # Step 2: Segmentation (Lines Manifest)
        manifest_path = nusha_dir / "lines_manifest.jsonl"
        segmentation_completed = manifest_path.exists()
        segmentation_count = 0
        if segmentation_completed:
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    segmentation_count = sum(1 for _ in f)
            except:
                pass
        
        # Step 3: Text Recognition (Google Vision OCR Output)
        ocr_dir = nusha_dir / "ocr"
        text_recognition_completed = ocr_dir.exists() and len(list(ocr_dir.glob("*.json"))) > 0
        text_recognition_count = 0
        if text_recognition_completed:
            text_recognition_count = len(list(ocr_dir.glob("*.json")))

        # Step 4: Alignment
        alignment_path = nusha_dir / "alignment.json"
        alignment_completed = alignment_path.exists()
        
        # Determine step statuses
        def get_step_status(completed, prerequisites_met):
            if completed:
                return "completed"
            elif prerequisites_met:
                return "pending"
            else:
                return "not_started"
        
        pages_status = get_step_status(pages_completed, True)
        segmentation_status = get_step_status(segmentation_completed, pages_completed)
        text_recognition_status = get_step_status(text_recognition_completed, segmentation_completed)
        alignment_status = get_step_status(alignment_completed, text_recognition_completed and has_reference)
        
        return {
            "steps": {
                "pages": {
                    "status": pages_status,
                    "count": pages_count
                },
                "segmentation": {
                    "status": segmentation_status,
                    "count": segmentation_count
                },
                "text_recognition": {
                    "status": text_recognition_status,
                    "count": text_recognition_count
                },
                "alignment": {
                    "status": alignment_status,
                    "requires_reference": not has_reference
                }
            }
        }
        
    except Exception as e:
        print(f"Pipeline Status Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_id}/nusha/{nusha_index}/pipeline/outputs")
def get_pipeline_outputs(project_id: str, nusha_index: int):
    """
    Returns the actual output data for each pipeline step for preview/debugging.
    - Pages: list of image filenames
    - Segmentation: list of line image filenames
    - Text Recognition: list of {filename, text} from OCR .txt files
    - Alignment: full alignment.json parsed as debug payload
    """
    import re
    try:
        nusha_dir = project_manager.get_nusha_dir(project_id, nusha_index)
        result = {}

        # 1. Pages — PNG image filenames (sorted naturally)
        pages_dir = nusha_dir / "pages"
        if pages_dir.exists():
            page_files = sorted([f.name for f in pages_dir.glob("*.png")])
            result["pages"] = page_files
        else:
            result["pages"] = []

        # 2. Segmentation — Line image filenames (sorted naturally)
        lines_dir = nusha_dir / "lines"
        if lines_dir.exists():
            line_files = sorted([f.name for f in lines_dir.glob("*.png")])
            result["lines"] = line_files
        else:
            result["lines"] = []

        # 3. Text Recognition — Read OCR .txt files (sorted naturally)
        ocr_dir = nusha_dir / "ocr"
        if ocr_dir.exists():
            ocr_texts = []
            txt_files = sorted(ocr_dir.glob("*.txt"), key=lambda f: f.name)
            for tf in txt_files:
                try:
                    text = tf.read_text(encoding="utf-8").strip()
                    ocr_texts.append({"filename": tf.name, "text": text})
                except Exception:
                    ocr_texts.append({"filename": tf.name, "text": "[okuma hatası]"})
            result["ocr_texts"] = ocr_texts
        else:
            result["ocr_texts"] = []

        # 4. Alignment — Full debug payload
        alignment_path = nusha_dir / "alignment.json"
        if alignment_path.exists():
            try:
                with open(alignment_path, "r", encoding="utf-8") as f:
                    alignment_data = json.load(f)

                # Extract debug-friendly summary
                aligned_lines = alignment_data.get("aligned", [])
                debug_info = {
                    "algo_version": alignment_data.get("algo_version", "unknown"),
                    "docx_path": alignment_data.get("docx_path", ""),
                    "tahkik_word_count": alignment_data.get("tahkik_word_count", 0),
                    "lines_count": alignment_data.get("lines_count", 0),
                    "has_alt": alignment_data.get("has_alt", False),
                    "has_alt3": alignment_data.get("has_alt3", False),
                    "has_alt4": alignment_data.get("has_alt4", False),
                    "lines_count_alt": alignment_data.get("lines_count_alt", 0),
                    "lines_count_alt3": alignment_data.get("lines_count_alt3", 0),
                    "lines_count_alt4": alignment_data.get("lines_count_alt4", 0),
                    "spellcheck_errors_count": len(alignment_data.get("spellcheck", [])),
                }

                # Per-line debug data: scores, bounds, text snippets
                line_details = []
                for item in aligned_lines:
                    best = item.get("best", {})
                    line_details.append({
                        "line_no": item.get("line_no"),
                        "ocr_text": item.get("ocr_text", ""),
                        "ref_text": best.get("raw", ""),
                        "score": best.get("score", 0),
                        "start_word": best.get("start_word", 0),
                        "end_word": best.get("end_word", 0),
                        "ocr_wc": item.get("ocr_wc", 0),
                        "seg_wc": item.get("seg_wc", 0),
                        "is_empty_ocr": item.get("is_empty_ocr", False),
                        "error_count": item.get("error_count", 0),
                        "line_image": item.get("line_image", ""),
                    })

                # Use real debug_log from alignment if present (new runs),
                # otherwise fall back to basic static info (old runs)
                debug_log = alignment_data.get("debug_log", None)
                if not debug_log:
                    # Fallback for alignment.json files generated before instrumentation
                    avg_score = sum(l['score'] for l in line_details) / max(len(line_details), 1) if line_details else 0
                    debug_log = [
                        {"name": "read_docx_text", "description": "Word dosyasından metin okuma", "output": f"{debug_info['tahkik_word_count']} kelime okundu", "data": {}},
                        {"name": "load_ocr_lines_ordered", "description": "OCR satırlarını yükleme", "output": f"{debug_info['lines_count']} satır yüklendi", "data": {}},
                        {"name": "score_segment", "description": "Hizalama skoru hesaplama", "output": f"Ortalama skor: {avg_score:.3f}", "data": {}},
                    ]

                result["alignment"] = {
                    "debug": debug_info,
                    "lines": line_details,
                    "functions_executed": debug_log,
                }
            except Exception as e:
                result["alignment"] = {"error": str(e)}
        else:
            result["alignment"] = None

        return result

    except Exception as e:
        print(f"Pipeline Outputs Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/nusha/{nusha_index}/pipeline/{step}")
async def execute_pipeline_step(
    project_id: str, 
    nusha_index: int, 
    step: str,
    background_tasks: BackgroundTasks,
    dpi: int = 300
):
    """
    Execute a single pipeline step: pages, ocr, or alignment.
    """
    if GLOBAL_STATUS["busy"]:
        raise HTTPException(status_code=400, detail="Sistem şu an meşgul.")
    
    valid_steps = ["pages", "segmentation", "text_recognition", "alignment", "full"]
    if step not in valid_steps:
        raise HTTPException(status_code=400, detail=f"Invalid step. Must be one of: {valid_steps}")
    
    # Map step names to backend process names
    step_map = {
        "pages": "images",
        "segmentation": "segmentation",
        "text_recognition": "ocr_only",
        "alignment": "align",
        "full": "full"
    }
    
    backend_step = step_map[step]
    
    # Pre-flight checks
    if step in ["alignment"]:
        tahkik_path = project_manager.projects_dir / project_id / "tahkik.docx"
        if not tahkik_path.exists():
            raise HTTPException(status_code=400, detail="Önce Word dosyası (tahkik.docx) yüklemelisiniz.")
    
    # Queue the task
    background_tasks.add_task(background_task_runner, project_id, backend_step, nusha_index, dpi)
    return {"ok": True, "message": f"{step} adımı başlatıldı."}

@app.delete("/api/projects/{project_id}/nusha/{nusha_index}/pipeline/{step}")
def delete_pipeline_step(project_id: str, nusha_index: int, step: str):
    """
    Delete output of a specific pipeline step with cascade deletion.
    - Delete pages → Also delete OCR + Alignment
    - Delete ocr → Also delete Alignment
    - Delete alignment → Only delete alignment.json
    """
    try:
        nusha_dir = project_manager.get_nusha_dir(project_id, nusha_index)
        
        deleted_items = []
        
        # Cascade deletion rules
        if step == "pages":
            # Delete pages directory
            pages_dir = nusha_dir / "pages"
            if pages_dir.exists():
                shutil.rmtree(pages_dir)
                deleted_items.append("pages")
            
            # Cascade: Also delete Segmentation, OCR and Alignment
            manifest_path = nusha_dir / "lines_manifest.jsonl"
            lines_dir = nusha_dir / "lines"
            ocr_dir = nusha_dir / "ocr" # Also delete OCR output
            
            if manifest_path.exists():
                manifest_path.unlink()
                deleted_items.append("lines_manifest.jsonl")
            if lines_dir.exists():
                shutil.rmtree(lines_dir)
                deleted_items.append("lines")
            if ocr_dir.exists():
                shutil.rmtree(ocr_dir)
                deleted_items.append("ocr")
            
            alignment_path = nusha_dir / "alignment.json"
            if alignment_path.exists():
                alignment_path.unlink()
                deleted_items.append("alignment.json")
                
        elif step == "segmentation":
            # Delete Segmentation outputs (lines + manifest)
            manifest_path = nusha_dir / "lines_manifest.jsonl"
            lines_dir = nusha_dir / "lines"
            
            if manifest_path.exists():
                manifest_path.unlink()
                deleted_items.append("lines_manifest.jsonl")
            if lines_dir.exists():
                shutil.rmtree(lines_dir)
                deleted_items.append("lines")
            
            # Cascade: Also delete OCR and Alignment
            ocr_dir = nusha_dir / "ocr"
            if ocr_dir.exists():
                shutil.rmtree(ocr_dir)
                deleted_items.append("ocr")
                
            alignment_path = nusha_dir / "alignment.json"
            if alignment_path.exists():
                alignment_path.unlink()
                deleted_items.append("alignment.json")

        elif step == "text_recognition":
            # Delete OCR outputs
            ocr_dir = nusha_dir / "ocr"
            if ocr_dir.exists():
                shutil.rmtree(ocr_dir)
                deleted_items.append("ocr")
            
            # Cascade: Also delete Alignment
            alignment_path = nusha_dir / "alignment.json"
            if alignment_path.exists():
                alignment_path.unlink()
                deleted_items.append("alignment.json")
                
        elif step == "alignment":
            # Only delete alignment.json
            alignment_path = nusha_dir / "alignment.json"
            if alignment_path.exists():
                alignment_path.unlink()
                deleted_items.append("alignment.json")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid step: {step}")
        
        return {
            "ok": True,
            "deleted": deleted_items,
            "message": f"{step} adımı silindi."
        }
        
    except Exception as e:
        print(f"Delete Pipeline Step Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _backfill_from_manifest(lines_list: List[Dict], manifest_path: Path):
    """
    Backfills missing bbox, page_image, and page_name from lines_manifest.jsonl.
    Matches primarily by line_image filename.
    """
    if not lines_list or not manifest_path.exists():
        return lines_list
        
    # Build Manifest Lookup: filename -> record
    manifest_map = {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                # Key by just the filename of the line image
                line_img_path = rec.get("line_image", "")
                if line_img_path:
                    fname = Path(line_img_path).name
                    manifest_map[fname] = rec
    except Exception as e:
        print(f"[API] Manifest read error: {e}")
        return lines_list

    # Backfill
    for item in lines_list:
        # Get existing image path from alignment
        line_img = item.get("line_image", "")
        if not line_img: continue
        
        fname = Path(line_img).name
        if fname in manifest_map:
            rec = manifest_map[fname]
            
            # 1. Backfill BBox if missing or null
            if item.get("bbox") is None:
                item["bbox"] = rec.get("bbox")
                
            # 2. Backfill Page Image (Critical for page mapping)
            # The manifest has full path, we might want just filename or relative
            # Frontend PageCanvas expects just filename in some places.
            if not item.get("page_image"):
                p_img = rec.get("page_image", "")
                if p_img:
                    item["page_image"] = Path(p_img).name # Use filename for safer matching
                    
            # 3. Page Name (Optional)
            if not item.get("page_name"):
                # Infer from page_image filename
                p_img = item.get("page_image", "")
                if p_img:
                    # extract number p001 -> Sayfa 1
                    import re
                    m = re.search(r'p(\d+)', p_img)
                    if m:
                         item["page_name"] = f"Sayfa {int(m.group(1))}"
    
    return lines_list

@app.get("/api/projects/{project_id}/mukabele-data")
def get_mukabele_data(project_id: str):
    try:
        # Initialize structure
        final_data = {
            "aligned": [],
            "aligned_alt": [],
            "aligned_alt3": [],
            "aligned_alt4": [],
            "has_alt": False,
            "has_alt3": False,
            "has_alt4": False
        }

        # Helper to load from nusha dir without failing
        def load_nusha(n_idx):
            try:
                p = project_manager.get_nusha_dir(project_id, n_idx) / "alignment.json"
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f).get("aligned", [])
            except: pass
            return []

        # Load N1 (Primary)
        # Priority: Nusha 1 specific > Legacy root alignment.json
        n1_data = load_nusha(1)
        if n1_data:
            final_data["aligned"] = n1_data
        else:
            # Fallback to legacy root alignment.json
            root_align = project_manager.projects_dir / project_id / "alignment.json"
            if root_align.exists():
                 with open(root_align, "r", encoding="utf-8") as f:
                     final_data["aligned"] = json.load(f).get("aligned", [])

        # Load others
        final_data["aligned_alt"] = load_nusha(2)
        final_data["aligned_alt3"] = load_nusha(3)
        final_data["aligned_alt4"] = load_nusha(4)
        
        # --- FIX 1: Backfill BBox & Page Data from Manifest ---
        # Only needed if direct alignment JSON is missing this info (it usually is)
        
        # Nusha 1
        n1_manifest = project_manager.get_nusha_dir(project_id, 1) / "lines_manifest.jsonl"
        _backfill_from_manifest(final_data["aligned"], n1_manifest)
        
        # Nusha 2
        n2_manifest = project_manager.get_nusha_dir(project_id, 2) / "lines_manifest.jsonl"
        _backfill_from_manifest(final_data["aligned_alt"], n2_manifest)
        
        # Nusha 3
        n3_manifest = project_manager.get_nusha_dir(project_id, 3) / "lines_manifest.jsonl"
        _backfill_from_manifest(final_data["aligned_alt3"], n3_manifest)
        
        # Nusha 4
        n4_manifest = project_manager.get_nusha_dir(project_id, 4) / "lines_manifest.jsonl"
        _backfill_from_manifest(final_data["aligned_alt4"], n4_manifest)

        
        # FILTER OUT PREFACE LINES (GİRİŞ KISMI) FROM ALL ALIGNED DATA
        # These are lines marked as outside alignment scope
        def filter_preface(lines):
            """Remove lines marked as preface/intro that shouldn't be displayed"""
            return [
                line for line in lines 
                if not (line.get('best', {}).get('raw', '').strip() == '--- [GİRİŞ KISMI / HİZALAMA DIŞI] ---')
            ]
        
        final_data["aligned"] = filter_preface(final_data["aligned"])

        final_data["aligned_alt"] = filter_preface(final_data["aligned_alt"])
        final_data["aligned_alt3"] = filter_preface(final_data["aligned_alt3"])
        final_data["aligned_alt4"] = filter_preface(final_data["aligned_alt4"])
        
        final_data["has_alt"] = len(final_data["aligned_alt"]) > 0
        final_data["has_alt3"] = len(final_data["aligned_alt3"]) > 0
        final_data["has_alt4"] = len(final_data["aligned_alt4"]) > 0

        # Only fallback to mukabele.json if absolutely no data found in N1
        if not final_data["aligned"]:
             mukabele_path = project_manager.projects_dir / project_id / "mukabele.json"
             if mukabele_path.exists():
                 with open(mukabele_path, "r", encoding="utf-8") as f:
                     # Return legacy format directly if needed, or try to adapt?
                     # Returns whatever is in mukabele.json, usually {"segments": ...}
                     # But MukabeleView expects "aligned".
                     # If we return raw mukabele.json, frontend might break if it expects "aligned".
                     # Let's verify what mukabele.json contains. It contains "segments".
                     # Currently, frontend LineList iterates `lines` which comes from `data.aligned`.
                     # We should map `segments` to `aligned` if possible, or just fail gracefully.
                     legacy_data = json.load(f)
                     # Simple adapter:
                     if "segments" in legacy_data:
                         final_data["aligned"] = []
                         for seg in legacy_data["segments"]:
                             # Convert segment to LineItem style
                             final_data["aligned"].append({
                                 "line_no": seg.get("id"),
                                 "best": {"raw": seg.get("ref_text", "")},
                                 # We lose image mapping here if we don't handle "nushas"
                             })
                 return final_data

        # Inject Highlighting & Enrich
        # process_highlighting expects spellcheck data.
        # We need to find where spellcheck data is. Likely in Nusha 1 alignment or root.
        root_align = project_manager.projects_dir / project_id / "alignment.json"
        if root_align.exists():
             with open(root_align, "r", encoding="utf-8") as f:
                 d = json.load(f)
                 if "spellcheck_per_paragraph" in d:
                     final_data["spellcheck_per_paragraph"] = d["spellcheck_per_paragraph"]
        elif (project_manager.get_nusha_dir(project_id, 1) / "alignment.json").exists():
             with open(project_manager.get_nusha_dir(project_id, 1) / "alignment.json", "r", encoding="utf-8") as f:
                 d = json.load(f)
                 if "spellcheck_per_paragraph" in d:
                     final_data["spellcheck_per_paragraph"] = d["spellcheck_per_paragraph"]

        final_data = alignment_service.process_highlighting(final_data)
        final_data = alignment_service.enrich_alignment_data(final_data, project_id=project_id)
        
        return final_data

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        print(f"[API] Mukabele Data Error: {traceback_str}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback_str})

@app.get("/api/projects/{project_id}/pages")
def get_pages(project_id: str, nusha_index: int = 1):
    try:
        # Determine nusha directory
        nusha_dir = project_manager.get_nusha_dir(project_id, nusha_index)
        pages_dir = nusha_dir / "pages"
        
        if not pages_dir.exists():
            return []
            
        # List images
        images = sorted([p for p in pages_dir.glob("*.png")])
        
        # Load alignment to get line counts per page if possible (optional but good UI)
        # For now, just return images
        pages_list = []
        for i, img_path in enumerate(images):
             # Construct valid URL part or relative path
             # Frontend PageCanvas logic: /media/{pid}/nusha_{idx}/pages/{filename}
             # We just return the filename or relative path
             pages_list.append({
                 "index": i,
                 "name": f"Sayfa {i+1}",
                 "image_filename": img_path.name,
                 "key": f"p{i+1}"
             })
        
        return pages_list
    except Exception as e:
         return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/projects/{project_id}/lines/update")
def update_line(project_id: str, req: UpdateLineRequest):
    try:
        # Determine which file to update based on nusha_index
        target_path = None
        
        # Try specific nusha folder first
        nusha_path = project_manager.get_nusha_dir(project_id, req.nusha_index) / "alignment.json"
        
        if nusha_path.exists():
            target_path = nusha_path
        elif req.nusha_index == 1:
            # Fallback for Nusha 1: check root alignment.json
            root_path = project_manager.projects_dir / project_id / "alignment.json"
            if root_path.exists():
                target_path = root_path
        
        if not target_path:
             print(f"[API] Update Error: Alignment file not found for Nusha {req.nusha_index}")
             raise HTTPException(status_code=404, detail=f"Alignment data not found for Nusha {req.nusha_index}")

        success = alignment_service.update_line(req.line_no, req.new_text, file_path=target_path)
        
        if success:
            return {"ok": True}
        else:
            raise HTTPException(status_code=404, detail="Line not found or save failed")
            
    except Exception as e:
        print(f"[API] Update Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts")
def tts_generate(req: TTSRequest):
    try:
        # Convert Pydantic model to dict for service
        # Exclude defaults? No, services handles them.
        req_dict = req.model_dump()
        result = tts_service.process_tts_request(req_dict)
        
        if "error" in result:
             status = result.get("status", 500)
             return JSONResponse(status_code=status, content=result)
             
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    uvicorn.run("src.api_server:app", host="0.0.0.0", port=8000, reload=True)
