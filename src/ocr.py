# -*- coding: utf-8 -*-
"""
Google Vision OCR (image -> text)
"""

import os
import base64
import json
import time
import io
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any
from PIL import Image
import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ConnectionError
from src.config import (
    VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE,
    VISION_MAX_DIM, VISION_JPEG_QUALITY, OCR_DIR, LINES_MANIFEST
)
from src.kraken_processor import load_line_records_ordered


VISION_ENDPOINT_TPL = "https://vision.googleapis.com/v1/images:annotate?key={api_key}"

def _prepare_image_for_vision(lp: Path, max_dim: int, jpeg_quality: int) -> bytes:
    img = Image.open(lp).convert("RGB")
    w, h = img.size
    m = max(w, h)
    if m > max_dim:
        scale = max_dim / float(m)
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()

def _b64_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def ocr_lines_with_google_vision_api(
    ordered_line_paths: List[Path],
    api_key: str,
    timeout: Tuple[int, int] = VISION_TIMEOUT,
    retries: int = VISION_RETRIES,
    backoff_base: float = VISION_BACKOFF_BASE,
    max_dim: int = VISION_MAX_DIM,
    jpeg_quality: int = VISION_JPEG_QUALITY,
    sleep_s: float = 0.10,
    status_callback: Optional[Callable[[str, str], None]] = None,
    ocr_dir: Path = OCR_DIR,
) -> Tuple[int, int]:
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("Google Vision API Key bulunamadı.")

    url = VISION_ENDPOINT_TPL.format(api_key=api_key)

    def parse_text(data: dict) -> str:
        try:
            resp0 = (data.get("responses") or [None])[0] or {}
            if "fullTextAnnotation" in resp0 and isinstance(resp0["fullTextAnnotation"], dict):
                return (resp0["fullTextAnnotation"].get("text") or "").strip()
            tas = resp0.get("textAnnotations") or []
            if tas and isinstance(tas, list) and isinstance(tas[0], dict):
                return (tas[0].get("description") or "").strip()
        except Exception:
            pass
        return ""

    total = len(ordered_line_paths)
    ok = 0

    for idx, lp in enumerate(ordered_line_paths):
        if status_callback and (idx + 1) % 10 == 0:
            status_callback(f"  OCR: {idx + 1}/{total} satır işlendi...", "INFO")
        img_bytes = _prepare_image_for_vision(lp, max_dim=max_dim, jpeg_quality=jpeg_quality)
        img_b64 = _b64_bytes(img_bytes)

        payload = {
            "requests": [{
                "image": {"content": img_b64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": ["ar"]}
            }]
        }

        last_err = None
        data = None

        for attempt in range(retries):
            try:
                r = requests.post(url, json=payload, timeout=timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    last_err = RuntimeError(f"Vision temporary error ({r.status_code}): {r.text[:300]}")
                    time.sleep((backoff_base ** attempt))
                    continue
                if r.status_code != 200:
                    raise RuntimeError(f"Vision API error ({r.status_code}): {r.text[:800]}")
                data = r.json()
                last_err = None
                break
            except (ReadTimeout, ConnectTimeout, ConnectionError) as e:
                last_err = e
                time.sleep((backoff_base ** attempt))

        try:
            ocr_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        out_txt = ocr_dir / f"{lp.stem}.txt"
        out_json = ocr_dir / f"{lp.stem}.json"

        if last_err is not None or data is None:
            out_json.write_text(json.dumps({"error": str(last_err)}, ensure_ascii=False, indent=2), encoding="utf-8")
            out_txt.write_text("", encoding="utf-8")
            continue

        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        text = parse_text(data)
        out_txt.write_text(text, encoding="utf-8")
        ok += 1

        time.sleep(sleep_s)

    return ok, total


# =========================
# Load OCR lines in manifest order
# =========================
def load_ocr_lines_ordered(
    manifest_path: Path = LINES_MANIFEST,
    ocr_dir: Path = OCR_DIR
) -> List[Dict[str, Any]]:
    recs = load_line_records_ordered(manifest_path=manifest_path)
    out: List[Dict[str, Any]] = []
    for r in recs:
        lp = Path(r["line_image"])
        txt_path = ocr_dir / f"{lp.stem}.txt"
        text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
        out.append({
            "line_image": str(lp),
            "ocr_text": text,
            # Keep page context for full-page viewer overlays
            "page_image": r.get("page_image", ""),
            "page_name": r.get("page_name", ""),
            "bbox": r.get("bbox", None),
            "line_index": r.get("line_index", None),
        })
    return out

