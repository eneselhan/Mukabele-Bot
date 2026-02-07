# -*- coding: utf-8 -*-
"""
Pipeline orchestration
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional, Callable
from src.config import (
    DPI_DEFAULT, VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE,
    VISION_MAX_DIM, VISION_JPEG_QUALITY, 
    PAGES_DIR as DEFAULT_PAGES_DIR,
    LINES_DIR as DEFAULT_LINES_DIR,
    OCR_DIR as DEFAULT_OCR_DIR,
    LINES_MANIFEST as DEFAULT_LINES_MANIFEST
)
from src.utils import hard_cleanup_output
from src.pdf_processor import pdf_to_page_pngs
from src.kraken_processor import split_page_to_lines, load_line_records_ordered
from src.ocr import ocr_lines_with_google_vision_api
from src.keys import get_google_vision_api_key


# =========================
# Pipeline
# =========================
def run_pipeline(
    pdf_path: Path, 
    dpi: int = 300, 
    do_ocr: bool = True, 
    status_callback: Optional[Callable[[str, str], None]] = None,
    output_dir: Optional[Path] = None
):
    """
    Run the full pipeline: PDF -> Pages -> Lines -> OCR.
    If output_dir is provided (e.g. for Nusha 2), it uses that directory structure.
    Otherwise uses default constants from config (Nusha 1).
    """
    
    # 1. Determine Paths & Cleanup
    if output_dir:
        # Custom Output Directory (Multi-View)
        pages_dir = output_dir / "pages"
        lines_dir = output_dir / "lines"
        ocr_dir = output_dir / "ocr"
        lines_manifest = output_dir / "lines_manifest.jsonl"
        
        if status_callback:
            status_callback(f"Çıktı klasörü hazırlanıyor: {output_dir.name}", "INFO")
        
        # Local cleanup for this specific nusha directory
        if output_dir.exists():
            for item in output_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        output_dir.mkdir(parents=True, exist_ok=True)
        # Re-create subdirs
        pages_dir.mkdir(parents=True, exist_ok=True)
        lines_dir.mkdir(parents=True, exist_ok=True)
        ocr_dir.mkdir(parents=True, exist_ok=True)
        
    else:
        # Default Output Directory (Main / Nusha 1)
        if status_callback:
            status_callback("Eski çıktılar (output_lines) temizleniyor...", "INFO")
        hard_cleanup_output()
        
        pages_dir = DEFAULT_PAGES_DIR
        lines_dir = DEFAULT_LINES_DIR
        ocr_dir = DEFAULT_OCR_DIR
        lines_manifest = DEFAULT_LINES_MANIFEST

    if status_callback:
        status_callback(f"PDF işleniyor: {pdf_path.name} (DPI: {dpi})...", "INFO")
        
    # 2. PDF -> Pages
    pages = pdf_to_page_pngs(pdf_path, dpi=dpi, pages_dir=pages_dir)
    
    if status_callback:
        status_callback(f"✓ {len(pages)} sayfa PNG'e dönüştürüldü", "INFO")

    if status_callback:
        status_callback("Sayfalar satırlara bölünüyor (Kraken)...", "INFO")
        
    # 3. Pages -> Lines
    # Initialize manifest
    with lines_manifest.open("w", encoding="utf-8") as mf:
        pass # Create/Clear file

    with lines_manifest.open("a", encoding="utf-8") as mf:
        for idx, page in enumerate(pages):
            if status_callback and (idx + 1) % 5 == 0:
                status_callback(f"  Sayfa {idx + 1}/{len(pages)} işleniyor...", "INFO")
            
            records = split_page_to_lines(page, lines_dir=lines_dir)
            for rec in records:
                mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if status_callback:
        status_callback("Satır kayıtları sıralanıyor...", "INFO")
        
    ordered_recs = load_line_records_ordered(manifest_path=lines_manifest)
    ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
    
    if status_callback:
        status_callback(f"✓ {len(ordered_line_paths)} satır görseli hazır", "INFO")

    ocr_ok = 0
    if do_ocr:
        if status_callback:
            status_callback(f"OCR yapılıyor: {len(ordered_line_paths)} satır...", "INFO")
        vkey = get_google_vision_api_key()
        ocr_ok, total = ocr_lines_with_google_vision_api(
            ordered_line_paths,
            api_key=vkey,
            timeout=VISION_TIMEOUT,
            retries=VISION_RETRIES,
            backoff_base=VISION_BACKOFF_BASE,
            max_dim=VISION_MAX_DIM,
            jpeg_quality=VISION_JPEG_QUALITY,
            sleep_s=0.10,
            status_callback=status_callback,
            ocr_dir=ocr_dir  # Pass the correct OCR directory
        )
        if status_callback:
            status_callback(f"✓ OCR tamamlandı: {ocr_ok}/{total} başarılı", "INFO")

    return len(pages), len(ordered_line_paths), ocr_ok
