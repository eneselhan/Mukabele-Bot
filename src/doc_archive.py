#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document-level output archiving.

Goal: When the user switches to a different Word/doc, the next run overwrites files under output_lines/
(especially output_lines/lines/). We snapshot the important viewer inputs so old docs remain viewable:
- alignment.json (contains tahkik segments per line)
- spellcheck.json (optional)
- viewer.html (optional; can be regenerated)
- lines/ images (critical for the viewer)
"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Callable

from src.config import (
    OUT,
    ALIGNMENT_JSON,
    VIEWER_HTML,
    VIEWER_DUAL_HTML,
    SPELLCHECK_JSON,
    LINES_DIR,
    LINES_MANIFEST,
    PAGES_DIR,
    NUSHA2_OUT,
    NUSHA2_PAGES_DIR,
    NUSHA2_LINES_DIR,
    NUSHA2_OCR_DIR,
    NUSHA2_LINES_MANIFEST,
    NUSHA2_VIEWER_HTML,
    NUSHA3_OUT,
    NUSHA3_PAGES_DIR,
    NUSHA3_LINES_DIR,
    NUSHA3_OCR_DIR,
    NUSHA3_LINES_MANIFEST,
    NUSHA3_VIEWER_HTML,
    DOC_ARCHIVES_DIR,
    DOC_ARCHIVES_DIR,
    DOC_ARCHIVE_KEEP,
    AUDIO_DIR,
    AUDIO_MANIFEST,
)


def _safe_stem(s: str) -> str:
    s = (s or "").strip()
    # Keep Arabic + basic word chars, replace the rest
    out = []
    for ch in s:
        o = ord(ch)
        if ch.isalnum() or ch in ("_", "-", " "):
            out.append(ch)
        elif 0x0600 <= o <= 0x06FF:
            out.append(ch)
        else:
            out.append("_")
    s2 = "".join(out)
    s2 = "_".join([x for x in s2.replace(" ", "_").split("_") if x])
    return (s2[:60] or "doc")


