# -*- coding: utf-8 -*-
from __future__ import annotations
"""
PDF processing: PDF to PNG conversion and spread splitting
"""

from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING
from src.config import PAGES_DIR, SPREAD_RATIO

if TYPE_CHECKING:
    # Only for type hints; imported lazily at runtime in _render_page_to_pil.
    from PIL import Image  # pragma: no cover


# =========================
# PDF -> page PNGs + split spreads (right first)
# =========================
def _render_page_to_pil(page, scale: float) -> Image.Image:
    # Lazy imports so the GUI can start even if optional deps are missing.
    # (We show a clear error only when the user runs the Pages stage.)
    from PIL import Image  # type: ignore
    try:
        r = page.render(scale=scale)
    except TypeError:
        r = page.render(scale=scale, rotation=0)

    if hasattr(r, "to_pil"):
        return r.to_pil()
    if hasattr(r, "to_pil_image"):
        return r.to_pil_image()
    if isinstance(r, Image.Image):
        return r
    raise RuntimeError("PDF render output could not be converted to PIL. Update pypdfium2: pip install -U pypdfium2")

def _is_spread(img: Image.Image) -> bool:
    w, h = img.size
    return (w / float(max(1, h))) > SPREAD_RATIO

def _split_spread(img: Image.Image) -> Tuple[Image.Image, Image.Image]:
    w, h = img.size
    mid = w // 2
    right = img.crop((mid, 0, w, h))
    left = img.crop((0, 0, mid, h))
    return right, left

def pdf_to_page_pngs(pdf_path: Path, dpi: int, pages_dir: Path = PAGES_DIR) -> List[Path]:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "pypdfium2 yüklü değil. PDF->PNG için gerekir.\n\n"
            "Kurulum:\n"
            "  pip install -r requirements.txt\n\n"
            "Eğer virtualenv kullanıyorsanız önce ortamı aktif edin, sonra tekrar deneyin."
        ) from e

    pdf = pdfium.PdfDocument(str(pdf_path))
    page_paths: List[Path] = []
    scale = dpi / 72.0

    try:
        for i in range(len(pdf)):
            page = pdf.get_page(i)
            try:
                img = _render_page_to_pil(page, scale=scale).convert("RGB")
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            if _is_spread(img):
                right, left = _split_spread(img)

                pages_dir.mkdir(parents=True, exist_ok=True)
                out_r = pages_dir / f"page_{i+1:04d}_01R.png"
                out_l = pages_dir / f"page_{i+1:04d}_02L.png"

                right.save(out_r)
                left.save(out_l)

                page_paths.append(out_r)
                page_paths.append(out_l)
            else:
                pages_dir.mkdir(parents=True, exist_ok=True)
                out_path = pages_dir / f"page_{i+1:04d}.png"
                img.save(out_path)
                page_paths.append(out_path)
    finally:
        try:
            pdf.close()
        except Exception:
            pass

    return page_paths

