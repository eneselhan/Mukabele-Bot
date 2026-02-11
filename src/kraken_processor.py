# -*- coding: utf-8 -*-
"""
Kraken: page -> line PNGs + manifest
BLLA (Baseline Layout Analyzer) kullanarak satır kesme
"""

from PIL import Image
from pathlib import Path
from typing import List, Dict, Any
from src.config import LINES_DIR, LINES_MANIFEST
import json


def split_page_to_lines(page_png: Path, lines_dir: Path = LINES_DIR) -> List[Dict[str, Any]]:
    """
    BLLA (Baseline Layout Analyzer) kullanarak sayfayı satırlara böler.
    satir_kes.py algoritmasıyla aynı yaklaşım.
    """
    img = Image.open(page_png).convert("RGB")

    # Lazy import: kraken pulls heavy deps (numpy/scipy); keep module import lightweight for GUI/viewer.
    from kraken import blla

    # BLLA ile segmentasyon (modern, neural network tabanlı)
    res = blla.segment(img)

    lines = getattr(res, "lines", None)
    if not lines:
        return []

    # y koordinatına göre sırala (boundary poligonunun min y değeri)
    def get_min_y(line):
        if hasattr(line, 'boundary') and line.boundary:
            return min(p[1] for p in line.boundary)
        return 0

    lines_sorted = sorted(lines, key=get_min_y)

    try:
        lines_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    records: List[Dict[str, Any]] = []
    counter = 1

    for line in lines_sorted:
        # boundary poligonu kullan (satir_kes.py ile aynı)
        if not hasattr(line, 'boundary') or not line.boundary:
            continue

        xs = [p[0] for p in line.boundary]
        ys = [p[1] for p in line.boundary]

        x0, x1 = int(min(xs)), int(max(xs))
        y0, y1 = int(min(ys)), int(max(ys))

        # Sınırları kontrol et
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(img.width, x1)
        y1 = min(img.height, y1)

        if x1 <= x0 or y1 <= y0:
            continue

        # Satırı kes
        crop = img.crop((x0, y0, x1, y1))
        out_path = lines_dir / f"{page_png.stem}_line_{counter:04d}.png"
        crop.save(out_path)

        records.append({
            "page_image": str(page_png),
            "page_name": page_png.name,
            "line_image": str(out_path),
            "line_index": counter,
            "bbox": [x0, y0, x1, y1],
        })
        counter += 1

    return records


# =========================
# Order lines by (page_name, y0)
# =========================
def load_line_records_ordered(manifest_path: Path = LINES_MANIFEST) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    if manifest_path.exists():
        for ln in manifest_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))

    def keyfn(r: Dict[str, Any]):
        page = r.get("page_name", "")
        bbox = r.get("bbox", [0, 0, 0, 0])
        y0 = int(bbox[1]) if isinstance(bbox, list) and len(bbox) >= 2 else 0
        return (page, y0, r.get("line_image", ""))

    recs.sort(key=keyfn)
    return recs
