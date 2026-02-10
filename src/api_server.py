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

class ProcessRequest(BaseModel):
    step: str # 'images', 'ocr', 'align', 'full'
    nusha_index: int = 1
    dpi: int = 300

class UpdateLineRequest(BaseModel):
    line_no: int
    new_text: str

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
def list_projects():
    return project_manager.list_projects()

@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    try:
        pid = project_manager.create_project(req.name)
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
    try:
        project_manager.delete_project(project_id)
        return {"status": "success", "message": f"Project {project_id} deleted."}
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
    file: UploadFile = File(...), 
    file_type: str = Form(...),  # 'docx' veya 'pdf'
    nusha_index: int = Form(1)
):
    # Dosya uzantısını kontrol et
    if file_type == "docx" and not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Sadece .docx yükleyebilirsiniz")
    
    try:
        # Note: We pass file.file (the file-like object) to the manager
        file_path = project_manager.save_uploaded_file(project_id, file.file, file_type, nusha_index, filename=file.filename)
        return {"status": "success", "path": str(file_path)}
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

@app.get("/api/projects/{project_id}/mukabele-data")
def get_mukabele_data(project_id: str):
    try:
        # Priority 1: alignment.json (Rich Data with Highlighting)
        alignment_path = project_manager.projects_dir / project_id / "alignment.json"
        
        # Priority 2: mukabele.json (Legacy/Simple Data)
        mukabele_path = project_manager.projects_dir / project_id / "mukabele.json"
        
        target_path = None
        if alignment_path.exists():
            target_path = alignment_path
            # Load and Process Highlighting
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Inject Highlighting (Line Marks)
            data = alignment_service.process_highlighting(data)
            return data
            
        elif mukabele_path.exists():
            target_path = mukabele_path
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Dosya yoksa boş şablon dön
            return {"segments": []}
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/projects/{project_id}/lines/update")
def update_line(project_id: str, req: UpdateLineRequest):
    try:
        # Determine which file to update
        alignment_path = project_manager.projects_dir / project_id / "alignment.json"
        # Only support updating alignment.json for now as it matches the editor structure
        target_path = alignment_path if alignment_path.exists() else None
        
        if not target_path:
             raise HTTPException(status_code=404, detail="Alignment data not found (alignment.json missing)")

        success = alignment_service.update_line(req.line_no, req.new_text, file_path=target_path)
        
        if success:
            return {"ok": True}
        else:
            raise HTTPException(status_code=404, detail="Line not found or save failed")
            
    except Exception as e:
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
