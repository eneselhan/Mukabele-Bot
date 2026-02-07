from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn
import os
import shutil
import json
from pathlib import Path
from gtts import gTTS
from PIL import Image

# Pipeline & Servisler
from src.services.alignment_service import AlignmentService
from src.pipeline import run_pipeline
from src.alignment import align_ocr_to_tahkik_segment_dp_multi
from src.config import ALIGNMENT_JSON, get_nusha_out_dir, LINES_MANIFEST

app = FastAPI()

# GLOBAL DURUM
JOB_STATUS = {
    "busy": False,
    "step": "idle",
    "message": "Hazır",
    "progress": 0,
    "current_nusha": 1
}

# --- YENİ REQUEST MODELİ ---
class ProcessRequest(BaseModel):
    ref_filename: str            
    filename: str                
    target_nusha_index: int = 1  

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

alignment_service = AlignmentService()

class LineUpdate(BaseModel):
    line_no: int
    text: str

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik Dosyalar 
OUTPUT_DIR = os.path.join(os.getcwd(), "output_lines")
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/output_lines", StaticFiles(directory=OUTPUT_DIR), name="output_lines")

audio_dir = os.path.join(os.getcwd(), "output")
os.makedirs(audio_dir, exist_ok=True)
app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

images_dir = os.path.join(os.getcwd(), "images")
os.makedirs(images_dir, exist_ok=True)
app.mount("/images", StaticFiles(directory=images_dir), name="images")

@app.get("/")
def read_root():
    return {"status": "API is running"}

@app.get("/api/lines")
def get_lines():
    data, _ = alignment_service._load_data()
    return data if data else []

@app.post("/api/update_line")
def update_line(update_data: LineUpdate):
    success = alignment_service.update_line(update_data.line_no, update_data.text)
    if not success:
        raise HTTPException(status_code=404, detail="Hata oluştu")
    return {"ok": True, "line_no": update_data.line_no}

@app.post("/api/generate_audio")
def generate_audio(data: LineUpdate):
    try:
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"line_{data.line_no}.wav")
        tts = gTTS(text=data.text, lang='ar')
        tts.save(file_path)
        return {"ok": True, "file": f"line_{data.line_no}.wav"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"filename": file.filename, "status": "uploaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
def list_files():
    files = []
    if os.path.exists(UPLOAD_DIR):
        files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return {"files": files}

# --- ARKA PLAN İŞLEMCİSİ ---
def background_processor(req: ProcessRequest):
    global JOB_STATUS
    try:
        n_idx = req.target_nusha_index
        JOB_STATUS.update({
            "busy": True, 
            "step": "starting", 
            "message": f"Nüsha {n_idx} için işlem başlatılıyor...", 
            "progress": 5,
            "current_nusha": n_idx
        })

        uploads = os.path.join(os.getcwd(), "uploads")
        pdf_path = os.path.join(uploads, req.filename)
        ref_path = os.path.join(uploads, req.ref_filename)

        if not os.path.exists(pdf_path):
            raise ValueError(f"PDF dosyası bulunamadı: {req.filename}")

        def update_progress(msg, level="INFO"):
            print(f"[PIPELINE N{n_idx}] {msg}")
            JOB_STATUS["message"] = msg
            if "PDF" in msg: JOB_STATUS["progress"] = 10
            elif "Kraken" in msg: JOB_STATUS["progress"] = 30
            elif "OCR" in msg: JOB_STATUS["progress"] = 50
            elif "ALIGN" in msg: JOB_STATUS["progress"] = 80

        # 1. Pipeline'ı Çalıştır (Hedef Klasöre)
        target_out_dir = get_nusha_out_dir(n_idx)
        
        JOB_STATUS.update({"step": "pipeline", "message": f"Nüsha {n_idx} OCR işlemi yapılıyor...", "progress": 10})
        
        run_pipeline(
            Path(pdf_path), 
            dpi=300, 
            do_ocr=True, 
            status_callback=update_progress,
            output_dir=target_out_dir 
        )

        # 2. Hizalama (Alignment)
        if LINES_MANIFEST.exists():
            JOB_STATUS.update({"step": "aligning", "message": "Tüm nüshalar hizalanıyor...", "progress": 85})
            
            alignment_result = align_ocr_to_tahkik_segment_dp_multi(
                docx_path=Path(ref_path),
                status_callback=update_progress
            )
            
            with open(ALIGNMENT_JSON, "w", encoding="utf-8") as f:
                json.dump(alignment_result, f, ensure_ascii=False, indent=2)
        else:
            JOB_STATUS.update({"message": f"Nüsha {n_idx} hazır! (Hizalama için önce Ana Nüsha yüklenmeli)", "progress": 90})

        JOB_STATUS.update({"busy": False, "step": "done", "message": "İşlem Tamamlandı!", "progress": 100})

    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
        JOB_STATUS.update({"busy": False, "step": "error", "message": f"Hata: {str(e)}", "progress": 0})

@app.post("/api/process")
async def start_process(req: ProcessRequest, background_tasks: BackgroundTasks):
    if JOB_STATUS["busy"]:
        raise HTTPException(status_code=400, detail="Şu an başka bir işlem yapılıyor.")

    background_tasks.add_task(background_processor, req)
    return {"ok": True, "message": f"Nüsha {req.target_nusha_index} işleme alındı."}

@app.get("/api/status")
def get_status():
    return JOB_STATUS

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
