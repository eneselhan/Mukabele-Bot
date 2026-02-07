from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn
import os
import shutil
import json
from pathlib import Path

# New Architecture Services
from src.services.project_manager import ProjectManager
from src.services.manuscript_engine import ManuscriptEngine
from src.config import PROJECTS_DIR

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


# --- DATA MODELS ---
class CreateProjectRequest(BaseModel):
    name: str

class ProcessRequest(BaseModel):
    step: str # 'images', 'ocr', 'align', 'full'
    nusha_index: int = 1


# --- SERVICES ---
project_manager = ProjectManager()


# --- BACKGROUND WORKER ---
def background_task_runner(project_id: str, step: str, nusha_index: int):
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
             res = engine.run_full_pipeline(nusha_index)
             if not res["success"]: raise RuntimeError(res.get("error"))

        # (Existing logic for individual steps is now redundant for 'ocr' but kept if needed for granularity or specific 'images' requests)
        elif step == "images":
             GLOBAL_STATUS["message"] = "PDF -> Resim dönüştürülüyor..."
             GLOBAL_STATUS["progress"] = 10
             res = engine.convert_pdf_to_images(nusha_index)
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

@app.post("/api/projects/{project_id}/upload")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    nusha_index: int = Form(1),
    file_type: str = Form("pdf"), # 'pdf' or 'docx'
    dpi: int = Form(300) 
):
    try:
        if file_type == "pdf":
            # Save to nusha folder
            target_dir = project_manager.get_nusha_dir(project_id, nusha_index)
            file_path = target_dir / "source.pdf"
            
            # Save DPI config
            project_manager.update_nusha_config(project_id, nusha_index, {"dpi": dpi})
            
        elif file_type == "docx":
             target_dir = project_manager.get_project_path(project_id)
             file_path = target_dir / "tahkik.docx"
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Use 'pdf' or 'docx'.")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"filename": file.filename, "saved_as": str(file_path.name), "status": "uploaded", "dpi": dpi if file_type == "pdf" else None}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/process")
async def process_project(
    project_id: str, 
    req: ProcessRequest, 
    background_tasks: BackgroundTasks
):
    if GLOBAL_STATUS["busy"]:
         raise HTTPException(status_code=400, detail="Sistem şu an meşgul.")

    background_tasks.add_task(background_task_runner, project_id, req.step, req.nusha_index)
    return {"ok": True, "message": f"{req.step} işlemi kuyruğa alındı."}

@app.get("/api/projects/{project_id}/status")
def get_status(project_id: str):
    # If the global status is busy with THIS project, return it
    if GLOBAL_STATUS["project_id"] == project_id:
        return GLOBAL_STATUS
    
    # Otherwise return idle
    return {
        "busy": False,
        "step": "idle",
        "message": "Bekleniyor",
        "progress": 0
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