def archive_current_outputs(
    docx_path: Optional[Path] = None,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> Optional[Path]:
    """
    Create a snapshot directory under output_lines/doc_archives/ and copy critical files.
    Returns archive directory path (or None on failure).
    """
    try:
        DOC_ARCHIVES_DIR.mkdir(exist_ok=True)
    except Exception:
        pass

    # Determine doc name
    docx = Path(docx_path) if docx_path else None
    stem = _safe_stem(docx.stem if docx else "")
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = DOC_ARCHIVES_DIR / f"{ts}__{stem}"

    try:
        dest.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        if status_callback:
            status_callback(f"ARŞİV: Klasör oluşturulamadı: {e}", "WARNING")
        return None

    def _copy_file(src: Path, rel: str):
        try:
            if src.exists() and src.is_file():
                d = dest / rel
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, d)
        except Exception as e:
            if status_callback:
                status_callback(f"ARŞİV: Dosya kopyalanamadı: {src.name} ({e})", "WARNING")

    def _copy_dir(src: Path, rel: str):
        try:
            if src.exists() and src.is_dir():
                d = dest / rel
                if d.exists():
                    return
                shutil.copytree(src, d)
        except Exception as e:
            if status_callback:
                status_callback(f"ARŞİV: Klasör kopyalanamadı: {src.name} ({e})", "WARNING")

    # Copy critical artifacts
    _copy_file(ALIGNMENT_JSON, "alignment.json")
    _copy_file(VIEWER_HTML, "viewer.html")
    _copy_file(VIEWER_DUAL_HTML, "viewer_dual.html")
    _copy_file(SPELLCHECK_JSON, "spellcheck.json")
    _copy_file(LINES_MANIFEST, "lines_manifest.jsonl")
    _copy_dir(LINES_DIR, "lines")
    _copy_dir(PAGES_DIR, "pages")
    _copy_dir(AUDIO_DIR, "audio")
    _copy_file(AUDIO_MANIFEST, "audio_manifest.json")
    # Copy optional audio manifests for other nushas if present
    try:
        for i in range(2, 5):
            am = AUDIO_MANIFEST.parent / f"audio_manifest_n{i}.json"
            _copy_file(am, f"audio_manifest_n{i}.json")
    except Exception:
        pass

    # Optional: 2. nüsha snapshot (so old comparisons keep working)
    try:
        if NUSHA2_OUT.exists():
            _copy_file(NUSHA2_LINES_MANIFEST, "nusha2/lines_manifest.jsonl")
            _copy_dir(NUSHA2_LINES_DIR, "nusha2/lines")
            _copy_dir(NUSHA2_OCR_DIR, "nusha2/ocr")
            _copy_file(NUSHA2_VIEWER_HTML, "nusha2/viewer.html")
            _copy_dir(NUSHA2_PAGES_DIR, "nusha2/pages")
    except Exception:
        pass

    # Optional: 3. nüsha snapshot
    try:
        if NUSHA3_OUT.exists():
            _copy_file(NUSHA3_LINES_MANIFEST, "nusha3/lines_manifest.jsonl")
            _copy_dir(NUSHA3_LINES_DIR, "nusha3/lines")
            _copy_dir(NUSHA3_OCR_DIR, "nusha3/ocr")
            _copy_file(NUSHA3_VIEWER_HTML, "nusha3/viewer.html")
            _copy_dir(NUSHA3_PAGES_DIR, "nusha3/pages")
    except Exception:
        pass

    # Add metadata
    try:
        meta = {
            "ts": ts,
            "docx_path": str(docx) if docx else "",
            "cwd": os.getcwd(),
            "has_alignment": (dest / "alignment.json").exists(),
            "has_spellcheck": (dest / "spellcheck.json").exists(),
            "has_viewer": (dest / "viewer.html").exists(),
            "has_lines": (dest / "lines").exists(),
        }
        (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Regenerate viewer.html inside archive so cached audio manifests are embedded.
    # This prevents TTS from falling back to the local server for archived views.
    try:
        ap = dest / "alignment.json"
        if ap.exists():
            payload = json.loads(ap.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                from src.viewer import write_viewer_html
                write_viewer_html(payload, prefer_alt=False, archive_path=str(dest), out_dir=dest)
    except Exception as e:
        if status_callback:
            status_callback(f"ARŞİV: viewer.html güncellenemedi (TTS): {e}", "WARNING")

    # Retention: keep newest N archives
    try:
        keep = max(1, int(DOC_ARCHIVE_KEEP))
    except Exception:
        keep = 15
    try:
        dirs = sorted([p for p in DOC_ARCHIVES_DIR.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
        for p in dirs[keep:]:
            try:
                shutil.rmtree(p)
            except Exception:
                pass
    except Exception:
        pass

    if status_callback:
        status_callback(f"ARŞİV: Doküman çıktıları kaydedildi: {dest}", "INFO")
    return dest


def restore_archive_to_outputs(
    archive_dir: Path,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> bool:
    """
    Restore an archived snapshot back to output_lines/ (so user can continue working on it).
    Copies files from archive_dir back to their original locations.
    Returns True on success, False on failure.
    """
    if not archive_dir or not archive_dir.exists() or not archive_dir.is_dir():
        if status_callback:
            status_callback(f"GERİ YÜKLEME: Arşiv klasörü bulunamadı: {archive_dir}", "ERROR")
        return False

    def _restore_file(src: Path, dst: Path):
        try:
            if src.exists() and src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                if status_callback:
                    status_callback(f"GERİ YÜKLEME: {dst.name} kopyalandı", "INFO")
        except Exception as e:
            if status_callback:
                status_callback(f"GERİ YÜKLEME: {src.name} kopyalanamadı: {e}", "WARNING")

    def _restore_dir(src: Path, dst: Path):
        try:
            if src.exists() and src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                if status_callback:
                    status_callback(f"GERİ YÜKLEME: {dst.name}/ kopyalandı", "INFO")
        except Exception as e:
            if status_callback:
                status_callback(f"GERİ YÜKLEME: {src.name}/ kopyalanamadı: {e}", "WARNING")

    # Restore primary outputs
    _restore_file(archive_dir / "alignment.json", ALIGNMENT_JSON)
    _restore_file(archive_dir / "viewer.html", VIEWER_HTML)
    _restore_file(archive_dir / "viewer_dual.html", VIEWER_DUAL_HTML)
    _restore_file(archive_dir / "spellcheck.json", SPELLCHECK_JSON)
    _restore_file(archive_dir / "lines_manifest.jsonl", LINES_MANIFEST)
    _restore_dir(archive_dir / "lines", LINES_DIR)
    _restore_dir(archive_dir / "pages", PAGES_DIR)
    _restore_dir(archive_dir / "audio", AUDIO_DIR)
    _restore_file(archive_dir / "audio_manifest.json", AUDIO_MANIFEST)

    # Restore nusha2 if exists
    n2_manifest_src = archive_dir / "nusha2" / "lines_manifest.jsonl"
    if n2_manifest_src.exists():
        _restore_file(n2_manifest_src, NUSHA2_LINES_MANIFEST)
        _restore_dir(archive_dir / "nusha2" / "lines", NUSHA2_LINES_DIR)
        _restore_dir(archive_dir / "nusha2" / "ocr", NUSHA2_OCR_DIR)
        _restore_file(archive_dir / "nusha2" / "viewer.html", NUSHA2_VIEWER_HTML)
        _restore_dir(archive_dir / "nusha2" / "pages", NUSHA2_PAGES_DIR)

    # Restore nusha3 if exists
    n3_manifest_src = archive_dir / "nusha3" / "lines_manifest.jsonl"
    if n3_manifest_src.exists():
        _restore_file(n3_manifest_src, NUSHA3_LINES_MANIFEST)
        _restore_dir(archive_dir / "nusha3" / "lines", NUSHA3_LINES_DIR)
        _restore_dir(archive_dir / "nusha3" / "ocr", NUSHA3_OCR_DIR)
        _restore_file(archive_dir / "nusha3" / "viewer.html", NUSHA3_VIEWER_HTML)
        _restore_dir(archive_dir / "nusha3" / "pages", NUSHA3_PAGES_DIR)

    if status_callback:
        status_callback(f"GERİ YÜKLEME: Arşiv geri yüklendi: {archive_dir.name}", "INFO")
    return True


