# -*- coding: utf-8 -*-
"""
Utility functions: file operations and text normalization
"""

import re
from pathlib import Path
from typing import Tuple, Optional
from src.config import PAGES_DIR, LINES_DIR, OCR_DIR, LINES_MANIFEST, ALIGNMENT_JSON, VIEWER_HTML, INDEX_HTML, SPELLCHECK_JSON


# =========================
# HARD CLEANUP
# =========================
def hard_cleanup_output():
    """Deletes old pages/lines/ocr + manifests + viewer/alignment/index/spellcheck."""
    for p in PAGES_DIR.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)

    for p in LINES_DIR.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)

    for p in OCR_DIR.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)

    LINES_MANIFEST.unlink(missing_ok=True)
    ALIGNMENT_JSON.unlink(missing_ok=True)
    VIEWER_HTML.unlink(missing_ok=True)
    INDEX_HTML.unlink(missing_ok=True)
    SPELLCHECK_JSON.unlink(missing_ok=True)


# =========================
# Arabic normalization for matching
# =========================
AR_DIAC = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
NON_AR = re.compile(r"[^\u0600-\u06FF0-9A-Za-z\s]+")

def normalize_ar(s: str) -> str:
    if not s:
        return ""
    s = s.replace("ـ", "")
    s = AR_DIAC.sub("", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و")
    s = s.replace("ة", "ه")
    s = NON_AR.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def take_prefix_words(s: str, n: int) -> str:
    w = s.split()
    return " ".join(w[:n]) if w else ""


# =========================
# File existence checks
# =========================
def check_pages_exist() -> Tuple[bool, int]:
    """Pages klasöründe PNG dosyaları var mı kontrol et"""
    pages = list(PAGES_DIR.glob("*.png"))
    return len(pages) > 0, len(pages)


def check_lines_exist() -> Tuple[bool, int]:
    """Lines klasöründe PNG dosyaları ve manifest var mı kontrol et"""
    lines = list(LINES_DIR.glob("*.png"))
    manifest_exists = LINES_MANIFEST.exists()
    return len(lines) > 0 and manifest_exists, len(lines)


def check_ocr_exist() -> Tuple[bool, int]:
    """OCR klasöründe txt dosyaları var mı kontrol et"""
    ocr_files = list(OCR_DIR.glob("*.txt"))
    return len(ocr_files) > 0, len(ocr_files)


def check_spellcheck_exist() -> Tuple[bool, Optional[Path]]:
    """Spellcheck JSON dosyası var mı kontrol et"""
    exists = SPELLCHECK_JSON.exists()
    return exists, SPELLCHECK_JSON if exists else None


def check_alignment_exist() -> Tuple[bool, Optional[Path]]:
    """Alignment JSON dosyası var mı kontrol et"""
    exists = ALIGNMENT_JSON.exists()
    return exists, ALIGNMENT_JSON if exists else None

