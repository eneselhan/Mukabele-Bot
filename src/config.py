# -*- coding: utf-8 -*-
"""
Settings and configuration constants
"""

import os
from pathlib import Path

# =========================
# SETTINGS
# =========================
DPI_DEFAULT = 300
SPREAD_RATIO = 1.15
VISION_TIMEOUT = (20, 240)
VISION_RETRIES = 5
VISION_BACKOFF_BASE = 1.6
VISION_MAX_DIM = 2000
VISION_JPEG_QUALITY = 85

# --- Alignment Settings ---
BEAM_K = 30
CAND_TOPK = 12
POS_BAND_WORDS = 450
POS_LAMBDA = 0.020
LEN_MINUS = 5
LEN_PLUS = 7
LEN_MIN_ABS = 4
LEN_MAX_ABS = 36
W_MAIN = 0.72
W_PREFIX = 0.28
PREFIX_WORDS = 4

# --- AI & Spellcheck ---
ENABLE_SPELLCHECK_DEFAULT = True
SPELLCHECK_SAVE_JSON = True
GEMINI_PROVIDER = (os.getenv("GEMINI_PROVIDER", "ai_studio") or "ai_studio").strip().lower()
SPELLCHECK_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
VERTEX_PROJECT_ID = (os.getenv("VERTEX_PROJECT_ID", "") or "").strip()
VERTEX_LOCATION = (os.getenv("VERTEX_LOCATION", "us-central1") or "us-central1").strip()
VERTEX_GEMINI_MODEL = (os.getenv("VERTEX_GEMINI_MODEL", "gemini-3-pro-preview") or "gemini-3-pro-preview").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101")
SPELLCHECK_MAX_PARAS = 999999

# =========================
# OUTPUT DIRECTORIES
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "tahkik_data" / "projects"
OUT = BASE_DIR / "output_lines"

# --- MAIN NUSHA (Nüsha 1) ---
PAGES_DIR = OUT / "pages"
LINES_DIR = OUT / "lines"
OCR_DIR = OUT / "ocr"
AUDIO_DIR = OUT / "audio"
LINES_MANIFEST = OUT / "lines_manifest.jsonl"
AUDIO_MANIFEST = OUT / "audio_manifest.json"
ALIGNMENT_JSON = OUT / "alignment.json"

# [FIX] Missing HTML definitions added here
VIEWER_HTML = OUT / "viewer.html"
VIEWER_DUAL_HTML = OUT / "viewer_dual.html"
INDEX_HTML = OUT / "index.html"

SPELLCHECK_JSON = OUT / "spellcheck.json"
SPELLCHECK_BACKUPS_DIR = OUT / "spellcheck_backups"
DOC_ARCHIVES_DIR = OUT / "doc_archives"
DOC_ARCHIVE_KEEP = int(os.getenv("DOC_ARCHIVE_KEEP", "15") or "15")

# --- NUSHA 2 ---
NUSHA2_OUT = OUT / "nusha2"
NUSHA2_PAGES_DIR = NUSHA2_OUT / "pages"
NUSHA2_LINES_DIR = NUSHA2_OUT / "lines"
NUSHA2_OCR_DIR = NUSHA2_OUT / "ocr"
NUSHA2_LINES_MANIFEST = NUSHA2_OUT / "lines_manifest.jsonl"

# --- NUSHA 3 ---
NUSHA3_OUT = OUT / "nusha3"
NUSHA3_PAGES_DIR = NUSHA3_OUT / "pages"
NUSHA3_LINES_DIR = NUSHA3_OUT / "lines"
NUSHA3_OCR_DIR = NUSHA3_OUT / "ocr"
NUSHA3_LINES_MANIFEST = NUSHA3_OUT / "lines_manifest.jsonl"

# --- NUSHA 4 ---
NUSHA4_OUT = OUT / "nusha4"
NUSHA4_PAGES_DIR = NUSHA4_OUT / "pages"
NUSHA4_LINES_DIR = NUSHA4_OUT / "lines"
NUSHA4_OCR_DIR = NUSHA4_OUT / "ocr"
NUSHA4_LINES_MANIFEST = NUSHA4_OUT / "lines_manifest.jsonl"

# Klasörleri Oluştur
for p in [OUT, PAGES_DIR, LINES_DIR, OCR_DIR, AUDIO_DIR, SPELLCHECK_BACKUPS_DIR, DOC_ARCHIVES_DIR]:
    p.mkdir(exist_ok=True)

for p in [NUSHA2_OUT, NUSHA2_PAGES_DIR, NUSHA2_LINES_DIR, NUSHA2_OCR_DIR]:
    p.mkdir(exist_ok=True)

for p in [NUSHA3_OUT, NUSHA3_PAGES_DIR, NUSHA3_LINES_DIR, NUSHA3_OCR_DIR]:
    p.mkdir(exist_ok=True)

for p in [NUSHA4_OUT, NUSHA4_PAGES_DIR, NUSHA4_LINES_DIR, NUSHA4_OCR_DIR]:
    p.mkdir(exist_ok=True)

# =========================
# HELPER: NUSHA MAP
# =========================
NUSHA_MAP = {
    1: OUT,          # output_lines/
    2: NUSHA2_OUT,   # output_lines/nusha2/
    3: NUSHA3_OUT,   # output_lines/nusha3/
    4: NUSHA4_OUT    # output_lines/nusha4/
}

def get_nusha_out_dir(nusha_index: int) -> Path:
    return NUSHA_MAP.get(nusha_index, OUT)