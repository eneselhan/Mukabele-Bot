# -*- coding: utf-8 -*-
"""
Viewer HTML generation
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
from src.config import (
    VIEWER_HTML,
    VIEWER_DUAL_HTML,
    SPELLCHECK_JSON,
    SPELLCHECK_BACKUPS_DIR,
    NUSHA2_VIEWER_HTML,
    LINES_MANIFEST,
    NUSHA2_LINES_MANIFEST,
    NUSHA3_VIEWER_HTML,
    NUSHA3_LINES_MANIFEST,
    NUSHA4_VIEWER_HTML,
    NUSHA4_LINES_MANIFEST,
)
from src.utils import normalize_ar
# Import detect_line_skips locally or with try-except to avoid potential circular imports if alignment.py changes
try:
    from src.alignment import detect_line_skips
except ImportError:
    detect_line_skips = None


def _find_first_token_span(haystack: List[str], needle: List[str]) -> Optional[Tuple[int, int]]:
    """Return (start, end_exclusive) for first exact token-sequence match, else None."""
    if not haystack or not needle:
        return None
    n = len(needle)
    if n > len(haystack):
        return None
    for i in range(0, len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return (i, i + n)
    return None


def _find_next_token_span(haystack: List[str], needle: List[str], start_at: int) -> Optional[Tuple[int, int]]:
    """Return (start, end_exclusive) for first exact token-sequence match at/after start_at, else None."""
    if not haystack or not needle:
        return None
    n = len(needle)
    if n > len(haystack):
        return None
    start_at = max(0, min(int(start_at or 0), len(haystack)))
    for i in range(start_at, len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return (i, i + n)
    return None


def _inject_line_marks(alignment: Dict[str, Any], per_paragraph: List[Dict[str, Any]], aligned_override: Optional[List[Dict[str, Any]]] = None):
    """
    Make highlighting occurrence-based (by global token index), NOT word-based.
    We compute the first occurrence of each (wrong) inside its paragraph, then
    map those global token indices into each aligned line's [start_word,end_word).
    Populates:
      - item['line_marks']: [{ 'gidx': int, 'wrong':..., 'suggestion':..., 'reason':..., 'sources':..., 'paragraph_index':... }, ...]
    """
    # Build global token stream + paragraph start offsets
    global_norm_tokens: List[str] = []
    para_start: Dict[int, int] = {}
    para_tokens_norm: Dict[int, List[str]] = {}
    para_tokens_raw: Dict[int, List[str]] = {}

    for p_obj in per_paragraph:
        if not isinstance(p_obj, dict):
            continue
        p_idx = p_obj.get("paragraph_index")
        if not isinstance(p_idx, int):
            continue
        text = p_obj.get("text") or ""
        toks_raw = text.split()
        toks_norm = [normalize_ar(t) for t in toks_raw]
        para_start[p_idx] = len(global_norm_tokens)
        para_tokens_norm[p_idx] = toks_norm
        para_tokens_raw[p_idx] = toks_raw
        global_norm_tokens.extend(toks_norm)

    # Compute occurrence map: global token index -> error meta
    # If the same WRONG is listed multiple times in the same paragraph, map them
    # to successive occurrences (not always the first one).
    occ: Dict[int, Dict[str, Any]] = {}
    unmapped: List[Dict[str, Any]] = []
    for p_obj in per_paragraph:
        if not isinstance(p_obj, dict):
            continue
        p_idx = p_obj.get("paragraph_index")
        if not isinstance(p_idx, int) or p_idx not in para_start:
            continue
        errs = p_obj.get("errors") or []
        if not isinstance(errs, list) or not errs:
            continue
        hay = para_tokens_norm.get(p_idx) or []
        base = para_start[p_idx]
        next_start: Dict[Tuple[str, ...], int] = {}
        for e in errs:
            if not isinstance(e, dict):
                continue
            wrong = (e.get("wrong") or "").strip()
            if not wrong:
                continue
            needle = normalize_ar(wrong).split()
            if not needle:
                continue
            key = tuple(needle)
            s0 = next_start.get(key, 0)
            span = _find_next_token_span(hay, needle, s0)
            if not span:
                unmapped.append(
                    {
                        "paragraph_index": p_idx,
                        "wrong": e.get("wrong") or "",
                        "wrong_norm": normalize_ar(e.get("wrong") or ""),
                        "suggestion": e.get("suggestion") or "",
                        "reason": e.get("reason") or "",
                        "sources": e.get("sources") or [],
                    }
                )
                continue
            s, t = span
            next_start[key] = max(t, s + 1)
            for off in range(s, t):
                gidx = base + off
                if gidx in occ:
                    continue
                occ[gidx] = {
                    "gidx": gidx,
                    "wrong": e.get("wrong") or "",
                    "wrong_norm": normalize_ar(e.get("wrong") or ""),
                    "suggestion": e.get("suggestion") or "",
                    "reason": e.get("reason") or "",
                    "sources": e.get("sources") or [],
                    "paragraph_index": p_idx,
                }

    # Attach per-line marks by intersecting [start,end) with occ keys
    aligned = aligned_override if aligned_override is not None else (alignment.get("aligned") or [])
    for item in aligned:
        best = item.get("best") if isinstance(item, dict) else None
        if not isinstance(best, dict):
            continue
        start = best.get("start_word")
        end = best.get("end_word")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        start = max(0, min(start, len(global_norm_tokens)))
        end = max(start, min(end, len(global_norm_tokens)))
        marks: List[Dict[str, Any]] = []
        for gidx in range(start, end):
            if gidx in occ:
                marks.append(occ[gidx])
        item["line_marks"] = marks

    alignment["spellcheck_unmapped"] = unmapped


# =========================
# Viewer HTML
# =========================
def write_viewer_html(
    alignment: Dict[str, Any],
    *,
    prefer_alt: bool = False,
    prefer_alt3: bool = False,
    prefer_alt4: bool = False,
    dual: bool = False,
    archive_path: Optional[str] = None,
    out_dir: Optional[Path] = None,
):
    # Spellcheck verisi: alignment payload'ında yoksa veya sources boşsa,
    # viewer'ın bulunduğu klasördeki `spellcheck.json` (arşivdeyse arşivdeki) içinden yükle.
    try:
        # If generating into an archive directory, prefer that archive's spellcheck snapshot.
        spellcheck_json_path = (out_dir / "spellcheck.json") if out_dir else SPELLCHECK_JSON
        spellcheck_backups_dir = (out_dir / "spellcheck_backups") if out_dir else SPELLCHECK_BACKUPS_DIR

        sc = alignment.get("spellcheck")
        has_sources = False
        if isinstance(sc, list) and sc:
            for e in sc:
                if isinstance(e, dict) and e.get("sources"):
                    has_sources = True
                    break
        
        pp_data = []
        if spellcheck_json_path.exists():
            sp = json.loads(spellcheck_json_path.read_text(encoding="utf-8"))
            runs = sp.get("runs")
            if isinstance(runs, list):
                alignment["spellcheck_runs"] = [x for x in runs if isinstance(x, dict)]
            pp = sp.get("per_paragraph")
            if isinstance(pp, list):
                alignment["spellcheck_per_paragraph"] = pp
                pp_data = pp

            # Load recent archived spellcheck backups (for viewer "eski sonuçlar" button)
            try:
                arch: List[Dict[str, Any]] = []
                files = []
                if spellcheck_backups_dir.exists():
                    files = sorted(
                        [p for p in spellcheck_backups_dir.glob("*__new.json") if p.is_file()],
                        key=lambda p: p.name,
                        reverse=True,
                    )
                for p in files[:10]:
                    try:
                        obj = json.loads(p.read_text(encoding="utf-8"))
                        if not isinstance(obj, dict):
                            continue
                        runs2 = obj.get("runs") or []
                        run0 = runs2[-1] if isinstance(runs2, list) and runs2 else {}
                        em = obj.get("errors_merged") or []
                        pp2 = obj.get("per_paragraph") or []
                        pp_errs: List[Dict[str, Any]] = []
                        if isinstance(pp2, list):
                            for blk in pp2:
                                if not isinstance(blk, dict):
                                    continue
                                pidx = blk.get("paragraph_index")
                                errs = blk.get("errors") or []
                                if not isinstance(pidx, int):
                                    continue
                                if not isinstance(errs, list):
                                    errs = []
                                # Store only errors; text will come from current spellPP (same docx)
                                pp_errs.append({"paragraph_index": pidx, "errors": errs})
                        arch.append(
                            {
                                "file": p.name,
                                "ts": (run0.get("ts") if isinstance(run0, dict) else None) or obj.get("ts") or p.name.split("__")[0],
                                "start_paragraph": (run0.get("start_paragraph") if isinstance(run0, dict) else None) or obj.get("start_paragraph") or 1,
                                "selected_paragraphs": (run0.get("selected_paragraphs") if isinstance(run0, dict) else None) if isinstance(run0, dict) else None,
                                "provider": (run0.get("provider") if isinstance(run0, dict) else None) or None,
                                "models": (run0.get("models") if isinstance(run0, dict) else None) or {},
                                "error_count": len(em) if isinstance(em, list) else 0,
                                "errors_merged": em if isinstance(em, list) else [],
                                "per_paragraph_errors": pp_errs,
                            }
                        )
                    except Exception:
                        continue
                if arch:
                    alignment["spellcheck_archives"] = arch
            except Exception:
                pass

            # spellcheck listesi için: sadece sources eksikse spellcheck.json'dan doldur
            if not has_sources:
                # Önce errors_merged kullan (eğer sources doluysa)
                em = sp.get("errors_merged")
                if isinstance(em, list) and any(isinstance(e, dict) and e.get("sources") for e in em):
                    alignment["spellcheck"] = em
                else:
                    # Aksi halde per_paragraph içinden flatten + sources union yap
                    mp = {}
                    pp_list = pp if isinstance(pp, list) else []
                    for blk in pp_list:
                        errs = (blk or {}).get("errors") if isinstance(blk, dict) else None
                        if not isinstance(errs, list):
                            continue
                        for e in errs:
                            if not isinstance(e, dict):
                                continue
                            wn = (e.get("wrong_norm") or normalize_ar(e.get("wrong") or "")).strip()
                            if not wn:
                                continue
                            srcs = e.get("sources") or []
                            if isinstance(srcs, str):
                                srcs = [srcs]
                            srcs = sorted({s for s in srcs if isinstance(s, str) and s.strip()})
                            if wn not in mp:
                                mp[wn] = {
                                    "wrong": e.get("wrong", ""),
                                    "wrong_norm": wn,
                                    "suggestion": e.get("suggestion", ""),
                                    "reason": e.get("reason", ""),
                                    "sources": srcs,
                                }
                            else:
                                # suggestion/reason boşsa doldur
                                if not mp[wn].get("suggestion") and (e.get("suggestion") or "").strip():
                                    mp[wn]["suggestion"] = (e.get("suggestion") or "").strip()
                                if not mp[wn].get("reason") and (e.get("reason") or "").strip():
                                    mp[wn]["reason"] = (e.get("reason") or "").strip()
                                # sources union
                                cur = set(mp[wn].get("sources") or [])
                                cur.update(srcs)
                                mp[wn]["sources"] = sorted(cur)
                    alignment["spellcheck"] = list(mp.values())
        
        # Inject context-aware errors into lines (primary + alt copies, if present)
        if pp_data:
            _inject_line_marks(alignment, pp_data, aligned_override=alignment.get("aligned") or [])
            try:
                alt = alignment.get("aligned_alt")
                if isinstance(alt, list) and alt:
                    _inject_line_marks(alignment, pp_data, aligned_override=alt)
            except Exception:
                pass
            try:
                alt3 = alignment.get("aligned_alt3")
                if isinstance(alt3, list) and alt3:
                    _inject_line_marks(alignment, pp_data, aligned_override=alt3)
            except Exception:
                pass
            try:
                alt4 = alignment.get("aligned_alt4")
                if isinstance(alt4, list) and alt4:
                    _inject_line_marks(alignment, pp_data, aligned_override=alt4)
            except Exception:
                pass
            
            
    except Exception:
        # Viewer üretimi asla crash etmesin
        pass

    # Viewer mode flag for JS (which list is the "main" mapping)
    try:
        if dual:
            alignment["view_mode"] = "dual"
        elif prefer_alt4:
            alignment["view_mode"] = "alt4"
        elif prefer_alt3:
            alignment["view_mode"] = "alt3"
        else:
            alignment["view_mode"] = "alt" if prefer_alt else "single"

        alignment["mapping_kind"] = "alt4" if prefer_alt4 else ("alt3" if prefer_alt3 else ("alt" if prefer_alt else "primary"))
        alignment["default_nusha"] = 4 if prefer_alt4 else (3 if prefer_alt3 else (2 if prefer_alt else 1))
        if dual:
            # Primary list as the base; show both copies side-by-side per row.
            alignment["aligned_view"] = alignment.get("aligned")
            alignment["default_nusha"] = 1
            alignment["mapping_kind"] = "primary"
        elif prefer_alt4:
            # Use 4th-copy alignment as the main list (if available).
            if isinstance(alignment.get("aligned_alt4"), list) and alignment.get("aligned_alt4"):
                alignment["aligned_view"] = alignment.get("aligned_alt4")
            else:
                alignment["aligned_view"] = alignment.get("aligned")
                alignment["default_nusha"] = 1
                alignment["mapping_kind"] = "primary"
        elif prefer_alt3:
            # Use 3rd-copy alignment as the main list (if available).
            if isinstance(alignment.get("aligned_alt3"), list) and alignment.get("aligned_alt3"):
                alignment["aligned_view"] = alignment.get("aligned_alt3")
            else:
                alignment["aligned_view"] = alignment.get("aligned")
                alignment["default_nusha"] = 1
                alignment["mapping_kind"] = "primary"
        elif prefer_alt:
            # Use alt alignment as the main list; keep primary reachable via item.alt (bidirectional links).
            if isinstance(alignment.get("aligned_alt"), list) and alignment.get("aligned_alt"):
                alignment["aligned_view"] = alignment.get("aligned_alt")
            else:
                alignment["aligned_view"] = alignment.get("aligned")
                alignment["default_nusha"] = 1
                alignment["mapping_kind"] = "primary"
        else:
            alignment["aligned_view"] = alignment.get("aligned")
    except Exception:
        alignment["aligned_view"] = alignment.get("aligned")
        alignment["default_nusha"] = 1
        alignment["mapping_kind"] = "primary"
        alignment["view_mode"] = "single"

    # Backfill page context (page_image/bbox) from manifests for older alignment.json files
    def _backfill_from_manifest(aligned_list: Any, manifest_path, nusha2: bool = False):
        if not isinstance(aligned_list, list) or not aligned_list:
            return
        try:
            if not manifest_path.exists():
                return
            mp = {}
            for ln in manifest_path.read_text(encoding="utf-8").splitlines():
                ln = (ln or "").strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                li = (r.get("line_image") or "")
                if not isinstance(li, str) or not li:
                    continue
                base = li.replace("\\", "/").split("/")[-1]
                mp[base] = {
                    "page_image": r.get("page_image", ""),
                    "page_name": r.get("page_name", ""),
                    "bbox": r.get("bbox", None),
                    "line_index": r.get("line_index", None),
                }
            if not mp:
                return
            for it in aligned_list:
                if not isinstance(it, dict):
                    continue
                # already has context
                if it.get("page_image") and it.get("bbox") is not None:
                    continue
                li = (it.get("line_image") or "")
                if not isinstance(li, str) or not li:
                    continue
                base = li.replace("\\", "/").split("/")[-1]
                rec = mp.get(base)
                if not rec:
                    continue
                it.setdefault("page_image", rec.get("page_image", ""))
                it.setdefault("page_name", rec.get("page_name", ""))
                it.setdefault("bbox", rec.get("bbox", None))
                it.setdefault("line_index", rec.get("line_index", None))
        except Exception:
            return

    try:
        _backfill_from_manifest(alignment.get("aligned"), LINES_MANIFEST, nusha2=False)
        _backfill_from_manifest(alignment.get("aligned_alt"), NUSHA2_LINES_MANIFEST, nusha2=True)
        _backfill_from_manifest(alignment.get("aligned_alt3"), NUSHA3_LINES_MANIFEST, nusha2=True)
        _backfill_from_manifest(alignment.get("aligned_alt4"), NUSHA4_LINES_MANIFEST, nusha2=True)
    except Exception:
        pass

    # Add archive_path if provided (for "Tekrar İşlem Yap" button)
    if archive_path:
        alignment["archive_path"] = archive_path

    # Inject skipped line data if present; if not (e.g. old archive), try to calculate on the fly
    try:
        if not alignment.get("skips_n1_vs_n2"):
            if detect_line_skips and HAS_N2 and isinstance(alignment.get("aligned"), list) and isinstance(alignment.get("aligned_alt"), list):
                alignment["skips_n1_vs_n2"] = detect_line_skips(alignment["aligned"], alignment["aligned_alt"], None)
            else:
                alignment["skips_n1_vs_n2"] = []
        
        if not alignment.get("skips_n2_vs_n1"):
            if detect_line_skips and HAS_N2 and isinstance(alignment.get("aligned"), list) and isinstance(alignment.get("aligned_alt"), list):
                alignment["skips_n2_vs_n1"] = detect_line_skips(alignment["aligned_alt"], alignment["aligned"], None)
            else:
                alignment["skips_n2_vs_n1"] = []

        if not alignment.get("skips_n1_vs_n3"):
            if detect_line_skips and HAS_N3 and isinstance(alignment.get("aligned"), list) and isinstance(alignment.get("aligned_alt3"), list):
                alignment["skips_n1_vs_n3"] = detect_line_skips(alignment["aligned"], alignment["aligned_alt3"], None)
            else:
                alignment["skips_n1_vs_n3"] = []

        if not alignment.get("skips_n1_vs_n4"):
            if detect_line_skips and HAS_N4 and isinstance(alignment.get("aligned"), list) and isinstance(alignment.get("aligned_alt4"), list):
                alignment["skips_n1_vs_n4"] = detect_line_skips(alignment["aligned"], alignment["aligned_alt4"], None)
            else:
                alignment["skips_n1_vs_n4"] = []
    except Exception:
        pass

    # Backward-compat: older alignment.json may lack has_alt/has_alt3 but still include aligned_alt/aligned_alt3
    try:
        if isinstance(alignment.get("aligned_alt"), list) and alignment.get("aligned_alt") and not alignment.get("has_alt"):
            alignment["has_alt"] = True
        if isinstance(alignment.get("aligned_alt3"), list) and alignment.get("aligned_alt3") and not alignment.get("has_alt3"):
            alignment["has_alt3"] = True
    except Exception:
        pass

    # Inject Cached Audio Data (if available) -> cached_audio
    # This allows the viewer to skip synthesis for pages that are already vocalized.
    try:
        from src.config import AUDIO_MANIFEST
        am_path = (out_dir / "audio_manifest.json") if out_dir else AUDIO_MANIFEST
        if am_path.exists():
             alignment["cached_audio"] = json.loads(am_path.read_text(encoding="utf-8"))
        
        # Inject other nushas
        for i in range(2, 5):
            am_name = f"audio_manifest_n{i}.json"
            am_path_ni = (out_dir / am_name) if out_dir else (AUDIO_MANIFEST.parent / am_name)
            if am_path_ni.exists():
                alignment[f"cached_audio_n{i}"] = json.loads(am_path_ni.read_text(encoding="utf-8"))
    except Exception:
        pass
    
    data_json = json.dumps(alignment, ensure_ascii=False)

    html = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Satir - Tahkik Hizalama</title>
<style>
  :root { --textSize: 23px; }
  body { font-family: Arial, sans-serif; margin: 0; font-size: var(--textSize); }
  header { padding: 12px 16px; border-bottom: 1px solid #ddd; display:flex; gap:12px; align-items:center; flex-wrap: wrap; }
  header .muted { color:#666; font-size: 0.86em; }
  .wrap { display:flex; height: calc(100vh - 78px); }
  body.hideHeader header { display: none; }
  body.hideHeader .wrap { height: 100vh; }
  body.hideList #listPane { display: none; }
  body.hideList #splitter { display: none; }
  body.hideList #pagePane { width: 100% !important; }
  .listToggleBtn {
    position: sticky;
    top: 10px;
    float: right;
    z-index: 900;
    margin: 6px 0 8px 8px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid #ddd;
    background: rgba(255,255,255,0.94);
    box-shadow: 0 10px 22px rgba(0,0,0,0.08);
    backdrop-filter: blur(6px);
    cursor: pointer;
    user-select: none;
  }
  .listToggleTab {
    position: fixed;
    right: 10px;
    top: 96px;
    z-index: 1306;
    display: none;
    padding: 8px 10px;
    border-radius: 999px;
    border: 1px solid #ddd;
    background: rgba(255,255,255,0.94);
    box-shadow: 0 10px 22px rgba(0,0,0,0.12);
    backdrop-filter: blur(6px);
    cursor: pointer;
    user-select: none;
  }
  body.hideList .listToggleTab { display: inline-block; }
  #btnShowHeader {
    position: fixed;
    left: 10px;
    top: 10px;
    z-index: 1305;
    display: none;
    padding: 6px 10px;
    border-radius: 12px;
    border: 1px solid #ddd;
    background: rgba(255,255,255,0.94);
    box-shadow: 0 10px 22px rgba(0,0,0,0.12);
    backdrop-filter: blur(6px);
  }
  body.hideHeader #btnShowHeader { display: inline-block; }
  .leftPane { width: 52%; overflow:auto; padding: 10px; }
  .rightPane { width: 48%; overflow:auto; padding: 10px; }
  .splitter {
    width: 10px;
    cursor: col-resize;
    background: linear-gradient(to right, rgba(0,0,0,0.00), rgba(0,0,0,0.06), rgba(0,0,0,0.00));
    border-left: 1px solid #eee;
    border-right: 1px solid #eee;
    user-select: none;
    touch-action: none;
  }
  .splitter:hover { background: linear-gradient(to right, rgba(0,0,0,0.00), rgba(0,0,0,0.10), rgba(0,0,0,0.00)); }
  /* Compact list cards (keep text size, reduce box spacing) */
  .item { border:1px solid #e6e6e6; border-radius: 10px; padding: 8px 10px; margin: 6px 0; cursor:pointer; }
  .item.active { border-color:#333; box-shadow: 0 0 0 2px rgba(0,0,0,.08); }
  img { width: 100%; border:1px solid #eee; border-radius: 8px; }
  img.clickable { cursor: pointer; }

  .pageWrap { position: relative; }
  .pageImg { width: 100%; display:block; border:1px solid #eee; border-radius: 12px; }
  .pageSvg { position:absolute; inset:0; width:100%; height:100%; pointer-events: auto; }

  .arbox {
    direction: rtl;
    unicode-bidi: isolate;
    font-family: "Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif;
  }

  pre {
    white-space: pre-wrap;
    background:#fafafa;
    border:1px solid #eee;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 1em; /* inherit from body via --textSize */
    line-height: 1.8;
    margin: 6px 0;
  }

  .row { display:flex; gap:10px; flex-wrap: wrap; }
  .dualRow { display:flex; gap:12px; flex-wrap: wrap; }
  .col { flex: 1 1 420px; min-width: 360px; }
  .colTitle { font-weight: 900; margin: 10px 0 6px; }
  .pill { font-size: 0.82em; padding:4px 8px; border:1px solid #ddd; border-radius: 999px; background:#fff; }
  .cand { border:1px solid #e6e6e6; border-radius: 10px; padding: 10px; margin: 10px 0; cursor:pointer; }
  .cand:hover { border-color:#999; }
  .btn { padding:8px 12px; border:1px solid #333; border-radius: 10px; background:#333; color:#fff; cursor:pointer; }
  .btn.secondary { background:#fff; color:#333; }
  .btn.small { padding:6px 10px; font-size: 0.88em; }
  .btn.xsmall { padding:4px 8px; font-size: 0.78em; border-radius: 999px; }
  .small { font-size: 0.88em; color:#555; }

  .label { font-weight:700; margin-top: 10px; }

  .err { padding: 0 3px; border-radius: 6px; }
  .err-all { background: #bff3c6; } /* all 3 models agree */
  .err-both { background: #ffb3b3; }
  .err-gem  { background: #ffd9a8; }
  .err-oa   { background: #c7d7ff; }
  .err-claude { background: #d6c7ff; }
  /* Override color for 2-model agreements */
  .err-gptgem { background: #C49A6C; }     /* kahverengi (GPT+Gemini) */
  .err-gptclaude { background: #CD7F32; }  /* bronz (GPT+Claude) */
  .err-unknown { outline: 2px dashed rgba(0,0,0,0.30); }

  .errpill { border: 1px solid #d22; color: #d22; background: #fff; }

  /* Line skip highlighting */
  .highlight-skip {
    background: #ffe6e6 !important;
    box-shadow: 0 0 0 3px #ffcccc !important;
    transition: background 0.5s ease;
  }
  .highlight-skip img { border-color: #ffcccc !important; }

  .legend { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .legendItem { display:inline-flex; gap:6px; align-items:center; padding:4px 8px; border:1px solid #ddd; border-radius: 999px; background:#fff; font-size: 0.82em; color:#333; }
  .swatch { width: 14px; height: 14px; border-radius: 4px; border:1px solid rgba(0,0,0,0.18); display:inline-block; }
  .sw-all { background:#bff3c6; }
  .sw-both { background:#ffb3b3; }
  .sw-gem { background:#ffd9a8; }
  .sw-oa { background:#c7d7ff; }
  .sw-claude { background:#d6c7ff; }
  .sw-gptgem { background:#C49A6C; }
  .sw-gptclaude { background:#CD7F32; }

  /* --- Click-to-explain popup (on highlighted words) --- */
  .popOverlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.25);
    z-index: 1100;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 14px;
  }
  .popOverlay.open { display: flex; }
  .popPanel {
    width: min(720px, 96vw);
    max-height: min(520px, 88vh);
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 14px;
    box-shadow: 0 18px 55px rgba(0,0,0,0.22);
    overflow: auto;
    padding: 12px;
  }
  .popHeader { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom: 10px; }
  .popTitle { font-weight: 900; }
  .popBody { display:flex; flex-direction:column; gap:10px; }
  .popBox { background:#fafafa; border:1px solid #eee; border-radius: 12px; padding: 10px; }
  .popBox .k { font-weight: 800; margin-bottom: 6px; }
  .popBox .v { direction: rtl; unicode-bidi: isolate; font-family: "Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif; font-size: 1em; line-height: 1.8; }

  /* Keep the error-detail popup above the line popup when opened from inside it */
  #linePop { z-index: 1110; }
  #errPop { z-index: 1120; }

  /* --- TTS panel --- */
  .ttsPanel {
    display:flex;
    gap:8px;
    align-items:center;
    flex-wrap: wrap;
    padding: 8px;
    border: 1px solid #eee;
    border-radius: 14px;
    background: rgba(255,255,255,0.94);
    box-shadow: 0 10px 22px rgba(0,0,0,0.06);
    backdrop-filter: blur(6px);
  }
  .ttsTranscript {
    margin-top: 8px;
    padding: 8px 10px;
    border: 1px solid #eee;
    border-radius: 14px;
    background:#fff;
    line-height: 1.9;
    direction: rtl;
    unicode-bidi: isolate;
    font-family: "Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif;
  }
  .ttsWord { padding: 1px 2px; border-radius: 6px; }
  .ttsWord.active { background: #fff2a8; outline: 2px solid rgba(0,0,0,0.15); }

  /* --- Compare popup (Nüsha 2) --- */
  .cmpOverlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.25);
    z-index: 1150;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 14px;
  }
  .cmpOverlay.open { display:flex; }
  .cmpPanel {
    width: min(980px, 98vw);
    max-height: min(720px, 92vh);
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 14px;
    box-shadow: 0 18px 55px rgba(0,0,0,0.22);
    overflow: auto;
    padding: 12px;
  }
  .cmpHeader { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom: 10px; }
  .cmpTitle { font-weight: 900; }
  .cmpBody { display:flex; flex-direction:column; gap:12px; }
  .cmpCard { border:1px solid #eee; background:#fafafa; border-radius: 12px; padding: 10px; }

  /* Floating error nav (keeps Next/Prev visible while scrolling) */
  .floatNav {
    position: fixed;
    left: 14px;
    top: 108px; /* a bit lower so it doesn't get lost at the very top */
    z-index: 1200;
    display:flex;
    flex-direction: column;
    gap:6px;            /* less whitespace */
    align-items:flex-start;
    padding: 6px 8px;   /* less whitespace */
    border: 1px solid #ddd;
    border-radius: 14px;
    background: rgba(255,255,255,0.94);
    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
    backdrop-filter: blur(6px);
  }
  .floatNav.dockRight { left: auto; right: 14px; }
  .floatNav.dockLeft { right: auto; left: 14px; }
  .floatNav {
    min-width: 320px;
    min-height: 54px;
    max-width: min(92vw, 980px);
    max-height: min(92vh, 620px);
    overflow: hidden; /* keep internal sections (AI list) scrollable */
  }
  .navHandle {
    width: 100%;
    cursor: grab;
    user-select: none;
    font-weight: 900;
    letter-spacing: 1px;
    color: #666;
    padding: 2px 6px 4px;
    border-radius: 10px;
    background: rgba(0,0,0,0.04);
  }
  .navHandle:active { cursor: grabbing; }
  .aiList {
    display: flex;
    flex-direction: column;
    gap: 4px;           /* tighter */
    width: 100%;
    flex: 1 1 auto;        /* scale with floatNav size */
    max-height: none;      /* no fixed cap; use available space */
    overflow: auto;        /* internal scroll when needed */
    padding-right: 2px;
  }
  /* AI buttons: no full-width boxes; fit content, minimal padding */
  .aiList .btn { text-align: left; width: fit-content; max-width: 100%; }
  .aiList .btn.secondary.small { padding: 4px 10px; border-radius: 12px; }
  .aiList .pill { margin-bottom: 2px; }
  /* Allow pills to wrap when space is tight */
  .pill { white-space: normal; }
  .navTopRow { width: 100%; flex-wrap: wrap; }
  .navTopRow .errpill {
    flex: 0 0 auto;            /* don't stretch full row */
    padding: 4px 8px;          /* tighter */
    line-height: 1.2;          /* tighter */
    white-space: nowrap;       /* keep it on one line; wrap happens by moving to next row */
    max-width: 100%;
  }
  .flexBreak { flex: 0 0 100%; height: 0; display: none; }
  .navTopRow.stack .flexBreak { display: block; }
  .searchBar {
    position: static; /* sits at top, but scrolls away (user can scroll up to use) */
    z-index: 900;
    background: rgba(255,255,255,0.98);
    border: 1px solid #eee;
    border-radius: 12px;
    padding: 8px;
    margin-bottom: 8px;
    box-shadow: 0 10px 22px rgba(0,0,0,0.06);
    backdrop-filter: blur(6px);
  }
  .searchRow { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .searchInput {
    flex: 1 1 220px;
    min-width: 180px;
    padding: 8px 10px;
    border: 1px solid #ddd;
    border-radius: 12px;
    font-size: 1em; /* keep text size */
    outline: none;
  }
  .searchMeta { font-size: 0.88em; color:#666; }
  .navResize {
    position: absolute;
    right: 6px;
    bottom: 6px;
    width: 14px;
    height: 14px;
    cursor: nwse-resize;
    user-select: none;
    opacity: 0.65;
  }
  .navResize::after {
    content: "";
    position: absolute;
    inset: 0;
    border-right: 2px solid rgba(0,0,0,0.35);
    border-bottom: 2px solid rgba(0,0,0,0.35);
    border-radius: 2px;
  }
  .leftPane { padding-top: 18px; } /* normal padding; nav logic scrolls below floatNav */
</style>
</head>
<body class="hideList">
<button class="btn secondary small" id="btnShowHeader" onclick="toggleHeader()" title="Üst menüyü aç/kapat (ArrowUp)">▲ Menü</button>
<header>
  <div style="font-weight:700;">Satir - Tahkik Hizalama</div>
  <div class="muted">Soldan satir sec • Görselin altinda dizgi + OCR • Imla hatalari vurgulanir</div>

  <div class="row" style="align-items:center;">
    <button class="btn secondary small" id="btnToggleHeader" onclick="toggleHeader()" title="Üst menüyü gizle/göster (ArrowUp)">▲</button>
    <button class="btn secondary small" onclick="decFont()">A-</button>
    <button class="btn secondary small" onclick="incFont()">A+</button>
    <span class="pill">Punto: <span id="fsLabel"></span></span>
    <button class="btn secondary small" onclick="showAiErrorReport()">AI Hata Raporu</button>
  </div>

  <div class="row" style="align-items:center;">
    <div class="ttsPanel">
      <span class="pill">TTS (sayfa)</span>
      <button class="btn secondary small" id="btnBatch" onclick="batchVocalize()" title="Tüm dokümanı sırayla seslendir ve kaydet">Toplu Hazırla</button>

      <button class="btn secondary small" id="btnTtsToggle" onclick="ttsToggle()" disabled>▶︎ Oku</button>
      <span class="pill">Hız: <span id="ttsRateLabel">0.60</span></span>
      <input id="ttsRate" type="range" min="0.50" max="1.15" step="0.01" value="0.60" oninput="ttsSetRate(this.value)" />
      <span class="pill muted" id="ttsStatus">Hazır</span>
    </div>
  </div>

  <div class="ttsTranscript" id="ttsTranscript" style="display:none;"></div>

  <div class="row" style="align-items:center;">
    <span class="pill muted" id="scRunLabel" style="display:none;"></span>
    <span class="pill muted" id="scSourceLabel" style="display:none;"></span>
    <span class="pill muted" id="nushaLabel"></span>
    <button class="btn secondary small" id="btnN1" onclick="setNusha(1)">Nüsha 1</button>
    <button class="btn secondary small" id="btnN2" onclick="setNusha(2)">Nüsha 2</button>
    <button class="btn secondary small" id="btnN3" onclick="setNusha(3)">Nüsha 3</button>
    <button class="btn secondary small" id="btnN4" onclick="setNusha(4)">Nüsha 4</button>
  </div>




  
  <div class="row" id="skipNavContainer" style="display:none;align-items:center;margin-left:auto;padding-left:12px;border-left:1px solid #ddd;">
     <span class="pill errpill" style="font-weight:bold;">Satır Atlaması!</span>
     <button class="btn secondary small" onclick="prevSkip()">←</button>
     <span class="pill" id="skipCountLabel">0/0</span>
     <button class="btn secondary small" onclick="nextSkip()">→</button>
     <button class="btn secondary small" onclick="closeSkipNav()">X</button>
  </div>
  <!-- Olası Satır Atlaması button removed per user request -->

</header>

<div class="floatNav" id="floatNav">
  <div class="navHandle" id="floatNavHandle" title="Sürükle: hata kutusunu taşı">⋮⋮</div>
  <div class="row navTopRow" style="gap:8px;align-items:center;">
    <button class="btn secondary small" onclick="prevError()">← Hata</button>
    <button class="btn secondary small" onclick="nextError()">Hata →</button>
    <span class="flexBreak" id="navBreak"></span>
    <span class="pill errpill">Hata satiri: <span id="errCount"></span></span>
    <span class="pill muted" id="navInfo" style="display:none;"></span>
  </div>
  <div class="pill" style="width: fit-content;">AI Hata Navigasyon</div>
  <div class="aiList" aria-label="AI hata butonları (kaydırılabilir)">
    <button class="btn secondary small" onclick="gotoErrBySource('gemini')">Gemini</button>
    <button class="btn secondary small" onclick="gotoErrBySource('openai')">GPT</button>
    <button class="btn secondary small" onclick="gotoErrBySource('claude')">Claude</button>
    <button class="btn secondary small" onclick="gotoGptGemCommon()">GPT+Gemini ortak</button>
    <button class="btn secondary small" onclick="gotoGptClaudeCommon()">GPT+Claude ortak</button>
    <button class="btn secondary small" onclick="gotoAllThreeCommon()">3'ü ortak</button>
  </div>
  <div class="navResize" id="floatNavResize" title="Boyutlandır (köşeden sürükle)"></div>
</div>

<div class="wrap">
  <div class="leftPane" id="pagePane"></div>
  <div class="splitter" id="splitter" title="Sürükle: el yazması / dizgi genişliği"></div>
  <div class="rightPane" id="listPane"></div>
</div>

<!-- Right-pane quick hide/show -->
<button class="listToggleTab" id="btnShowListTab" onclick="toggleListPane()" title="Dizgiyi göster">← Dizgi</button>

<!-- Click-to-explain popup -->
<div class="popOverlay" id="errPop" onclick="closeErrPop(event)">
  <div class="popPanel" onclick="event.stopPropagation()">
    <div class="popHeader">
      <div class="popTitle">İmla Hatası Detayı</div>
      <button class="btn small" onclick="closeErrPop()">Kapat</button>
    </div>
    <div class="popBody" id="errPopBody"></div>
  </div>
</div>

<!-- Line popup (double-click on page line) -->
<div class="popOverlay" id="linePop" onclick="closeLinePop(event)">
  <div class="popPanel" onclick="event.stopPropagation()">
    <div class="popHeader">
      <div class="popTitle" id="linePopTitle">Dizgi Satırı</div>
      <button class="btn small" onclick="closeLinePop()">Kapat</button>
    </div>
    <div class="popBody" id="linePopBody"></div>
  </div>
</div>

<!-- Compare popup (other nusha(s)) -->
<div class="cmpOverlay" id="cmpPop" onclick="closeCmpPop(event)">
  <div class="cmpPanel" onclick="event.stopPropagation()">
    <div class="cmpHeader">
      <div class="cmpTitle" id="cmpTitle">Karşılaştırma</div>
      <div class="row" style="gap:8px;align-items:center;">
        <button class="btn secondary small" id="btnCmpN1" onclick="switchCmp(1)" style="display:none;">Nüsha 1</button>
        <button class="btn secondary small" id="btnCmpN2" onclick="switchCmp(2)" style="display:none;">Nüsha 2</button>
        <button class="btn secondary small" id="btnCmpN3" onclick="switchCmp(3)" style="display:none;">Nüsha 3</button>
        <button class="btn secondary small" id="btnCmpN4" onclick="switchCmp(4)" style="display:none;">Nüsha 4</button>
      <button class="btn small" onclick="closeCmpPop()">Kapat</button>
      </div>
    </div>
    <div class="cmpBody" id="cmpPopBody"></div>
  </div>
</div>

<!-- AI Hata Raporu popup -->
<div class="popOverlay" id="aiReportPop" onclick="closeAiReportPop(event)">
  <div class="popPanel" style="width: min(900px, 96vw); max-height: min(80vh, 90vh);" onclick="event.stopPropagation()">
    <div class="popHeader">
      <div class="popTitle">AI Hata Raporu (Model Bazlı)</div>
      <button class="btn small" onclick="closeAiReportPop()">Kapat</button>
    </div>
    <div class="popBody" id="aiReportPopBody" style="max-height: calc(80vh - 80px); overflow-y: auto;"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON_PLACEHOLDER__;
// Primary (Nüsha 1) mapping (may include localStorage overrides)
let mapping = DATA.aligned_view || DATA.aligned || [];
// Nüsha 2 mapping
const altMapping = DATA.aligned_alt || [];
// Nüsha 3 mapping
// Nüsha 3 mapping
const alt3Mapping = DATA.aligned_alt3 || [];
// Nüsha 4 mapping
const alt4Mapping = DATA.aligned_alt4 || [];
const spellPP = DATA.spellcheck_per_paragraph || [];
const scRuns = DATA.spellcheck_runs || [];
const scArchives = DATA.spellcheck_archives || [];

// Detect archive path from current viewer.html location if not in DATA.
// IMPORTANT: Avoid backslash-heavy regex which can break JS when embedded; normalize first.
let archivePath = DATA.archive_path || null;
if (!archivePath) {
  try {
    const viewerPathRaw = window.location.pathname || window.location.href || "";
    const viewerPath = String(viewerPathRaw).replaceAll("\\\\", "/");
    const match = viewerPath.match(/doc_archives\/([^\/]+)/);
    if (match) {
        archivePath = decodeURIComponent(match[1]);
    }
  } catch(e) { alert("Error extracting archive: " + e); }
}

let ACTIVE_SOURCE = { kind: "current", label: "Güncel sonuç" };

// Nüsha toggle: 1=nüsha1 (primary), 2=nüsha2, 3=nüsha3 (if available)
const HAS_N2 = !!(DATA.has_alt && Array.isArray(altMapping) && altMapping.length);
const HAS_N3 = !!(DATA.has_alt3 && Array.isArray(alt3Mapping) && alt3Mapping.length);
const HAS_N4 = !!(DATA.has_alt4 && Array.isArray(alt4Mapping) && alt4Mapping.length);
let ACTIVE_NUSHA = (DATA.default_nusha === 4 && HAS_N4) ? 4 : ((DATA.default_nusha === 3 && HAS_N3) ? 3 : ((DATA.default_nusha === 2 && HAS_N2) ? 2 : 1));
const MAPPING_KIND = (DATA.mapping_kind === "alt4") ? "alt4" : ((DATA.mapping_kind === "alt3") ? "alt3" : ((DATA.mapping_kind === "alt") ? "alt" : "primary"));
const VIEW_MODE = (DATA.view_mode === "dual") ? "dual" : "single";

// Audio Caches for all Nushas
const ALL_AUDIO_CACHES = {
  1: DATA.cached_audio || {},
  2: DATA.cached_audio_n2 || {},
  3: DATA.cached_audio_n3 || {},
  4: DATA.cached_audio_n4 || {}
};
let cachedAudio = ALL_AUDIO_CACHES[ACTIVE_NUSHA] || {};

// Keep references so we can swap the main viewer between N1 / N2 / N3 / N4
let mappingPrimary = (DATA.aligned || []);
const mappingAlt = altMapping;
const mappingAlt3 = alt3Mapping;
const mappingAlt4 = alt4Mapping;
let ACTIVE_PP_FOR_MARKS = (spellPP || []); // current spellcheck source used for highlights

function _safeStorageKey(s) {
  return String(s || "")
    .replaceAll("\\\\", "/")
    .replace(/[^a-zA-Z0-9_:\\-\\/\\.]+/g, "_")
    .slice(0, 160);
}

const keyMapLegacy = "tahkik_alignment_override_v3";
const DOC_KEY = _safeStorageKey(
  (archivePath ? ("arch:" + archivePath) : "") ||
  (DATA.docx_path ? ("docx:" + String(DATA.docx_path)) : "") ||
  ""
);
const keyMap = keyMapLegacy + "__" + (DOC_KEY || "unknown");
const keyFS  = "viewer_font_size_v1";
const keyPageZoom = "viewer_page_zoom_v1";
const keySplit = "viewer_split_ratio_v1";
const keyHideList = "viewer_hide_list_v1";
const keyActivePage = "viewer_active_page_v1";
const keyActiveLine = "viewer_active_line_v1";
const keyActiveNusha = "viewer_active_nusha_v1";
const keyArchive = "imla_saved_reports_v1";
let fontSize = 23;
let PAGE_ZOOM = 1.32; // 1.0 = 100%
let SPLIT = 0.52;    // left pane ratio (0..1)
let HIDE_LIST = true;

// Keep manuscript bbox + dizgi selected line aligned to the same vertical anchor while following playback/selection.
const SYNC_SCROLL_ANCHOR_RATIO = 0.18; // ~top 18% of pane height
const SYNC_SCROLL_ANCHOR_MIN_PX = 40;

// --- TTS (Google Cloud via local proxy) ---
const TTS_URL = "http://127.0.0.1:8765/tts";
const tahkikTokens = Array.isArray(DATA.tahkik_tokens) ? DATA.tahkik_tokens : [];
// TTS can work in two modes:
// - "tahkik": use global tahkik_tokens (best for accurate global indices)
// - "page": fallback for old archives with no tahkik_tokens: tokenize current page's best.raw lines
let ttsTokens = tahkikTokens;
let TTS_TOKEN_MODE = (tahkikTokens && tahkikTokens.length) ? "tahkik" : "none";
let TTS_RATE = 0.60;
let ttsAudio = null;
let ttsTimer = null;
let ttsTimepoints = []; // [{idx,time}]
let ttsActiveIdx = -1;  // token idx within page slice
let ttsPageStart = 0;
let ttsPageEnd = 0;
let ttsPageRanges = []; // [{line_no,start,end}] sorted by start
let ttsLastLine = null;
let ttsChunks = []; // [{audio:Audio, timepoints:[{idx,time}]}]
let ttsChunkIdx = 0;
let ttsChunkTpPos = 0;

function _ttsSetStatus(msg) {
  const el = document.getElementById("ttsStatus");
  if (el) el.textContent = String(msg || "");
}

function ttsSetRate(v) {
  const n = parseFloat(String(v || "1"));
  TTS_RATE = isFinite(n) ? Math.max(0.50, Math.min(1.25, n)) : 1.0;
  const lab = document.getElementById("ttsRateLabel");
  if (lab) lab.textContent = TTS_RATE.toFixed(2);
}

function _ttsBtnState(ready, playing) {
  const bToggle = document.getElementById("btnTtsToggle");
  if (bToggle) {
    if (ready) bToggle.removeAttribute("disabled");
    else bToggle.setAttribute("disabled", "true");
    
    if (playing) {
      bToggle.textContent = "⏸ Duraklat";
      bToggle.onclick = ttsPause;
    } else {
      bToggle.textContent = "▶︎ Oku";
      bToggle.onclick = ttsToggle;
    }
  }
}

function _escapeXml(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function _ttsComputePageBounds(pageObj) {
  const lines = (pageObj && pageObj.lines) ? pageObj.lines : [];
  let s = null, e = null;
  const ranges = [];
  for (const it of lines) {
    const b = (it && typeof it === "object") ? (it.best || {}) : {};
    const st = b && typeof b.start_word === "number" ? b.start_word : null;
    const en = b && typeof b.end_word === "number" ? b.end_word : null;
    const ln = it && typeof it.line_no === "number" ? it.line_no : null;
    if (st == null || en == null || ln == null) continue;
    if (en <= st) continue;
    s = (s == null) ? st : Math.min(s, st);
    e = (e == null) ? en : Math.max(e, en);
    ranges.push({ line_no: ln, start: st, end: en });
  }
  ranges.sort((a,b) => a.start - b.start);
  return { start: (s == null ? 0 : s), end: (e == null ? 0 : e), ranges };
}

function _ttsComputePageBoundsFromRaw(pageObj) {
  // Fallback when tahkik_tokens are missing: tokenize each line's best.raw and build per-line ranges.
  const lines = (pageObj && pageObj.lines) ? pageObj.lines : [];
  const tokens = [];
  const ranges = [];
  for (const it of lines) {
    if (!it || typeof it !== "object") continue;
    const ln = (typeof it.line_no === "number") ? it.line_no : null;
    const best = it.best || {};
    const raw = String(best.raw || "").trim();
    if (ln == null || !raw) continue;
    const parts = raw.split(/\s+/).map(x => String(x || "").trim()).filter(Boolean);
    if (!parts.length) continue;
    const start = tokens.length;
    for (const p of parts) tokens.push(p);
    const end = tokens.length;
    if (end > start) ranges.push({ line_no: ln, start, end });
  }
  return { tokens, start: 0, end: tokens.length, ranges };
}

let TTS_PENDING_SEEK_LINE = null;
let TTS_PENDING_AUTO_PLAY = null;

function _ttsIsPlaying() {
    const cur = _ttsCurrentAudio();
    return !!(cur && !cur.paused);
}

function _ttsLineForGidx(gidx) {
  // binary search on starts
  const arr = ttsPageRanges || [];
  let lo = 0, hi = arr.length - 1, best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid].start <= gidx) { best = mid; lo = mid + 1; }
    else hi = mid - 1;
  }
  if (best < 0) return null;
  const r = arr[best];
  return (gidx >= r.start && gidx < r.end) ? r.line_no : null;
}

function _ttsRenderTranscript(activeIdx) {
  const el = document.getElementById("ttsTranscript");
  if (!el) return;
  const total = Math.max(0, ttsPageEnd - ttsPageStart);
  if (!total) { el.style.display = "none"; el.innerHTML = ""; return; }
  el.style.display = "block";

  const before = 18, after = 18;
  const a = Math.max(0, Math.min(total - 1, activeIdx));
  const from = Math.max(0, a - before);
  const to = Math.min(total, a + after + 1);
  const parts = [];
  if (from > 0) parts.push(`<span class="small muted">… </span>`);
  for (let i = from; i < to; i++) {
    const src = (ttsTokens && ttsTokens.length) ? ttsTokens : tahkikTokens;
    const tok = _escapeXml((src && src.length) ? (src[ttsPageStart + i] || "") : "");
    const cls = (i === a) ? "ttsWord active" : "ttsWord";
    parts.push(`<span class="${cls}">${tok}</span>`);
    parts.push(" ");
  }
  if (to < total) parts.push(`<span class="small muted"> …</span>`);
  el.innerHTML = parts.join("");
}

function _ttsClearTimer() {
  if (ttsTimer) {
    try { clearInterval(ttsTimer); } catch(e) {}
    ttsTimer = null;
  }
}

function _ttsCurrentAudio() {
  try {
    if (ttsChunks && ttsChunks.length) return (ttsChunks[ttsChunkIdx] && ttsChunks[ttsChunkIdx].audio) ? ttsChunks[ttsChunkIdx].audio : null;
    return ttsAudio || null;
  } catch(e) {
    return null;
  }
}

function _ttsSeekToGidx(gidx, lineNoForLastLine) {
  try {
    if (!isFinite(gidx) || gidx < 0) return;
    const curAudio = _ttsCurrentAudio();
    const wasPlaying = !!(curAudio && curAudio.paused === false);

    // Chunked mode
    if (ttsChunks && ttsChunks.length) {
      let targetChunk = 0;
      for (let i = 0; i < ttsChunks.length; i++) {
        const arr = (ttsChunks[i] && ttsChunks[i].timepoints) ? ttsChunks[i].timepoints : [];
        if (!arr.length) continue;
        const first = arr[0].idx;
        const last = arr[arr.length - 1].idx;
        if (gidx >= first && gidx <= last) { targetChunk = i; break; }
        if (gidx > last) targetChunk = i; // keep last <= gidx as best
      }

      // Pause current chunk and move to target
      try { if (ttsChunks[ttsChunkIdx] && ttsChunks[ttsChunkIdx].audio) ttsChunks[ttsChunkIdx].audio.pause(); } catch(e) {}
      ttsChunkIdx = Math.max(0, Math.min(ttsChunks.length - 1, targetChunk));
      const ch = ttsChunks[ttsChunkIdx];
      if (!ch || !ch.audio) return;
      const arr = ch.timepoints || [];
      if (!arr.length) return;

      // Find nearest timepoint for gidx (first >= gidx, else last)
      let pos = 0;
      for (let i = 0; i < arr.length; i++) {
        pos = i;
        if (arr[i].idx >= gidx) break;
      }
      ttsChunkTpPos = pos;
      const tp = arr[pos];
      const targetTime = tp && isFinite(tp.time) ? tp.time : 0;

      // Update UI state to avoid immediate re-select loops.
      if (tp && isFinite(tp.idx)) {
        ttsActiveIdx = tp.idx;
        _ttsRenderTranscript(ttsActiveIdx - ttsPageStart);
      }
      if (typeof lineNoForLastLine === "number") ttsLastLine = lineNoForLastLine;

      try { ch.audio.currentTime = Math.max(0, targetTime); } catch(e) {}
      if (wasPlaying) {
        try { ch.audio.play(); _ttsSetStatus("Okunuyor…"); _ttsBtnState(true, true); } catch(e) {}
      }
      return;
    }

    // Single audio mode
    if (ttsAudio && ttsTimepoints && ttsTimepoints.length) {
      let pos = 0;
      for (let i = 0; i < ttsTimepoints.length; i++) {
        pos = i;
        if (ttsTimepoints[i].idx >= gidx) break;
      }
      const tp = ttsTimepoints[pos];
      const targetTime = tp && isFinite(tp.time) ? tp.time : 0;
      
      // This block was added by the user
      // ACTIVE_LINE_NO = (lastLine != null) ? parseInt(lastLine, 10) : null; // This line seems out of place here, assuming it was a typo in the instruction and should not be inserted.
  
      if (gidx != null && isFinite(gidx)) {
        // try to restore tts state? hard without audio
        // But if we have archivePath, enable button to hint it might be available
        if (archivePath) {
             _ttsBtnState(true, false);
        }
      }
      // End of user-added block

      if (tp && isFinite(tp.idx)) {
        ttsActiveIdx = tp.idx;
        _ttsRenderTranscript(ttsActiveIdx - ttsPageStart);
      }
      if (typeof lineNoForLastLine === "number") ttsLastLine = lineNoForLastLine;
      try { ttsAudio.currentTime = Math.max(0, targetTime); } catch(e) {}
      if (wasPlaying) {
        try { ttsAudio.play(); _ttsSetStatus("Okunuyor…"); _ttsBtnState(true, true); } catch(e) {}
      }
    }
  } catch(e) {}
}

function _ttsFollowSelectedLine(lineNo, wasPlaying) {
  try {
    if (typeof lineNo !== "number") return;
    // Update: If content is missing (new page), queue seek and trigger load
    const hasContent = (ttsChunks && ttsChunks.length) || (ttsAudio && ttsAudio.src);
    if (!hasContent) {
        TTS_PENDING_SEEK_LINE = lineNo;
        // Force auto-play on cross-page jump (as requested by user "direk okumaya başlasın")
        TTS_PENDING_AUTO_PLAY = true; 
        ttsToggle(); 
        return;
    }
    const arr = ttsPageRanges || [];
    if (!arr.length) return;
    const r = arr.find(x => x && x.line_no === lineNo);
    if (!r || !isFinite(r.start)) return;
    _ttsSeekToGidx(r.start, lineNo);
  } catch(e) {}
}

function ttsStop() {
  _ttsClearTimer();
  try {
    if (ttsAudio) {
      ttsAudio.pause();
      ttsAudio.removeAttribute("src"); // Setting "" causes error on some browsers
    }
  } catch(e) {}
  try {
    for (const ch of (ttsChunks || [])) {
      try { if (ch && ch.audio) { ch.audio.pause(); ch.audio.src = ""; } } catch(_e) {}
    }
  } catch(e) {}
  ttsChunks = [];
  ttsChunkIdx = 0;
  ttsChunkTpPos = 0;
  ttsTimepoints = [];
  ttsActiveIdx = -1;
  ttsLastLine = null;
  _ttsRenderTranscript(0);
  _ttsBtnState(false, false);
  _ttsSetStatus("Hazır");
}

function ttsPause() {
  try {
    const cur = (ttsChunks && ttsChunks.length) ? (ttsChunks[ttsChunkIdx] && ttsChunks[ttsChunkIdx].audio) : ttsAudio;
    if (cur) cur.pause();
    _ttsSetStatus("Duraklatıldı");
    _ttsBtnState(true, false);
  } catch(e) {}
}

async function ttsToggle() {
  const isEmpty = (!ttsChunks || !ttsChunks.length) && !ttsAudio;
  if (isEmpty) {
      // If cached (in memory) OR we are in an archive (lazy check on server), try preparing first.
      if ((cachedAudio && cachedAudio[ACTIVE_PAGE_KEY]) || archivePath) {
          try {
              _ttsSetStatus("Arşivden yükleniyor...");
              await ttsPrepare();
              
              if (TTS_PENDING_SEEK_LINE !== null) {
                  const ln = TTS_PENDING_SEEK_LINE;
                  TTS_PENDING_SEEK_LINE = null;
                  const arr = ttsPageRanges || [];
                  const r = arr.find(x => x && x.line_no === ln);
                  if (r && isFinite(r.start)) {
                       // _ttsSeekToGidx sets ttsActiveIdx and currentTime
                       _ttsSeekToGidx(r.start, ln);
                  }
              }
              
              if (TTS_PENDING_AUTO_PLAY !== null) {
                   const shouldPlay = TTS_PENDING_AUTO_PLAY;
                   TTS_PENDING_AUTO_PLAY = null;
                   if (!shouldPlay) {
                       _ttsSetStatus("Hazır");
                       _ttsBtnState(true, false);
                       return; // Exit without playing
                   }
              }
          } catch(e) {
              alert("Hazırlama hatası: " + e.message);
              _ttsSetStatus("Hata");
              return;
          }
      }
  }

  // If we still have no content, we can't play.
  // But wait, if ttsPrepare succeeded, isEmpty is now false (logic check).
  // Let's re-evaluate current state.
  const hasContent = (ttsChunks && ttsChunks.length) || ttsAudio;
  
  if (!hasContent) {
      // If we clicked play but couldn't get content
      console.warn("ttsToggle: No content");
      return;
  }

  // Identify current audio
  try {
    const cur = (ttsChunks && ttsChunks.length) ? (ttsChunks[ttsChunkIdx] && ttsChunks[ttsChunkIdx].audio) : ttsAudio;
    if (cur) {
        // Enforce start from selected line if available
        if (typeof ACTIVE_LINE_NO === "number") {
             const arr = ttsPageRanges || [];
             const r = arr.find(x => x && x.line_no === ACTIVE_LINE_NO);
             if (r && isFinite(r.start)) {
                 _ttsSeekToGidx(r.start, ACTIVE_LINE_NO);
             }
        }
    
        cur.play().then(() => {
            _ttsSetStatus("Okunuyor…");
            _ttsBtnState(true, true);
        }).catch(e => {
            // Ignore AbortError (common when specific play() calls are interrupted by new loads)
            if (e.name === "AbortError" || e.message.includes("aborted")) {
                console.warn("Play aborted (harmless)", e);
                return;
            }
            console.error(e);
            _ttsSetStatus("Hata: " + e.message);
            alert("Ses çalınamadı: " + e.message);
        });
    }
    
    // Resume timer if needed
    if (ttsChunks && ttsChunks.length && !ttsTimer) {
         ttsTimer = setInterval(() => {
            try {
              if (!ttsChunks.length) return;
              const ch = ttsChunks[ttsChunkIdx];
              if (!ch || !ch.audio) return;
              const t = ch.audio.currentTime || 0;
              const arr = ch.timepoints || [];
              while (ttsChunkTpPos + 1 < arr.length && arr[ttsChunkTpPos + 1].time <= t) {
                ttsChunkTpPos += 1;
              }
              if (!arr.length) return;
              const cur = arr[ttsChunkTpPos];
              if (!cur) return;
              if (cur.idx !== ttsActiveIdx) {
                ttsActiveIdx = cur.idx; // absolute gidx
                const rel = ttsActiveIdx - ttsPageStart;
                _ttsRenderTranscript(rel);
                const ln = _ttsLineForGidx(ttsActiveIdx);
                if (ln != null && ln !== ttsLastLine) {
                  ttsLastLine = ln;
                  selectLine(ln, { fromTts: true });
                }
              }
            } catch(e) {}
          }, 60);
    }
  } catch(e) {}
}

async function ttsPrepare() {
  const pageObj = _pageByKey(ACTIVE_PAGE_KEY);
  if (!pageObj) return;

  // Cache Check
  if (cachedAudio && cachedAudio[ACTIVE_PAGE_KEY]) {
      console.log("Using cached audio for", ACTIVE_PAGE_KEY);
      _ttsSetStatus("Önbellekten yükleniyor...");
      
      const chunksData = cachedAudio[ACTIVE_PAGE_KEY]; // list of {audio_path, timepoints}
      // Reconstruct ttsChunks structure similar to server response
      // But here we have paths, not base64.
      // So we set audio.src to the relative path.
      
      ttsStop();
      ttsChunks = chunksData.map(c => {
          const audio = new Audio();
          // Ensure path is encoded for browser (spaces, special chars)
          // Also explicitly ignore query params if any
          const cleanPath = (c.audio_path || "").split("?")[0];
          audio.src = encodeURI(cleanPath); 
          audio.preload = "auto";
          audio.onerror = (e) => {
              // Ignore errors if src is empty or refers to self (viewer.html) or just "file:"
              if (!audio.src || audio.src.indexOf("viewer.html") !== -1 || audio.src === window.location.href) return;
              console.error("Audio Load Error:", audio.src, e);
              alert("Ses yüklenemedi:\\n" + audio.src + "\\nHata kodu: " + (e.target.error ? e.target.error.code : "Unknown"));
          };
          audio.onplay = () => _ttsBtnState(true, true);
          audio.onpause = () => _ttsBtnState(true, false);
          
          // Re-hydrate timepoints
          const tps = (c.timepoints || []).map(tp => {
             // Server saves {mark: "w123", time: 1.23}
             const mk = String(tp.mark || "");
             const idx = parseInt(mk.replace(/^w/, ""), 10);
             const tm = parseFloat(String(tp.time || "0"));
             return { idx, time: (isFinite(tm) ? tm : 0) };
          }).filter(x => isFinite(x.idx) && x.idx >= 0).sort((a,b)=>a.time-b.time);
          
          return { audio, timepoints: tps };
      });
      
      // Setup chain
      ttsChunkIdx = 0;
      ttsChunkTpPos = 0;
      for (let i=0;i<ttsChunks.length;i++) {
        const a = ttsChunks[i].audio;
        a.onended = () => {
          if (i !== ttsChunkIdx) return;
          ttsChunkIdx += 1;
          ttsChunkTpPos = 0;
          if (ttsChunkIdx >= ttsChunks.length) { 
             _ttsBtnState(true, false); 
             _ttsSetStatus("Tamamlandı");
             _ttsClearTimer();
             return; 
          }
          try { 
              ttsChunks[ttsChunkIdx].audio.play(); 
              _ttsSetStatus("Okunuyor…"); 
          } catch(_e) {}
        };
      }
      
      // Setup page bounds for highlighting
      // We need to know token ranges. 
      // Fallback: we assume cached audio corresponds to current Tokens.
      // If we are in "tahkik" mode, we use tahkikTokens.
      if (tahkikTokens && tahkikTokens.length) {
        TTS_TOKEN_MODE = "tahkik";
        ttsTokens = tahkikTokens;
        const b = _ttsComputePageBounds(pageObj);
        ttsPageStart = b.start;
        ttsPageEnd = b.end;
        ttsPageRanges = b.ranges;
      } else {
        TTS_TOKEN_MODE = "page";
        const fb = _ttsComputePageBoundsFromRaw(pageObj);
        ttsTokens = fb.tokens || [];
        const b = { start: fb.start, end: fb.end, ranges: fb.ranges };
        ttsPageStart = b.start;
        ttsPageEnd = b.end;
        ttsPageRanges = b.ranges;
      }

      _ttsSetStatus("Hazır (Arşiv)");
      _ttsBtnState(true, false);
      return;
  }

  // stop any previous playback
  ttsStop();
  // But we want to indicate "Preparing"
  _ttsSetStatus("Hazırlanıyor…");
  
  // Token source: prefer tahkik_tokens; fallback to per-page tokenization from best.raw for old archives.
  let b = null;
  if (tahkikTokens && tahkikTokens.length) {
    TTS_TOKEN_MODE = "tahkik";
    ttsTokens = tahkikTokens;
    b = _ttsComputePageBounds(pageObj);
  } else {
    TTS_TOKEN_MODE = "page";
    const fb = _ttsComputePageBoundsFromRaw(pageObj);
    ttsTokens = fb.tokens || [];
    b = { start: fb.start, end: fb.end, ranges: fb.ranges };
  }

  ttsPageStart = b.start;
  ttsPageEnd = b.end;
  ttsPageRanges = b.ranges;
  const total = ttsPageEnd - ttsPageStart;
  if (total <= 0) {
    alert(TTS_TOKEN_MODE === "page"
      ? "TTS: Bu sayfada seslendirecek dizgi metni bulunamadı."
      : "Bu sayfa için hizalanmış dizgi aralığı bulunamadı."
    );
    ttsStop();
    return;
  }

  const toks = (ttsTokens && ttsTokens.length ? ttsTokens : tahkikTokens).slice(ttsPageStart, ttsPageEnd);
  const maxTok = 2400; // avoid huge requests; enough for a page
  const toks2 = toks.slice(0, maxTok);
  ttsPageEnd = ttsPageStart + toks2.length;

    if (window.ttsAbortController) { try{window.ttsAbortController.abort();}catch(e){} }
    window.ttsAbortController = new AbortController();
    const controller = window.ttsAbortController;
    const timeoutId = setTimeout(() => controller.abort(), 1800000);
    
    
    // Check server for existing audio (Lazy Lookup)
    try {
      const resp = await fetch(TTS_URL, {
        signal: controller.signal,
        method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tokens: toks2,
        token_start: ttsPageStart,
        chunk_size: 450,
        page_key: ACTIVE_PAGE_KEY,
        nusha_id: ACTIVE_NUSHA || 1,
        action: "check_only",
        archive_path: (function(){
            if (archivePath) return archivePath;
            try {
                const m = (window.location.href||"").match(/doc_archives\/([^\/]+)/);
                if (m) return decodeURIComponent(m[1]);
            } catch(e){}
            return null;
        })()
      })
    });
    const obj = await resp.json();
    if (!resp.ok) {
        const errMsg = obj && obj.error ? obj.error : ("HTTP " + resp.status);
        throw new Error(errMsg + `\n(Key: ${ACTIVE_PAGE_KEY}, Nusha: ${ACTIVE_NUSHA}, Arch: ${
            (function(){ try{ return (window.location.href||"").match(/doc_archives\/([^\/]+)/)[1]; }catch(en){return "err";} })()
        })`);
    }
        clearTimeout(timeoutId);

    // Chunked mode
    const chs = Array.isArray(obj.chunks) ? obj.chunks : null;
    if (chs && chs.length) {
      ttsChunks = chs.map((c) => {
        const audioB64 = c.audio_b64 || "";
        const tps = Array.isArray(c.timepoints) ? c.timepoints : [];
        const timepoints = tps.map((tp) => {
          const mk = String(tp.mark || "");
          const idx = parseInt(mk.replace(/^w/, ""), 10); // absolute gidx
          const tm = parseFloat(String(tp.time || "0"));
          return { idx, time: (isFinite(tm) ? tm : 0) };
        }).filter(x => isFinite(x.idx) && x.idx >= 0).sort((a,b)=>a.time-b.time);
        const audio = new Audio();
        audio.src = "data:audio/mp3;base64," + audioB64;
        audio.preload = "auto";
        audio.onplay = () => _ttsBtnState(true, true);
        audio.onpause = () => _ttsBtnState(true, false);
        return { audio, timepoints };
      });

      ttsChunkIdx = 0;
      ttsChunkTpPos = 0;
      for (let i=0;i<ttsChunks.length;i++) {
        const a = ttsChunks[i].audio;
        a.onended = () => {
          if (i !== ttsChunkIdx) return;
          ttsChunkIdx += 1;
          ttsChunkTpPos = 0;
          if (ttsChunkIdx >= ttsChunks.length) { 
             // Finished all chunks
             _ttsBtnState(true, false); 
             _ttsSetStatus("Tamamlandı");
             _ttsClearTimer();
             return; 
          }
          // Play next chunk
          try { 
              ttsChunks[ttsChunkIdx].audio.play(); 
              _ttsSetStatus("Okunuyor…"); 
          } catch(_e) {}
        };
      }

      // DO NOT play immediately. Just Ready.
      _ttsSetStatus("Hazır");
      _ttsBtnState(true, false);
      return;
    }

    // Backward compat (single audio)
    const audioB64 = obj.audio_b64 || "";
    const tps = Array.isArray(obj.timepoints) ? obj.timepoints : [];
    ttsTimepoints = tps.map((tp) => {
      const mk = String(tp.mark || "");
      const idx = parseInt(mk.replace(/^w/, ""), 10);
      const tm = parseFloat(String(tp.time || "0"));
      return { idx, time: (isFinite(tm) ? tm : 0) };
    }).filter(x => isFinite(x.idx) && x.idx >= 0).sort((a,b)=>a.time-b.time);

    ttsAudio = new Audio();
    ttsAudio.src = "data:audio/mp3;base64," + audioB64;
    ttsAudio.preload = "auto";
    ttsAudio.onplay = () => _ttsBtnState(true, true);
    ttsAudio.onpause = () => _ttsBtnState(true, false);
    ttsAudio.onended = () => {
        _ttsBtnState(true, false);
        _ttsSetStatus("Tamamlandı");
    };
    
    // DO NOT play immediately
    _ttsSetStatus("Hazır");
    _ttsBtnState(true, false);

  } catch(e) {
    if (e.name === 'AbortError') return;
    alert("TTS çalışmadı: " + (e && e.message ? e.message : e));
    ttsStop();
  }
}

// Global batch lock
let BATCH_ABORT = false;

async function batchVocalize() {
    if (!confirm("Tüm sayfalar sırayla seslendirilecek ve kaydedilecek.\\nBu işlem uzun sürebilir ve API kredisi kullanır.\\nDevam edilsin mi?")) return;
    
    BATCH_ABORT = false;
    const btn = document.getElementById("btnBatch");
    if (btn) btn.disabled = true;
    
    // Use the global PAGES array which is built from mapping
    const pages = PAGES || [];
    let processed = 0;
    
    const N = pages.length || 0;
    
    // Overlay
    const ov = document.createElement("div");
    ov.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;";
    ov.innerHTML = `<h3>Toplu Seslendirme</h3><div id='batchStatus'>Hazırlanıyor...</div><br><button onclick='BATCH_ABORT=true;this.innerText="Durduruluyor...";'>Durdur</button>`;
    document.body.appendChild(ov);
    const st = document.getElementById("batchStatus");

    try {
        const currentNusha = (typeof ACTIVE_NUSHA === "number") ? ACTIVE_NUSHA : 1;
        for (let i = 0; i < N; i++) {
            if (BATCH_ABORT) break;
            st.innerText = `Nüsha ${currentNusha} - Sayfa ${i+1} / ${N} işleniyor...`;
            
            const pObj = pages[i];
            const key = pObj.key || ("p" + i);
            
            // If already cached, skip? 
            // Only skip for Nusha 1. For other Nushas, we likely want to generate fresh/specific audio
            // or at least not be blocked by Nusha 1 cache.
            if (currentNusha === 1 && cachedAudio && cachedAudio[key]) {
                 console.log(`Skipping ${key}, already cached.`);
                 processed++;
                 continue;
            }
            
            // Re-implement simplified bound checks
            let toks = [];
            let start = 0;
            
            if (tahkikTokens && tahkikTokens.length) {
                const b = _ttsComputePageBounds(pObj);
                toks = tahkikTokens.slice(b.start, b.end);
                start = b.start;
            } else {
                const fb = _ttsComputePageBoundsFromRaw(pObj);
                toks = fb.tokens || [];
                start = 0; // relative to itself if raw
            }
            
            if (!toks || !toks.length) {
                console.warn("No tokens for page", i);
                continue;
            }
            
            // Limit chunks to avoid huge payload (just like ttsPrepare)
             const maxTok = 2400; 
             const toks2 = toks.slice(0, maxTok);
             
             // API Call
             try {
                const resp = await fetch(TTS_URL, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        tokens: toks2,
                        token_start: start,
                        chunk_size: 450,
                        language_code: "ar-XA",
                        gender: "MALE",
                        voice_name: "ar-XA-Wavenet-B",
                        speaking_rate: TTS_RATE,
                        action: "batch_save",
                        page_key: key,
                        nusha_id: currentNusha,
                        archive_path: (archivePath || null),
                        reset_log: (i === 0)
                    })
                });
                const obj = await resp.json();
                if (!resp.ok) throw new Error(obj.error || resp.status);
                
                // Update local cache manually so we don't need reload
                if (obj.ok && obj.saved_chunks) {
                    // Update specific nusha cache
                    if (!ALL_AUDIO_CACHES[currentNusha]) ALL_AUDIO_CACHES[currentNusha] = {};
                    ALL_AUDIO_CACHES[currentNusha][key] = obj.saved_chunks;
                    
                    // If viewing active nusha, sync pointer
                    if (currentNusha == ACTIVE_NUSHA) {
                        cachedAudio = ALL_AUDIO_CACHES[ACTIVE_NUSHA];
                    }
                }
                
             } catch(e) {
                 console.error("Batch error page", i, e);
                 st.innerText += `\nHata (Sayfa ${i+1}): ${e.message}`;
                 await new Promise(r => setTimeout(r, 2000));
             }
             
             processed++;
        }
        st.innerText = BATCH_ABORT ? "Durduruldu." : "Tamamlandı!";
        await new Promise(r => setTimeout(r, 1000));
    } catch(e) {
        alert("Batch hatası: " + e);
    } finally {
        document.body.removeChild(ov);
        if (btn) btn.disabled = false;
        
        // Auto-prepare current page if it was part of the batch
        if (cachedAudio && cachedAudio[ACTIVE_PAGE_KEY]) {
             await ttsPrepare(); 
             // ttsPrepare is async, it updates UI to 'Ready'
        }
        
        alert("İşlem bitti.");
    }
}

function applyFontSize() {
  fontSize = Math.max(12, Math.min(36, fontSize));
  document.documentElement.style.setProperty('--textSize', fontSize + 'px');
  const lab = document.getElementById("fsLabel");
  if (lab) lab.textContent = fontSize + "px";
}

function loadFontSize() {
  try {
    const v = localStorage.getItem(keyFS);
    if (v) {
      const n = parseInt(v, 10);
      if (!isNaN(n)) fontSize = n;
    }
  } catch(e) {}
  applyFontSize();
}

function incFont() {
  fontSize += 2;
  applyFontSize();
  try { localStorage.setItem(keyFS, String(fontSize)); } catch(e) {}
}

function decFont() {
  fontSize -= 2;
  applyFontSize();
  try { localStorage.setItem(keyFS, String(fontSize)); } catch(e) {}
}

function _clampPageZoom(z) {
  const n = (typeof z === "number") ? z : parseFloat(String(z || ""));
  if (!isFinite(n)) return 1.0;
  const clamped = Math.max(1.0, Math.min(5.0, n));
  // Snap to 2% increments for finer control (100, 102, 104, ... 112, 140, 160, ...)
  const snapped = Math.round(clamped / 0.02) * 0.02;
  return Math.max(1.0, Math.min(5.0, snapped));
}

function applyPageZoom() {
  PAGE_ZOOM = _clampPageZoom(PAGE_ZOOM);
  const wrap = document.getElementById("pageWrap");
  if (wrap) wrap.style.width = Math.round(PAGE_ZOOM * 100) + "%";
  const lab = document.getElementById("pageZoomLabel");
  if (lab) lab.textContent = Math.round(PAGE_ZOOM * 100) + "%";
}

function loadPageZoom() {
  try {
    const v = localStorage.getItem(keyPageZoom);
    if (v) PAGE_ZOOM = _clampPageZoom(parseFloat(v));
  } catch(e) {}
  applyPageZoom();
}

function setPageZoom(z) {
  PAGE_ZOOM = _clampPageZoom(z);
  applyPageZoom();
  try { localStorage.setItem(keyPageZoom, String(PAGE_ZOOM)); } catch(e) {}
}

function incPageZoom() { setPageZoom(PAGE_ZOOM + 0.04); }
function decPageZoom() { setPageZoom(PAGE_ZOOM - 0.04); }
function resetPageZoom() { setPageZoom(1.0); }

function _clampSplit(x) {
  const n = (typeof x === "number") ? x : parseFloat(String(x || ""));
  if (!isFinite(n)) return 0.52;
  return Math.max(0.18, Math.min(0.82, n));
}

function applySplit() {
  // If list pane is hidden, force page pane to full width.
  try {
    if (document.body.classList.contains("hideList")) return;
  } catch(e) {}
  SPLIT = _clampSplit(SPLIT);
  const left = document.getElementById("pagePane");
  const right = document.getElementById("listPane");
  const sp = document.getElementById("splitter");
  if (!left || !right || !sp) return;
  // account for splitter fixed px width by using calc()
  const lp = Math.round(SPLIT * 1000) / 10; // 1 decimal
  const rp = Math.round((100 - lp) * 10) / 10;
  left.style.width = `calc(${lp}% - 5px)`;
  right.style.width = `calc(${rp}% - 5px)`;
}

function loadSplit() {
  try {
    const v = localStorage.getItem(keySplit);
    if (v) SPLIT = _clampSplit(parseFloat(v));
  } catch(e) {}
  applySplit();
}

function _initSplitterDrag() {
  const sp = document.getElementById("splitter");
  const wrap = sp ? sp.parentElement : null;
  if (!sp || !wrap) return;
  let dragging = false;

  function onMove(ev) {
    if (!dragging) return;
    const rect = wrap.getBoundingClientRect();
    const x = (ev.clientX - rect.left);
    const ratio = x / Math.max(1, rect.width);
    SPLIT = _clampSplit(ratio);
    applySplit();
  }
  function onUp() {
    if (!dragging) return;
    dragging = false;
    try { localStorage.setItem(keySplit, String(SPLIT)); } catch(e) {}
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  }
  sp.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    try { if (document.body.classList.contains("hideList")) return; } catch(e) {}
    dragging = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  });
}

function applyListPaneState() {
  try {
    if (HIDE_LIST) document.body.classList.add("hideList");
    else document.body.classList.remove("hideList");
  } catch(e) {}
  const b = document.getElementById("btnToggleList");
  if (b) b.textContent = HIDE_LIST ? "Dizgiyi Göster" : "Dizgiyi Gizle";
  // When showing again, restore split widths.
  if (!HIDE_LIST) applySplit();
}

function loadListPaneState() {
  try {
    const v = localStorage.getItem(keyHideList);
    HIDE_LIST = (v === "1");
  } catch(e) {}
  applyListPaneState();
}

function toggleListPane() {
  HIDE_LIST = !HIDE_LIST;
  try { localStorage.setItem(keyHideList, HIDE_LIST ? "1" : "0"); } catch(e) {}
  applyListPaneState();
}

try {
  const saved = localStorage.getItem(keyMap) || (!archivePath ? localStorage.getItem(keyMapLegacy) : null);
  if (saved) {
    const parsed = JSON.parse(saved);
    // IMPORTANT:
    // Older saved mappings may not include `line_marks` (spellcheck highlights).
    // If we blindly replace `mapping`, AI error spans disappear and model-nav buttons show 0.
    // So we MERGE: keep fresh DATA (incl. line_marks), only apply saved alignment overrides.
    if (parsed && Array.isArray(parsed)) {
      const byLine = new Map();
      parsed.forEach(it => {
        if (it && typeof it === "object" && typeof it.line_no === "number") {
          byLine.set(it.line_no, it);
        }
      });
      mappingPrimary = (DATA.aligned || []).map(cur => {
        const sv = byLine.get(cur.line_no);
        if (!sv) return cur;
        const out = Object.assign({}, cur);
        // Apply only alignment-related overrides; keep current line_marks/sources.
        if (sv.best && typeof sv.best === "object") out.best = sv.best;
        if (Array.isArray(sv.candidates)) out.candidates = sv.candidates;
        return out;
      });
      // If we're currently showing Nüsha 1, apply the merged mapping immediately.
      if (ACTIVE_NUSHA === 1) mapping = mappingPrimary;
    }
  }
} catch(e) {}

function imgSrc(pathStr) {
  const p = (pathStr || "").replaceAll("\\\\","/");
  const name = p.split("/").pop();
  // IMPORTANT:
  // alignment.json stores absolute paths, but the viewer HTML is opened from either:
  // - output_lines/viewer*.html (where images live under ./lines and ./nusha2/lines)
  // - output_lines/doc_archives/<ts>/viewer*.html (where images are copied under ./lines and ./nusha2/lines)
  // So we must not drop the directory info for Nüsha 2; otherwise it would incorrectly load from Nüsha 1.
  if (p.includes("/nusha2/")) return "nusha2/lines/" + name;
  if (p.includes("/nusha3/")) return "nusha3/lines/" + name;
  if (p.includes("/nusha4/")) return "nusha4/lines/" + name;
  return "lines/" + name;
}

function pageSrc(pathStr) {
  const p = (pathStr || "").replaceAll("\\\\","/");
  const name = p.split("/").pop();
  if (p.includes("/nusha2/")) return "nusha2/pages/" + name;
  if (p.includes("/nusha3/")) return "nusha3/pages/" + name;
  if (p.includes("/nusha4/")) return "nusha4/pages/" + name;
  return "pages/" + name;
}

function escapeHtml(s) {
  // Attribute-safe escaping (title/data-*)
  return (s || "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#39;");
}

function normalizeArJS(s) {
  if (!s) return "";
  s = s.replaceAll("\u0640", "");
  s = s.replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, "");
  s = s.replace(/[أإآ]/g, "ا").replace(/ى/g, "ي").replace(/ئ/g, "ي").replace(/ؤ/g, "و").replace(/ة/g, "ه");
  s = s.replace(/[^\u0600-\u06FF0-9A-Za-z\s]+/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

function _findNextTokenSpan(hay, needle, startAt) {
  if (!Array.isArray(hay) || !Array.isArray(needle) || needle.length === 0) return null;
  const n = needle.length;
  const st = Math.max(0, Math.min(parseInt(startAt || 0, 10) || 0, hay.length));
  for (let i = st; i <= hay.length - n; i++) {
    let ok = true;
    for (let j = 0; j < n; j++) {
      if (hay[i + j] !== needle[j]) { ok = false; break; }
    }
    if (ok) return [i, i + n];
  }
  return null;
}

function _injectLineMarksFromPP(pp, targetMapping) {
  // Mirrors Python _inject_line_marks: occurrence-based highlight by global token index.
  const tgt = targetMapping || mapping;
  const globalNorm = [];
  const paraStart = new Map();      // pidx -> base offset
  const paraTokens = new Map();     // pidx -> tokens norm

  for (const p of (pp || [])) {
    if (!p || typeof p !== "object") continue;
    const pidx = p.paragraph_index;
    if (typeof pidx !== "number") continue;
    const text = String(p.text || "");
    const toks = text.split(/\s+/).filter(Boolean);
    const toksNorm = toks.map(t => normalizeArJS(t));
    paraStart.set(pidx, globalNorm.length);
    paraTokens.set(pidx, toksNorm);
    for (const t of toksNorm) globalNorm.push(t);
  }

  const occ = new Map();      // gidx -> meta
  const nextStart = new Map(); // key -> next search start

  for (const p of (pp || [])) {
    if (!p || typeof p !== "object") continue;
    const pidx = p.paragraph_index;
    if (typeof pidx !== "number") continue;
    if (!paraStart.has(pidx)) continue;
    const errs = Array.isArray(p.errors) ? p.errors : [];
    if (!errs.length) continue;
    const hay = paraTokens.get(pidx) || [];
    const base = paraStart.get(pidx) || 0;

    for (const e of errs) {
      if (!e || typeof e !== "object") continue;
      const wrong = String(e.wrong || "").trim();
      if (!wrong) continue;
      const needle = normalizeArJS(wrong).split(/\s+/).filter(Boolean);
      if (!needle.length) continue;
      const key = needle.join("|");
      const s0 = nextStart.get(key) || 0;
      const span = _findNextTokenSpan(hay, needle, s0);
      if (!span) continue;
      const s = span[0], t = span[1];
      nextStart.set(key, Math.max(t, s + 1));
      for (let off = s; off < t; off++) {
        const gidx = base + off;
        if (occ.has(gidx)) continue;
        occ.set(gidx, {
          gidx,
          wrong: (e.wrong || ""),
          wrong_norm: normalizeArJS(e.wrong || ""),
          suggestion: (e.suggestion || ""),
          reason: (e.reason || ""),
          sources: (e.sources || []),
          paragraph_index: pidx
        });
      }
    }
  }

  for (const it of (tgt || [])) {
    const best = it.best || {};
    let start = best.start_word, end = best.end_word;
    if (typeof start !== "number" || typeof end !== "number") {
      it.line_marks = [];
      continue;
    }
    start = Math.max(0, Math.min(start, globalNorm.length));
    end = Math.max(start, Math.min(end, globalNorm.length));
    const marks = [];
    for (let g = start; g < end; g++) {
      if (occ.has(g)) marks.push(occ.get(g));
    }
    it.line_marks = marks;
  }
}

function _resetNavState() {
  try { for (const k of Object.keys(_errNavState)) delete _errNavState[k]; } catch (e) {}
  _setNavInfo("");
  const el = document.getElementById("navInfo");
  if (el) el.style.display = "none";
}

function _ppFromArchive(arch) {
  // Use current spellPP texts, but archive errors as source of truth.
  const ppErrs = (arch && Array.isArray(arch.per_paragraph_errors)) ? arch.per_paragraph_errors : [];
  const byP = new Map();
  for (const blk of ppErrs) {
    if (!blk || typeof blk !== "object") continue;
    const pidx = blk.paragraph_index;
    if (typeof pidx !== "number") continue;
    byP.set(pidx, Array.isArray(blk.errors) ? blk.errors : []);
  }
  return (spellPP || []).map((p) => {
    const pidx = p.paragraph_index;
    return {
      paragraph_index: pidx,
      text: p.text || "",
      errors: byP.get(pidx) || []
    };
  });
}

function applyCurrentSpellcheck() {
  ACTIVE_SOURCE = { kind: "current", label: "Güncel sonuç" };
  setSourceLabel();
  ACTIVE_PP_FOR_MARKS = (spellPP || []);
  _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingPrimary);
  if (Array.isArray(mappingAlt) && mappingAlt.length) _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingAlt);
  if (Array.isArray(mappingAlt3) && mappingAlt3.length) _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingAlt3);
  _resetNavState();
  setHeaderErrCount();
  renderAll();
}

function applyArchiveSpellcheck(idx) {
  const a = (Array.isArray(scArchives) && idx >= 0) ? scArchives[idx] : null;
  if (!a) return;
  ACTIVE_SOURCE = { kind: "archive", label: `Arşiv: ${a.file || ("#" + String(idx+1))}` };
  setSourceLabel();
  const pp = _ppFromArchive(a);
  ACTIVE_PP_FOR_MARKS = pp;
  _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingPrimary);
  if (Array.isArray(mappingAlt) && mappingAlt.length) _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingAlt);
  if (Array.isArray(mappingAlt3) && mappingAlt3.length) _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS, mappingAlt3);
  _resetNavState();
  setHeaderErrCount();
  renderAll();
  try { closeErrPop(); } catch (e) {}
}

function classifyErr(meta) {
  const src = meta.sources || [];
  if (!src || src.length === 0) return "err-both err-unknown";
  const hasG = src.includes("gemini");
  const hasO = src.includes("openai");
  const hasC = src.includes("claude");
  if (hasG && hasO && hasC) return "err-all";
  // Birden fazla class döndürebilir (space-separated)
  if (hasG && hasO) return "err-both err-gptgem";
  if (hasO && hasC) return "err-both err-gptclaude";
  if (hasG && hasC) return "err-both";
  if (hasG) return "err-gem";
  if (hasO) return "err-oa";
  if (hasC) return "err-claude";
  return "err-both";
}

function tooltipText(meta) {
  const s = [];
  if (meta.suggestion) s.push("Öneri: " + meta.suggestion);
  if (meta.reason) s.push("Not: " + meta.reason);
  const src = (meta.sources || []).join(", ");
  if (src) s.push("Kaynak: " + src);
  return s.join("\\n");
}

function highlightTextArabic(raw, startWord, lineMarks) {
  if (!raw) return "";
  if (!lineMarks || lineMarks.length === 0) return escapeHtml(raw);

  // Map by global token index for occurrence-accurate highlighting
  const byIdx = {};
  lineMarks.forEach(m => {
    const gi = m.gidx;
    if (typeof gi === "number") byIdx[gi] = m;
  });

  const parts = raw.split(/(\s+)/);
  let tokI = 0; // token counter within raw
  const out = parts.map(p => {
    if (!p) return "";
    if (/^\s+$/.test(p)) return p;
    const gidx = (typeof startWord === "number" ? startWord : 0) + tokI;
    tokI += 1;
    if (byIdx[gidx]) {
      const meta = byIdx[gidx];
      const cls = classifyErr(meta);
      const tip = escapeHtml(tooltipText(meta));
      const src = (meta.sources || []).join(" ");
      const sug = escapeHtml(meta.suggestion || "");
      const reason = escapeHtml(meta.reason || "");
      const wrong = escapeHtml(meta.wrong || p);
      const pidx = (meta.paragraph_index ?? "");
      return `<span class="err ${cls}" data-gidx="${escapeHtml(String(gidx))}" data-src="${escapeHtml(src)}" data-wrong="${wrong}" data-sug="${sug}" data-reason="${reason}" data-pidx="${escapeHtml(String(pidx))}" title="${tip}">${escapeHtml(p)}</span>`;
    }
    // non-highlighted token
    return escapeHtml(p);
  });
  return out.join("");
}

// --- AI error navigation (Gemini / GPT(OpenAI) / Claude / commons) ---
const _errNavState = { gemini: -1, openai: -1, claude: -1, gptgem: -1, gptclaude: -1, all3: -1 };

function _setNavInfo(msg) {
  const el = document.getElementById("navInfo");
  if (!el) return;
  if (!msg) { el.style.display = "none"; el.textContent = ""; return; }
  el.style.display = "inline-block";
  el.textContent = String(msg);
  try { window.clearTimeout(_setNavInfo._t); } catch(e) {}
  _setNavInfo._t = window.setTimeout(() => { el.style.display = "none"; }, 2200);
}

function _allErrMarksGlobal() {
  // Global list across ALL pages (not just currently-rendered spans).
  const out = [];
  for (const it of (mapping || [])) {
    if (!it || typeof it !== "object") continue;
    const lineNo = it.line_no;
    const marks = Array.isArray(it.line_marks) ? it.line_marks : [];
    for (const m of marks) {
      if (!m || typeof m !== "object") continue;
      const gidx = m.gidx;
      if (typeof lineNo !== "number" || typeof gidx !== "number") continue;
      const srcs = Array.isArray(m.sources) ? m.sources.map(x => String(x||"").toLowerCase()) : [];
      out.push({
        line_no: lineNo,
        gidx,
        sources: srcs,
        paragraph_index: m.paragraph_index ?? "",
        wrong_norm: m.wrong_norm || "",
      });
    }
  }
  out.sort((a,b) => (a.line_no - b.line_no) || (a.gidx - b.gidx));
  return out;
}

function _marksForSource(srcName) {
  const key = String(srcName || "").trim().toLowerCase();
  if (!key) return [];
  const all = _allErrMarksGlobal();
  return all.filter(m => Array.isArray(m.sources) && m.sources.includes(key));
}

function _marksForGptGemCommon() {
  const all = _allErrMarksGlobal();
  return all.filter(m => (m.sources||[]).includes("gemini") && (m.sources||[]).includes("openai"));
}

function _marksForGptClaudeCommon() {
  const all = _allErrMarksGlobal();
  return all.filter(m => (m.sources||[]).includes("openai") && (m.sources||[]).includes("claude"));
}

function _marksForAllThreeCommon() {
  const all = _allErrMarksGlobal();
  return all.filter(m => (m.sources||[]).includes("gemini") && (m.sources||[]).includes("openai") && (m.sources||[]).includes("claude"));
}

function _scrollSpanIntoLeft(el) {
  // Page-based viewer: right pane (#listPane) is the scroll container for spans.
  const pane = document.getElementById("listPane");
  if (!pane || !el) {
    try { el.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" }); } catch(e) { try { el.scrollIntoView(); } catch(_e) {} }
    return;
  }
  // Manual scroll to avoid inconsistent scrollIntoView behavior with nested containers
  const r = el.getBoundingClientRect();
  const pr = pane.getBoundingClientRect();
  const nav = document.querySelector(".floatNav");
  const navH = nav ? nav.getBoundingClientRect().height : 0;
  // Place target just BELOW the floating nav so it never covers UI
  const margin = 16;
  const target = (r.top - pr.top) + pane.scrollTop - navH - margin;
  pane.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
}

function _gotoMarkList(key, marks, label) {
  if (!marks || marks.length === 0) return;
  const cur = _errNavState[key] ?? -1;
  const next = (cur + 1) % marks.length;
  _errNavState[key] = next;
  const m = marks[next];
  const lab = label || key || "";
  _setNavInfo(`${lab}: ${next + 1}/${marks.length}`);
  if (!m) return;
  // Jump across pages
  selectLine(m.line_no);
  // After render, scroll to the exact error span (by gidx)
  window.setTimeout(() => {
    try {
      const el = document.querySelector(`span.err[data-gidx='${String(m.gidx)}']`);
      if (el) _scrollSpanIntoLeft(el);
    } catch(e) {}
  }, 120);
}

function gotoErrBySource(srcName) {
  const marks = _marksForSource(srcName);
  if (!marks.length) return;
  const label = (srcName === "openai") ? "GPT" : (srcName === "claude") ? "Claude" : "Gemini";
  _gotoMarkList(srcName, marks, label);
}

function gotoGptGemCommon() {
  const marks = _marksForGptGemCommon();
  if (!marks.length) return;
  _gotoMarkList("gptgem", marks, "GPT+Gemini ortak");
}

function gotoGptClaudeCommon() {
  const marks = _marksForGptClaudeCommon();
  if (!marks.length) return;
  _gotoMarkList("gptclaude", marks, "GPT+Claude ortak");
}

function gotoAllThreeCommon() {
  const marks = _marksForAllThreeCommon();
  if (!marks.length) return;
  _gotoMarkList("all3", marks, "3'ü ortak");
}

// --- Click-to-explain: click highlighted word to see reason/suggestion ---
function openErrPopFromSpan(spanEl) {
  const overlay = document.getElementById("errPop");
  const body = document.getElementById("errPopBody");
  if (!overlay || !body || !spanEl) return;

  const wrong = spanEl.getAttribute("data-wrong") || (spanEl.textContent || "");
  const sug = spanEl.getAttribute("data-sug") || "";
  const reason = spanEl.getAttribute("data-reason") || "";
  const src = spanEl.getAttribute("data-src") || "";
  const pidx = spanEl.getAttribute("data-pidx") || "";

  body.innerHTML = `
    <div class="popBox">
      <div class="k">Hatalı</div>
      <div class="v">${escapeHtml(wrong)}</div>
    </div>
    ${sug ? `<div class="popBox"><div class="k">Öneri</div><div class="v">${escapeHtml(sug)}</div></div>` : ``}
    ${reason ? `<div class="popBox"><div class="k">Açıklama</div><div class="v">${escapeHtml(reason)}</div></div>` : `<div class="popBox"><div class="k">Açıklama</div><div class="small muted">Bu hata için açıklama yok.</div></div>`}
    ${(src || pidx) ? `<div class="popBox"><div class="k">Bilgi</div><div class="small">${pidx ? `Paragraf: <b>${escapeHtml(pidx)}</b>` : ``}${(src && pidx) ? ` • ` : ``}${src ? `Kaynak: <b>${escapeHtml(src)}</b>` : ``}</div></div>` : ``}
  `;

  overlay.classList.add("open");
}

function closeErrPop(ev) {
  const overlay = document.getElementById("errPop");
  if (!overlay) return;
  overlay.classList.remove("open");
}

function _fmtRun(r) {
  if (!r || typeof r !== "object") return "";
  const ts = r.ts || "";
  const sp = r.start_paragraph || "";
  const prov = r.provider ? ` (${r.provider})` : "";
  const mods = (r.models && typeof r.models === "object")
    ? Object.entries(r.models).filter(([_, v]) => !!v).map(([k,_]) => k).join(", ")
    : "";
  const mtxt = mods ? ` • ${mods}` : "";
  return `${ts} • P${sp}${prov}${mtxt}`;
}

function setRunLabel() {
  const el = document.getElementById("scRunLabel");
  if (!el) return;
  if (!Array.isArray(scRuns) || scRuns.length === 0) {
    el.textContent = "run yok";
    return;
  }
  const last = scRuns[scRuns.length - 1];
  const sp = (last && last.start_paragraph) ? String(last.start_paragraph) : "?";
  el.textContent = `${scRuns.length} koşu • son: P${sp}`;
}
setRunLabel();

function setSourceLabel() {
  const el = document.getElementById("scSourceLabel");
  if (!el) return;
  el.textContent = ACTIVE_SOURCE && ACTIVE_SOURCE.label ? String(ACTIVE_SOURCE.label) : "";
}
setSourceLabel();

function showSpellcheckRuns() {
  const body = document.getElementById("errPopBody");
  const pop = document.getElementById("errPop");
  if (!body || !pop) return;
  if (!Array.isArray(scRuns) || scRuns.length === 0) {
    body.innerHTML = `<div class="popBox"><div class="k">Spellcheck runs</div><div class="small">Kayıt yok.</div></div>`;
    pop.classList.add("open");
    return;
  }
  const rows = scRuns.slice(-200).reverse().map((r) => {
    return `<div class="popBox"><div class="k">${escapeHtml(_fmtRun(r))}</div></div>`;
  }).join("");
  body.innerHTML = `
    <div class="popBox">
      <div class="k">Spellcheck runs</div>
      <div class="small">Son 200 koşu gösteriliyor (en yeni üstte).</div>
    </div>
    ${rows}
  `;
  pop.classList.add("open");
}

function _fmtSel(sel) {
  if (!Array.isArray(sel) || !sel.length) return "";
  const s = sel.map(x => parseInt(x, 10)).filter(x => !isNaN(x)).sort((a,b)=>a-b);
  if (!s.length) return "";
  if (s.length === 1) return ` • seçili: P${s[0]}`;
  return ` • seçili: ${s.length} (P${s[0]}–P${s[s.length-1]})`;
}

function _fmtArch(a) {
  if (!a || typeof a !== "object") return "";
  const ts = a.ts || "";
  const sp = a.start_paragraph || "";
  const prov = a.provider ? ` (${a.provider})` : "";
  const mods = (a.models && typeof a.models === "object")
    ? Object.entries(a.models).filter(([_, v]) => !!v).map(([k,_]) => k).join(", ")
    : "";
  const mtxt = mods ? ` • ${mods}` : "";
  const selTxt = _fmtSel(a.selected_paragraphs);
  const cnt = (typeof a.error_count === "number") ? ` • ${a.error_count} hata` : "";
  return `${ts} • P${sp}${selTxt}${prov}${mtxt}${cnt}`;
}

function showArchiveErrors(idx) {
  const body = document.getElementById("errPopBody");
  const pop = document.getElementById("errPop");
  if (!body || !pop) return;
  const a = (Array.isArray(scArchives) && idx >= 0) ? scArchives[idx] : null;
  if (!a) return;
  const errs = Array.isArray(a.errors_merged) ? a.errors_merged : [];
  const rows = errs.slice(0, 400).map((e) => {
    const w = (e && e.wrong) ? String(e.wrong) : "";
    const s = (e && e.suggestion) ? String(e.suggestion) : "";
    const r = (e && e.reason) ? String(e.reason) : "";
    const srcs = (e && e.sources) ? e.sources : [];
    const srcTxt = Array.isArray(srcs) && srcs.length ? ` • ${srcs.join(",")}` : "";
    return `<div class="popBox">
      <div class="k">${escapeHtml(w)}${srcTxt ? `<span class="small muted">${escapeHtml(srcTxt)}</span>` : ``}</div>
      ${s ? `<div class="v">${escapeHtml(s)}</div>` : ``}
      ${r ? `<div class="small muted">${escapeHtml(r)}</div>` : ``}
    </div>`;
  }).join("");
  body.innerHTML = `
    <div class="popBox">
      <div class="k">Arşiv sonuçları</div>
      <div class="small muted">${escapeHtml(_fmtArch(a))}</div>
      <div class="small">İlk 400 hata gösteriliyor.</div>
      <div style="margin-top:8px;"><button class="btn small" onclick="showSpellcheckArchives()">Geri</button></div>
    </div>
    ${rows || `<div class="popBox"><div class="small muted">Hata yok.</div></div>`}
  `;
  pop.classList.add("open");
}

function showSpellcheckArchives() {
  const body = document.getElementById("errPopBody");
  const pop = document.getElementById("errPop");
  if (!body || !pop) return;
  if (!Array.isArray(scArchives) || scArchives.length === 0) {
    body.innerHTML = `<div class="popBox"><div class="k">Eski sonuçlar</div><div class="small">Arşiv yok.</div></div>`;
    pop.classList.add("open");
    return;
  }
  const rows = scArchives.slice(0, 30).map((a, i) => {
    return `<div class="popBox">
      <div class="k">${escapeHtml(_fmtArch(a))}</div>
      <div class="small muted">${escapeHtml(a.file || "")}</div>
      <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
        <button class="btn small" onclick="applyArchiveSpellcheck(${i})">Viewer’da aç (kaynak yap)</button>
        <button class="btn small" onclick="showArchiveErrors(${i})">Sadece liste</button>
      </div>
    </div>`;
  }).join("");
  body.innerHTML = `
    <div class="popBox">
      <div class="k">Eski sonuçlar</div>
      <div class="small muted">Son 30 arşiv gösteriliyor (en yeni üstte).</div>
      <div style="margin-top:8px;"><button class="btn small" onclick="applyCurrentSpellcheck()">Güncel sonuca dön</button></div>
    </div>
    ${rows}
  `;
  pop.classList.add("open");
}

document.addEventListener("click", (ev) => {
  const t = ev.target;
  if (!t) return;
  if (t.classList && t.classList.contains("err")) {
    openErrPopFromSpan(t);
  }
});

document.addEventListener("keydown", (ev) => {
  if (ev && ev.key === "Escape") closeErrPop();
  if (ev && ev.shiftKey && (ev.key === "ArrowUp" || ev.key === "Up")) {
    try { toggleHeader(); } catch (e) {}
    ev.preventDefault();
  }
});

// --- HTML report save + archive (localStorage) ---
function _docTitleFromWordFirstWords() {
  // Use first words from Word (paragraph 1) as title; fallback to docx filename
  try {
    const t = (spellPP && spellPP.length && spellPP[0] && spellPP[0].text) ? String(spellPP[0].text) : "";
    const ws = t.trim().split(/\s+/).filter(Boolean);
    if (ws.length) return ws.slice(0, 10).join(" ");
  } catch (e) {}
  try {
    const p = String(DATA.docx_path || "").replaceAll("\\\\", "/");
    const name = p.split("/").pop() || "report";
    return name.replace(/\.docx$/i, "");
  } catch (e) {}
  return "report";
}

function _safeFileBase(s) {
  const t = (s || "").trim();
  const cleaned = t
    .replace(/[^\u0600-\u06FFA-Za-z0-9\s\-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 60);
  return cleaned.replace(/\s+/g, "_") || "report";
}

function _downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function _collectMarksForReport() {
  const out = [];
  const seen = new Set();
  for (const it of (mapping || [])) {
    const best = it.best || {};
    const marks = it.line_marks || [];
    for (const m of marks) {
      const gidx = m.gidx;
      if (typeof gidx !== "number") continue;
      const key = String(gidx);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        gidx,
        line_no: it.line_no,
        line_image: it.line_image,
        start_word: (typeof best.start_word === "number" ? best.start_word : 0),
        raw: best.raw || "",
        wrong: m.wrong || "",
        suggestion: m.suggestion || "",
        reason: m.reason || "",
        sources: m.sources || [],
        paragraph_index: m.paragraph_index ?? ""
      });
    }
  }
  out.sort((a,b) => (a.line_no||0)-(b.line_no||0) || (a.gidx||0)-(b.gidx||0));
  return out;
}

function _makeSnippet(raw, relIdx, wrong) {
  const toks = String(raw || "").split(/\s+/).filter(Boolean);
  if (!toks.length) return escapeHtml(raw || "");
  const i = Math.max(0, Math.min(toks.length - 1, relIdx));
  toks[i] = `<span class="err err-both">${escapeHtml(toks[i])}</span>`;
  return toks.join(" ");
}

function _renderSingleReportHtml(entry) {
  const title = escapeHtml(entry.title || "Rapor");
  const ts = escapeHtml(entry.timestamp || "");
  const docx = escapeHtml(entry.docx_path || "");
  const items = entry.items || [];
  const cards = items.map((it) => {
    const src = Array.isArray(it.sources) ? it.sources.join(", ") : String(it.sources || "");
    const rel = (it.gidx - it.start_word);
    const snippet = _makeSnippet(it.raw || "", rel, it.wrong || "");
    return `
      <div style="border:1px solid #eee;border-radius:12px;padding:10px;margin:10px 0;background:#fafafa;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          <span style="padding:4px 8px;border:1px solid #ddd;border-radius:999px;background:#fff;"><b>${escapeHtml(it.wrong||"")}</b></span>
          ${it.suggestion ? `<span style="padding:4px 8px;border:1px solid #ddd;border-radius:999px;background:#fff;">Öneri: ${escapeHtml(it.suggestion)}</span>` : ``}
          ${it.paragraph_index ? `<span style="padding:4px 8px;border:1px solid #ddd;border-radius:999px;background:#fff;">Paragraf ${escapeHtml(String(it.paragraph_index))}</span>` : ``}
          ${src ? `<span style="padding:4px 8px;border:1px solid #ddd;border-radius:999px;background:#fff;">Kaynak: ${escapeHtml(src)}</span>` : ``}
          ${it.line_no ? `<span style="padding:4px 8px;border:1px solid #ddd;border-radius:999px;background:#fff;">Satır ${escapeHtml(String(it.line_no))}</span>` : ``}
        </div>
        <div style="margin-top:8px;direction:rtl;unicode-bidi:isolate;font-family:Traditional Arabic, Noto Naskh Arabic, Amiri, Geeza Pro, serif;line-height:1.9;background:#fff;border:1px solid #eee;border-radius:10px;padding:8px;">${snippet}</div>
        <div style="margin-top:8px;background:#fff;border:1px solid #eee;border-radius:10px;padding:8px;">
          <div style="font-weight:800;margin-bottom:6px;">Açıklama</div>
          <div style="direction:rtl;unicode-bidi:isolate;font-family:Traditional Arabic, Noto Naskh Arabic, Amiri, Geeza Pro, serif;line-height:1.9;">${escapeHtml(it.reason||"") || "<span style='color:#666'>Açıklama yok.</span>"}</div>
        </div>
      </div>
    `;
  }).join("");
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>${title}</title></head>
  <body style="font-family:Arial,sans-serif;margin:16px;">
    <h2 style="margin:0 0 6px;">${title}</h2>
    <div style="color:#666;margin-bottom:12px;">${ts}${docx ? ` • ${docx}` : ""} • Kayıt: ${items.length}</div>
    ${cards || "<div style='color:#666'>Kayıt yok.</div>"}
  </body></html>`;
}

function _loadArchive() {
  try {
    const raw = localStorage.getItem(keyArchive);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch (e) { return []; }
}

function _saveArchive(arr) {
  try { localStorage.setItem(keyArchive, JSON.stringify(arr)); } catch (e) {}
}

function saveReportHtml() {
  const title = _docTitleFromWordFirstWords();
  const fileBase = _safeFileBase(title);
  const now = new Date();
  const ts = now.toISOString().replace("T"," ").slice(0,19);
  const items = _collectMarksForReport();
  const entry = {
    title,
    timestamp: ts,
    docx_path: (DATA.docx_path || ""),
    items
  };
  const arch = _loadArchive();
  arch.push(entry);
  _saveArchive(arch);

  const html = _renderSingleReportHtml(entry);
  _downloadTextFile(`imla_${fileBase}.html`, html);
  _setNavInfo("Rapor kaydedildi");
}

function downloadArchiveHtml() {
  const arch = _loadArchive();
  const title = "İmla Rapor Arşivi";
  const now = new Date();
  const ts = now.toISOString().replace("T"," ").slice(0,19);
  const body = arch.map((e, idx) => {
    const head = `${idx+1}. ${escapeHtml(e.title||"Rapor")} • ${escapeHtml(e.timestamp||"")}`;
    const html = _renderSingleReportHtml(e);
    // embed as <details> to keep file readable
    return `<details style="border:1px solid #eee;border-radius:12px;padding:10px;margin:10px 0;background:#fafafa;">
      <summary style="cursor:pointer;font-weight:800;">${head} (kayıt: ${(e.items||[]).length})</summary>
      <div style="margin-top:10px;">
        <iframe style="width:100%;height:520px;border:1px solid #ddd;border-radius:12px;background:#fff;" srcdoc="${escapeHtml(html)}"></iframe>
      </div>
    </details>`;
  }).join("");
  const html = `<!doctype html><html lang="tr"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>${escapeHtml(title)}</title></head>
    <body style="font-family:Arial,sans-serif;margin:16px;">
      <h2 style="margin:0 0 6px;">${escapeHtml(title)}</h2>
      <div style="color:#666;margin-bottom:12px;">${escapeHtml(ts)} • Toplam rapor: ${arch.length}</div>
      ${body || "<div style='color:#666'>Arşiv boş.</div>"}
    </body></html>`;
  _downloadTextFile(`imla_arsiv.html`, html);
  _setNavInfo("Arşiv indirildi");
}

function setHeaderErrCount() {
  const errLines = mapping.filter(x => (x.line_marks && x.line_marks.length > 0)).length;
  const el = document.getElementById("errCount");
  if (el) el.textContent = String(errLines);
}
setHeaderErrCount();

function _setCompareBtnLabels() {
  // No-op: compare buttons are now rendered per-target (Nüsha 2 / Nüsha 3 separately).
}

// --- Page-based viewer (single mode): show full page + highlight bbox; right side is numbered tahkik list ---
function buildPagesIndex() {
  const pages = [];
  const byKey = new Map();
  (mapping || []).forEach(it => {
    const pimg = (it && it.page_image) ? String(it.page_image) : "";
    const pname = (it && it.page_name) ? String(it.page_name) : "";
    const key = pname || (pimg ? pimg.split("/").pop() : "unknown");
    if (!byKey.has(key)) {
      byKey.set(key, { key, page_image: pimg, page_name: pname, lines: [] });
      pages.push(byKey.get(key));
    }
    byKey.get(key).lines.push(it);
  });
  return pages;
}

let PAGES = buildPagesIndex();
let ACTIVE_PAGE_KEY = (PAGES[0] && PAGES[0].key) ? PAGES[0].key : null;
let ACTIVE_LINE_NO = null;

// Restore saved state
try {
  // Restore Nusha first
  const savedNusha = localStorage.getItem(keyActiveNusha);
  if (savedNusha) {
    const n = parseInt(savedNusha, 10);
    if (n === 1 || (n === 2 && HAS_N2) || (n === 3 && HAS_N3) || (n === 4 && HAS_N4)) {
       ACTIVE_NUSHA = n;
       // We must update 'mapping' because it was initialized before restoration
       mapping = (ACTIVE_NUSHA === 4) ? (Array.isArray(mappingAlt4) && mappingAlt4.length ? mappingAlt4 : mappingPrimary)
               : (ACTIVE_NUSHA === 3) ? (Array.isArray(mappingAlt3) && mappingAlt3.length ? mappingAlt3 : mappingPrimary)
               : (ACTIVE_NUSHA === 2) ? (Array.isArray(mappingAlt) && mappingAlt.length ? mappingAlt : mappingPrimary)
               : mappingPrimary;
       // Also ensure highlighted errors are injected into this new mapping
       if (typeof _injectLineMarksFromPP === "function") {
          _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS || [], mapping);
       }
      // Keep cached audio in sync with restored nusha so TTS can load after refresh.
      if (typeof ALL_AUDIO_CACHES !== "undefined") {
         cachedAudio = ALL_AUDIO_CACHES[ACTIVE_NUSHA] || {};
      }
       // CRITICAL: We changed mapping, so we MUST rebuild PAGES index immediately,
       // otherwise ACTIVE_PAGE_KEY restoration below will look at stale pages (N1).
       PAGES = buildPagesIndex();
    }
  }

  const savedKey = localStorage.getItem(keyActivePage);
  if (savedKey && _pageByKey(savedKey)) {
    ACTIVE_PAGE_KEY = savedKey;
  }
  const savedLine = localStorage.getItem(keyActiveLine);
  if (savedLine) {
    const ln = parseInt(savedLine, 10);
    if (Number.isFinite(ln)) ACTIVE_LINE_NO = ln;
  }
} catch(e) {}

// --- Dizgi arama (tüm sayfalarda) ---
const SEARCH = { q: "", qn: "", hits: [], idx: -1 };

function _countOcc(hayNorm, needleNorm) {
  if (!needleNorm) return 0;
  let c = 0;
  let i = 0;
  while (true) {
    const j = hayNorm.indexOf(needleNorm, i);
    if (j < 0) break;
    c += 1;
    i = j + Math.max(1, needleNorm.length);
  }
  return c;
}

function buildSearchHits(q) {
  const qq = String(q || "").trim();
  const qn = normalizeArJS(qq);
  SEARCH.q = qq;
  SEARCH.qn = qn;
  SEARCH.hits = [];
  SEARCH.idx = -1;
  if (!qn) return;
  for (const it of (mapping || [])) {
    if (!it || typeof it !== "object") continue;
    const best = it.best || {};
    const raw = String(best.raw || "");
    const hn = normalizeArJS(raw);
    const cnt = _countOcc(hn, qn);
    if (cnt > 0) {
      for (let k = 0; k < cnt; k++) {
        SEARCH.hits.push({ line_no: it.line_no });
      }
    }
  }
}

function setSearchLabel() {
  const el = document.getElementById("srchCount");
  if (!el) return;
  const total = SEARCH.hits.length;
  if (!SEARCH.qn || total === 0 || SEARCH.idx < 0) {
    el.textContent = (SEARCH.qn ? `0/${total}` : "0/0");
    return;
  }
  el.textContent = `${SEARCH.idx + 1}/${total}`;
}

function gotoSearchIndex(i) {
  const total = SEARCH.hits.length;
  if (!total) { SEARCH.idx = -1; setSearchLabel(); return; }
  SEARCH.idx = (i % total + total) % total;
  setSearchLabel();
  const hit = SEARCH.hits[SEARCH.idx];
  if (hit && typeof hit.line_no === "number") {
    selectLine(hit.line_no);
  }
}

function doSearch() {
  const inp = document.getElementById("srchInput");
  const q = inp ? inp.value : "";
  buildSearchHits(q);
  if (SEARCH.hits.length) gotoSearchIndex(0);
  else { setSearchLabel(); renderAll(); }
}

function nextSearch() {
  if (!SEARCH.hits.length) return;
  gotoSearchIndex((SEARCH.idx < 0 ? 0 : SEARCH.idx + 1));
}

function prevSearch() {
  if (!SEARCH.hits.length) return;
  gotoSearchIndex((SEARCH.idx < 0 ? 0 : SEARCH.idx - 1));
}

function clearSearch() {
  SEARCH.q = ""; SEARCH.qn = ""; SEARCH.hits = []; SEARCH.idx = -1;
  const inp = document.getElementById("srchInput");
  if (inp) inp.value = "";
  setSearchLabel();
  renderAll();
}

function _findPageByLine(lineNo) {
  for (const p of PAGES) {
    if ((p.lines||[]).some(it => it && it.line_no === lineNo)) return p;
  }
  return null;
}

function _pageByKey(key) {
  return PAGES.find(p => p.key === key) || null;
}

function renderPagePane(pageObj, activeLineNo) {
  const pane = document.getElementById("pagePane");
  if (!pane) return;
  if (!pageObj) {
    pane.innerHTML = `<div class="small muted">Sayfa bulunamadı.</div>`;
    return;
  }

  const pageImgPath = pageObj.page_image || "";
  const title = escapeHtml(pageObj.page_name || pageObj.key || "Sayfa");

  pane.innerHTML = `
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:10px;">
      <div class="pill">Sayfa: ${title}</div>
      <div class="row" style="align-items:center;">
        <button class="btn secondary small" onclick="decPageZoom()" title="Zoom - (Ctrl/⌘ + tekerlek)">−</button>
        <button class="btn secondary small" onclick="incPageZoom()" title="Zoom + (Ctrl/⌘ + tekerlek)">+</button>
        <button class="btn secondary small" onclick="resetPageZoom()" title="Zoom sıfırla">1:1</button>
        <span class="pill">Zoom: <span id="pageZoomLabel"></span></span>
        <button class="btn secondary small" onclick="prevPage()">← Sayfa</button>
        <button class="btn secondary small" onclick="nextPage()">Sayfa →</button>
      </div>
    </div>
    <div class="pageWrap" id="pageWrap">
      <img id="pageImg" class="pageImg" src="${pageSrc(pageImgPath)}" loading="lazy">
      <svg id="pageSvg" class="pageSvg" xmlns="http://www.w3.org/2000/svg"></svg>
    </div>
    <div class="small" style="margin-top:8px;color:#666;">Sağdaki satıra veya soldaki sayfada satırın üstüne tıkla: ilgili bölge aydınlanır (diğer yerler gölgelenir).</div>
  `;

  // Apply zoom state to the newly rendered page.
  applyPageZoom();

  // Ctrl/⌘ + wheel to zoom (like PDF viewers)
  try {
    const wrap = document.getElementById("pageWrap");
    if (wrap) {
      wrap.addEventListener("wheel", (e) => {
        if (!(e && (e.ctrlKey || e.metaKey))) return;
        e.preventDefault();
        // Trackpad pinch produces many small wheel events; use a smooth factor to avoid huge jumps.
        const dy = Math.max(-120, Math.min(120, Number(e.deltaY || 0)));
        const factor = Math.exp(-dy * 0.002); // dy=50 -> ~0.905, dy=5 -> ~0.99
        setPageZoom(PAGE_ZOOM * factor);
      }, { passive: false });
    }
  } catch(e) {}

  const img = document.getElementById("pageImg");
  const svg = document.getElementById("pageSvg");

  function _scrollToBBox(bb) {
    try {
      if (!pane || !img || !bb || bb.length < 4) return;
      const w0 = img.naturalWidth || 0;
      const h0 = img.naturalHeight || 0;
      if (!w0 || !h0) return;

      // Displayed size (in CSS px)
      const dispW = img.clientWidth || 0;
      const dispH = img.clientHeight || 0;
      if (!dispW || !dispH) return;
      const sx = dispW / w0;
      const sy = dispH / h0;

      const y0 = Math.max(0, bb[1] || 0);
      const y1 = Math.max(y0 + 1, bb[3] || 0);
      const topPx = img.offsetTop + (y0 * sy);
      const hPx = Math.max(8, (y1 - y0) * sy);

      // Keep the bbox near the TOP of the visible area (not centered).
      // This feels better for "following" playback/selection while reading.
      const anchor = Math.max(SYNC_SCROLL_ANCHOR_MIN_PX, (pane.clientHeight || 0) * SYNC_SCROLL_ANCHOR_RATIO);
      const target = Math.max(0, topPx - anchor + Math.min(16, hPx * 0.15)); // slight inset so bbox isn't glued to the line
      pane.scrollTo({ top: target, behavior: "smooth" });
    } catch(e) {}
  }

  function drawBox() {
    if (!svg || !img) return;
    const w = img.naturalWidth || 0;
    const h = img.naturalHeight || 0;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.innerHTML = "";

    // Clickable hit regions for each line bbox (so clicking page selects the matching tahkik line).
    let hitG = null;
    try {
      hitG = document.createElementNS("http://www.w3.org/2000/svg","g");
      hitG.setAttribute("id", "hitLayer");
      for (const it0 of (pageObj.lines || [])) {
        const bb0 = (it0 && Array.isArray(it0.bbox) && it0.bbox.length >= 4) ? it0.bbox : null;
        const ln0 = (it0 && typeof it0.line_no === "number") ? it0.line_no : null;
        if (!bb0 || ln0 == null) continue;
        const x0 = Math.max(0, bb0[0]||0), y0 = Math.max(0, bb0[1]||0);
        const x1 = Math.max(x0+1, bb0[2]||0), y1 = Math.max(y0+1, bb0[3]||0);
        const rw0 = x1 - x0, rh0 = y1 - y0;
        const r = document.createElementNS("http://www.w3.org/2000/svg","rect");
        r.setAttribute("x", String(x0));
        r.setAttribute("y", String(y0));
        r.setAttribute("width", String(rw0));
        r.setAttribute("height", String(rh0));
        r.setAttribute("fill", "rgba(0,0,0,0)"); // invisible but clickable
        r.setAttribute("pointer-events", "all");
        r.style.cursor = "pointer";
        r.addEventListener("click", (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          // Do NOT auto-open the right (dizgi) pane when it's hidden; keep hidden mode.
          selectLine(ln0, { scrollBehavior: "smooth" });
        });
        r.addEventListener("dblclick", (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          // Keep selection in sync, then show the dizgi/OCR popup.
          // Keep hidden mode if the user has hidden the dizgi pane.
          selectLine(ln0, { scrollBehavior: "smooth" });
          openLinePop(ln0);
        });
        hitG.appendChild(r);
      }
    } catch(e) {}

    // Find bbox for active line on this page
    const it = (pageObj.lines || []).find(x => x && x.line_no === activeLineNo);
    const bb = (it && Array.isArray(it.bbox) && it.bbox.length >= 4) ? it.bbox : null;
    if (!bb) {
      // No highlight yet, but still allow clicking to select lines.
      if (hitG) svg.appendChild(hitG);
      return;
    }
    const x0 = Math.max(0, bb[0]||0), y0 = Math.max(0, bb[1]||0);
    const x1 = Math.max(x0+1, bb[2]||0), y1 = Math.max(y0+1, bb[3]||0);
    const rw = x1 - x0, rh = y1 - y0;

    // Darken everything, leave bbox as hole using mask
    const defs = document.createElementNS("http://www.w3.org/2000/svg","defs");
    const mask = document.createElementNS("http://www.w3.org/2000/svg","mask");
    mask.setAttribute("id","holeMask");
    const full = document.createElementNS("http://www.w3.org/2000/svg","rect");
    full.setAttribute("x","0"); full.setAttribute("y","0");
    full.setAttribute("width", String(w)); full.setAttribute("height", String(h));
    full.setAttribute("fill","white");
    const hole = document.createElementNS("http://www.w3.org/2000/svg","rect");
    hole.setAttribute("x", String(x0)); hole.setAttribute("y", String(y0));
    hole.setAttribute("width", String(rw)); hole.setAttribute("height", String(rh));
    hole.setAttribute("fill","black");
    hole.setAttribute("rx","6"); hole.setAttribute("ry","6");
    mask.appendChild(full); mask.appendChild(hole);
    defs.appendChild(mask);
    svg.appendChild(defs);

    const dim = document.createElementNS("http://www.w3.org/2000/svg","rect");
    dim.setAttribute("x","0"); dim.setAttribute("y","0");
    dim.setAttribute("width", String(w)); dim.setAttribute("height", String(h));
    dim.setAttribute("fill","rgba(0,0,0,0.45)");
    dim.setAttribute("mask","url(#holeMask)");
    dim.setAttribute("pointer-events", "none"); // don't block clicks
    svg.appendChild(dim);

    const outline = document.createElementNS("http://www.w3.org/2000/svg","rect");
    outline.setAttribute("x", String(x0)); outline.setAttribute("y", String(y0));
    outline.setAttribute("width", String(rw)); outline.setAttribute("height", String(rh));
    outline.setAttribute("fill","none");
    outline.setAttribute("stroke","#00A3FF");
    outline.setAttribute("stroke-width","6");
    outline.setAttribute("rx","6"); outline.setAttribute("ry","6");
    outline.setAttribute("pointer-events", "none"); // don't block clicks
    svg.appendChild(outline);

    // Keep click layer on top, otherwise the dim overlay eats clicks.
    if (hitG) svg.appendChild(hitG);

    // After drawing the highlight, auto-scroll the page pane so the bbox is visible.
    try { requestAnimationFrame(() => _scrollToBBox(bb)); } catch(e) { _scrollToBBox(bb); }
  }

  if (img) {
    if (img.complete) drawBox();
    img.onload = () => drawBox();
  }
  drawBox();
}

function saveLine(lineNo, btn) {
  const item = btn.closest(".item");
  if (!item) return;
  const pre = item.querySelector("pre.arbox");
  if (!pre) return;
  const newText = pre.innerText;

  const originalText = "Kaydet";
  btn.textContent = "Kaydediliyor...";
  btn.disabled = true;

  fetch("http://localhost:8765/update_line", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ line_no: lineNo, new_text: newText })
  })
  .then(r => {
    if (r.ok) {
       btn.textContent = "Kaydedildi";
       setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 2000);
    } else {
       btn.textContent = "Hata";
       alert("Hata oluştu: " + r.statusText);
       btn.disabled = false;
    }
  })
  .catch(e => {
     console.error(e);
     btn.textContent = "Hata";
     alert("Bağlantı hatası: " + e);
     btn.disabled = false;
  });
}

function copyLine(ev, btn) {
    const item = btn.closest(".item");
    if (!item) return;
    const pre = item.querySelector("pre.arbox");
    if (!pre) return;
    const text = pre.innerText;
    navigator.clipboard.writeText(text).then(() => {
        const orig = "Kopyala";
        btn.textContent = "Kopyalandı";
        setTimeout(() => btn.textContent = orig, 1500);
    });
}

function renderListPane(pageObj, activeLineNo) {
  const pane = document.getElementById("listPane");
  if (!pane) return;
  if (!pageObj) {
    pane.innerHTML = `<div class="small muted">Satır listesi yok.</div>`;
    return;
  }

  // Quick hide button inside the right pane
  const hideBtnHtml = `<button class="listToggleBtn" onclick="toggleListPane()" title="Dizgiyi gizle">→</button>`;

  const searchHtml = `
    <div class="searchBar">
      ${hideBtnHtml}
      <div class="searchRow">
        <input id="srchInput" class="searchInput" placeholder="Dizgide ara (tüm sayfalar)…" value="${escapeHtml(SEARCH.q || "")}"
          onkeydown="if(event.key==='Enter'){doSearch();}"/>
        <button class="btn secondary small" onclick="doSearch()">Ara</button>
        <button class="btn secondary small" onclick="prevSearch()">↑</button>
        <button class="btn secondary small" onclick="nextSearch()">↓</button>
        <button class="btn secondary small" onclick="clearSearch()">Temizle</button>
        <span class="pill searchMeta">Eşleşme: <span id="srchCount">0/0</span></span>
      </div>
      <div class="small muted" style="margin-top:6px;">Not: Arama aktif nüsha dizgisi üzerinde çalışır ve tüm sayfalarda gezdirir.</div>
    </div>
  `;

  const lines = (pageObj.lines || []);
  pane.innerHTML = searchHtml + lines.map(it => {
    const best = it.best || {};
    const lm = it.line_marks || [];
    const ec = lm.length;
    const activeCls = (it.line_no === activeLineNo) ? " active" : "";
    const snippet = highlightTextArabic(best.raw || "", best.start_word ?? 0, lm);
    return `
      <div class="item${activeCls}" data-line="${it.line_no}" onclick="selectLine(${it.line_no})" ondblclick="openCompareDefault(${it.line_no});">
        <div style="display:flex;gap:6px;margin-bottom:4px;justify-content:flex-end;">
             <button class="btn xsmall secondary" onclick="event.stopPropagation();copyLine(event, this)">Kopyala</button>
             <button class="btn xsmall secondary" onclick="event.stopPropagation();saveLine(${it.line_no}, this)">Kaydet</button>
        </div>
        <pre class="arbox" style="margin-top:0;" contenteditable="true" onclick="event.stopPropagation();" onkeydown="event.stopPropagation();">${snippet}</pre>
      </div>
    `;
  }).join("");
  // Keep count label accurate after re-render
  setSearchLabel();
}

function renderAll() {
  // Persist state
  try {
    if (ACTIVE_PAGE_KEY) localStorage.setItem(keyActivePage, ACTIVE_PAGE_KEY);
    if (ACTIVE_LINE_NO !== null) localStorage.setItem(keyActiveLine, String(ACTIVE_LINE_NO));
    else localStorage.removeItem(keyActiveLine);
  } catch(e) {}

  const pageObj = _pageByKey(ACTIVE_PAGE_KEY);
  renderPagePane(pageObj, ACTIVE_LINE_NO);
  renderListPane(pageObj, ACTIVE_LINE_NO);
}

function _scrollActiveListItem(opts) {
  try {
    const o = (opts && typeof opts === "object") ? opts : {};
    const behavior = (o.behavior === "auto" || o.behavior === "smooth") ? o.behavior : "smooth";
    const pane = document.getElementById("listPane");
    if (!pane) return;
    try { if (document.body.classList.contains("hideList")) return; } catch(e) {}
    const active = pane.querySelector(".item.active");
    if (!active) return;

    // Align active item to the same vertical anchor as the manuscript bbox.
    // Use DOMRects (not offsetTop) so sticky search bar / layout quirks don't break alignment.
    const pr = pane.getBoundingClientRect();
    const r = active.getBoundingClientRect();
    const anchor = Math.max(SYNC_SCROLL_ANCHOR_MIN_PX, (pane.clientHeight || 0) * SYNC_SCROLL_ANCHOR_RATIO);
    const curTop = pane.scrollTop || 0;
    const target = Math.max(0, curTop + (r.top - pr.top) - anchor);
    pane.scrollTo({ top: target, behavior });
  } catch(e) {}
}

function selectLine(lineNo) {
  const opts = (arguments.length >= 2 && arguments[1] && typeof arguments[1] === "object") ? arguments[1] : {};
  
  // User click priority: Clear any pending TTS auto-resume/seek flags immediately.
  TTS_PENDING_SEEK_LINE = null;
  TTS_PENDING_AUTO_PLAY = null;

  const wasPlaying = _ttsIsPlaying();
  ACTIVE_LINE_NO = lineNo;
  const p = _findPageByLine(lineNo);
  
  // Detect context mismatch: if audio is loaded but the line isn't in its range (e.g. page changed without refresh), force a switch.
  const hasContentPre = (typeof ttsChunks !== "undefined" && ttsChunks && ttsChunks.length > 0) || 
                        (typeof ttsAudio !== "undefined" && ttsAudio && ttsAudio.src);
  const ranges = (typeof ttsPageRanges !== "undefined" && Array.isArray(ttsPageRanges)) ? ttsPageRanges : [];
  let contentMismatch = false;
  if (hasContentPre && ranges.length > 0 && !ranges.some(r => r.line_no === lineNo) && !opts.preserveTTS) {
       contentMismatch = true;
  }

  // Only stop TTS if page changed AND we are not explicitly preserving TTS state (e.g. nusha switch)
  if ((p && p.key !== ACTIVE_PAGE_KEY && !opts.preserveTTS) || contentMismatch) {
      // Page changed: Clear TTS state so we treat it as fresh load
      if (p) ACTIVE_PAGE_KEY = p.key;
      ttsStop(); 
  }
  // If preserving TTS, we still might need to update ACTIVE_PAGE_KEY if it mismatch, but WITHOUT stopping.
  if (p && p.key !== ACTIVE_PAGE_KEY && opts.preserveTTS) {
      ACTIVE_PAGE_KEY = p.key;
  }

  // If selection originates from clicking the manuscript page, ensure the text pane is visible.
  try {
    const forceShowList = !!opts.forceShowList;
    if (forceShowList && document.body.classList.contains("hideList")) {
      try { toggleListPane(); } catch(e) {}
    }
  } catch(e) {}

  renderAll();
  // After re-render, scroll the selected dizgi line into view (if the pane is visible).
  try {
    const behavior = (opts.scrollBehavior === "auto" || opts.scrollBehavior === "smooth") ? opts.scrollBehavior : "smooth";
    try { requestAnimationFrame(() => _scrollActiveListItem({ behavior })); } catch(e) { _scrollActiveListItem({ behavior }); }
    try { setTimeout(() => _scrollActiveListItem({ behavior: "auto" }), 0); } catch(e) {}
  } catch(e) {}
  // If the user changes selection while TTS is playing, follow the selected line.
  try {
    const fromTts = !!opts.fromTts;
    // Pass captured play state, but skip if preserveTTS is set
    if (!fromTts && !opts.preserveTTS) {
        _ttsFollowSelectedLine(lineNo, wasPlaying);
        
        // Auto-play on line click (only if content is ready/paused, ensuring "same page" context)
        const hasContent = (typeof ttsChunks !== "undefined" && ttsChunks && ttsChunks.length > 0) || 
                           (typeof ttsAudio !== "undefined" && ttsAudio && ttsAudio.src);
        
        if (hasContent && !_ttsIsPlaying()) {
            ttsToggle();
        }
    }
  } catch(e) {}
}

function nextPage() {
  if (!PAGES.length) return;
  const idx = PAGES.findIndex(p => p.key === ACTIVE_PAGE_KEY);
  const ni = (idx < 0) ? 0 : Math.min(PAGES.length-1, idx+1);
  ACTIVE_PAGE_KEY = PAGES[ni].key;
  ACTIVE_LINE_NO = null;
  renderAll();
}

function prevPage() {
  if (!PAGES.length) return;
  const idx = PAGES.findIndex(p => p.key === ACTIVE_PAGE_KEY);
  const pi = (idx <= 0) ? 0 : idx-1;
  ACTIVE_PAGE_KEY = PAGES[pi].key;
  ACTIVE_LINE_NO = null;
  renderAll();
}

// Backward-compat wrapper: older code paths call renderList(null) after spellcheck source switches.
function renderList(activeNo) {
  if (typeof activeNo === "number") {
    selectLine(activeNo);
    return;
  }
  ACTIVE_LINE_NO = null;
  renderAll();
}

function saveLocal() {
  try {
    localStorage.setItem(keyMap, JSON.stringify(mapping));
    alert("Kaydedildi.");
  } catch(e) {
    alert("Kaydedilemedi: " + e);
  }
}

function exportMapping() {
  const out = mapping.map(it => {
    return {
      line_no: it.line_no,
      line_image: it.line_image,
      ocr_text: it.ocr_text,
      best: it.best,
      error_count: (it.line_marks||[]).length
    };
  });
  const blob = new Blob([JSON.stringify(out, null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "alignment_export.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

function errorLineNos() {
  const out = [];
  const seen = new Set();
  for (const x of (mapping || [])) {
    if (!x || !x.line_marks || !x.line_marks.length) continue;
    const ln = x.line_no;
    if (typeof ln !== "number") continue;
    const k = String(ln);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(ln);
  }
  out.sort((a,b) => a-b);
  return out;
}

function currentActiveLine() {
  if (typeof ACTIVE_LINE_NO === "number") return ACTIVE_LINE_NO;
  const active = document.querySelector(".item.active");
  if (!active) return null;
  const ln = active.getAttribute("data-line") || "";
  const n = parseInt(String(ln), 10);
  return Number.isFinite(n) ? n : null;
}

function nextError() {
  const errs = errorLineNos();
  if (!errs.length) {
    alert("Hata bulunan satir yok.");
    return;
  }
  const cur = currentActiveLine();
  if (cur == null) {
    selectLine(errs[0]);
    return;
  }
  const idx = errs.findIndex(x => x > cur);
  if (idx >= 0) selectLine(errs[idx]);
  else selectLine(errs[0]);
}

function prevError() {
  const errs = errorLineNos();
  if (!errs.length) {
    alert("Hata bulunan satir yok.");
    return;
  }
  const cur = currentActiveLine();
  if (cur == null) {
    selectLine(errs[0]);
    return;
  }
  let prev = null;
  for (let i=0;i<errs.length;i++) {
    if (errs[i] < cur) prev = errs[i];
  }
  if (prev != null) selectLine(prev);
  else selectLine(errs[errs.length-1]);
}

loadFontSize();
loadPageZoom();
renderAll();
// Apply persisted split after initial render (elements exist now)
try { loadSplit(); _initSplitterDrag(); } catch(e) {}
try { loadListPaneState(); } catch(e) {}

// --- Header collapse (ArrowUp to toggle) ---
try {
  const keyHeader = "viewer_hide_header_v1";
  function updateHeaderToggleLabels() {
    const hidden = document.body.classList.contains("hideHeader");
    const b = document.getElementById("btnToggleHeader");
    const s = document.getElementById("btnShowHeader");
    if (b) b.textContent = hidden ? "▼" : "▲";
    if (s) s.textContent = hidden ? "▼ Menü" : "▲ Menü";
  }
  function applyHeaderState() {
    try {
      const v = localStorage.getItem(keyHeader);
      if (v === "1") document.body.classList.add("hideHeader");
      else document.body.classList.remove("hideHeader");
    } catch(e) {}
    updateHeaderToggleLabels();
  }
  function toggleHeader() {
    const nowHidden = !document.body.classList.contains("hideHeader");
    if (nowHidden) document.body.classList.add("hideHeader");
    else document.body.classList.remove("hideHeader");
    try { localStorage.setItem(keyHeader, nowHidden ? "1" : "0"); } catch(e) {}
    updateHeaderToggleLabels();
    // Layout changed; re-render to keep panes correct
    try { renderAll(); } catch(e) {}
  }
  // Make it available for inline onclick handlers
  window.toggleHeader = toggleHeader;
  applyHeaderState();
  window.addEventListener("keydown", (e) => {
    if (!e) return;
    // ArrowUp toggles header visibility. ArrowDown restores if hidden.
    if (e.key === "ArrowUp") {
      e.preventDefault();
      toggleHeader();
    } else if (e.key === "ArrowDown") {
      if (document.body.classList.contains("hideHeader")) {
        e.preventDefault();
        toggleHeader();
      }
    }
  });
} catch(e) {}

// --- Draggable floating nav (only via handle; clicks on buttons won't move it) ---
try {
  const nav = document.getElementById("floatNav");
  const handle = document.getElementById("floatNavHandle");
  const resizeHandle = document.getElementById("floatNavResize");
  const keyNavState = "viewer_floatNav_state_v2"; // {dock,left,top,width,height}
  if (nav && handle) {
    // Toggle "stack" mode for the top row when nav is narrow, so errpill can drop to next line.
    function updateNavStackMode() {
      try {
        const row = nav.querySelector(".navTopRow");
        if (!row) return;
        const r = nav.getBoundingClientRect();
        // When narrow, force break between buttons and errpill.
        if (r.width < 360) row.classList.add("stack");
        else row.classList.remove("stack");
      } catch(e) {}
    }

    try {
      // react to resizing (both window and manual resize of nav)
      const ro = new ResizeObserver(() => updateNavStackMode());
      ro.observe(nav);
      window.addEventListener("resize", () => updateNavStackMode());
    } catch(e) {
      // fallback: just call once
    }

    // restore saved position + size + dock side
    try {
      const raw = localStorage.getItem(keyNavState);
      if (raw) {
        const o = JSON.parse(raw);
        if (o && typeof o === "object") {
          const dock = (o.dock === "right") ? "right" : (o.dock === "left") ? "left" : null;
          nav.classList.remove("dockLeft", "dockRight");
          if (dock === "right") nav.classList.add("dockRight");
          if (dock === "left") nav.classList.add("dockLeft");

          if (typeof o.top === "number") nav.style.top = Math.max(0, o.top) + "px";
          if (!dock && typeof o.left === "number") nav.style.left = Math.max(0, o.left) + "px";
          if (dock) nav.style.left = ""; // handled by dock class
          if (typeof o.width === "number") nav.style.width = Math.max(240, o.width) + "px";
          if (typeof o.height === "number") nav.style.height = Math.max(54, o.height) + "px";
        }
      }
    } catch(e) {}
    // initial
    updateNavStackMode();

    let dragging = false;
    let dx = 0, dy = 0;
    let resizing = false;
    let rw0 = 0, rh0 = 0, rx0 = 0, ry0 = 0;

    function onMove(ev) {
      if (dragging) {
        const x = (ev.clientX - dx);
        const y = (ev.clientY - dy);
        nav.classList.remove("dockLeft", "dockRight");
        nav.style.left = Math.max(0, x) + "px";
        nav.style.top = Math.max(0, y) + "px";
        nav.style.right = "";
        return;
      }
      if (resizing) {
        const dx2 = ev.clientX - rx0;
        const dy2 = ev.clientY - ry0;
        const maxW = Math.min(window.innerWidth - 20, 980);
        const maxH = Math.min(window.innerHeight - 20, 620);
        const w = Math.max(240, Math.min(maxW, rw0 + dx2));
        const h = Math.max(54, Math.min(maxH, rh0 + dy2));
        nav.style.width = w + "px";
        nav.style.height = h + "px";
        updateNavStackMode();
      }
    }

    function onUp() {
      if (!dragging && !resizing) return;
      const wasDragging = dragging;
      dragging = false;
      resizing = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      // Snap to edges if close, to support "yaslanma" left/right.
      try {
        const r = nav.getBoundingClientRect();
        const snapPx = 44;
        nav.classList.remove("dockLeft", "dockRight");
        let dock = null;
        if (r.left <= snapPx) {
          nav.classList.add("dockLeft");
          nav.style.left = "";
          dock = "left";
        } else if ((window.innerWidth - r.right) <= snapPx) {
          nav.classList.add("dockRight");
          nav.style.left = "";
          dock = "right";
        }
        // Persist
        const left = r.left;
        const top = r.top;
        const width = r.width;
        const height = r.height;
        localStorage.setItem(keyNavState, JSON.stringify({ dock, left, top, width, height }));
      } catch(e) {}
      // If we resized, re-render so scroll offsets stay sane
      if (!wasDragging) {
        try { renderAll(); } catch(e) {}
      }
    }

    handle.addEventListener("mousedown", (ev) => {
      try { ev.preventDefault(); ev.stopPropagation(); } catch(e) {}
      const r = nav.getBoundingClientRect();
      dragging = true;
      dx = ev.clientX - r.left;
      dy = ev.clientY - r.top;
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    if (resizeHandle) {
      resizeHandle.addEventListener("mousedown", (ev) => {
        try { ev.preventDefault(); ev.stopPropagation(); } catch(e) {}
        const r = nav.getBoundingClientRect();
        resizing = true;
        rw0 = r.width;
        rh0 = r.height;
        rx0 = ev.clientX;
        ry0 = ev.clientY;
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      });
    }
  }
} catch(e) {}

// Keep Nüsha selector visible in the viewer so the user can switch between Nüsha 1/2/3 when available.

function closeCmpPop(e) {
  try {
    if (e && e.target && e.target.id !== "cmpPop") return;
  } catch(_e) {}
  const ov = document.getElementById("cmpPop");
  if (ov) ov.classList.remove("open");
}

function closeLinePop(e) {
  try {
    if (e && e.target && e.target.id !== "linePop") return;
  } catch(_e) {}
  const ov = document.getElementById("linePop");
  if (ov) ov.classList.remove("open");
}

function openLinePop(lineNo) {
  const it = (mapping || []).find(x => x && x.line_no === lineNo);
  if (!it) return;
  const body = document.getElementById("linePopBody");
  const titleEl = document.getElementById("linePopTitle");
  const ov = document.getElementById("linePop");
  if (!body || !ov) return;
  if (titleEl) titleEl.textContent = `Dizgi Satırı ${lineNo}`;

  const best = it.best || {};
  const lm = it.line_marks || [];
  const snippet = highlightTextArabic(best.raw || "", best.start_word ?? 0, lm);

  // Compare buttons (open the same compare popup you get from double-clicking a dizgi line)
  const cmpBtns = `
    <div class="row" style="gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px;">
      <span class="pill">Karşılık</span>
      ${(ACTIVE_NUSHA !== 1) ? `<button class="btn secondary small" onclick="openCompare(${lineNo}, 1)">Nüsha 1</button>` : ``}
      ${(HAS_N2 && ACTIVE_NUSHA !== 2) ? `<button class="btn secondary small" onclick="openCompare(${lineNo}, 2)">Nüsha 2</button>` : ``}
      ${(HAS_N3 && ACTIVE_NUSHA !== 3) ? `<button class="btn secondary small" onclick="openCompare(${lineNo}, 3)">Nüsha 3</button>` : ``}
      ${(HAS_N4 && ACTIVE_NUSHA !== 4) ? `<button class="btn secondary small" onclick="openCompare(${lineNo}, 4)">Nüsha 4</button>` : ``}
      <button class="btn secondary small" onclick="openCompareDefault(${lineNo})">Karşılaştır</button>
    </div>
  `;

  body.innerHTML = `
    ${cmpBtns}
    <div class="popBox">
      <div class="k">Dizgi</div>
      <div class="v">${snippet || "<span style='color:#666'>Boş.</span>"}</div>
    </div>
  `;

  // In this popup, clicking a highlighted word should open the suggestion/reason popup.
  try {
    body.onclick = (ev) => {
      const t = ev && ev.target ? ev.target : null;
      const span = t && t.closest ? t.closest("span.err") : null;
      if (!span) return;
      ev.preventDefault();
      ev.stopPropagation();
      openErrPopFromSpan(span);
    };
  } catch(e) {}
  ov.classList.add("open");
}

let CMP_LAST_LINE_NO = null;
let CMP_LAST_TARGET = null;

function openCompareDefault(lineNo) {
  // On double click, show "the other" nusha relative to the currently displayed one.
  // N1 -> prefer N2 then N3
  // N2 -> prefer N1 then N3
  // N3 -> prefer N1 then N2
  if (ACTIVE_NUSHA === 2) {
    openCompare(lineNo, 1);
    return;
  }
  if (ACTIVE_NUSHA === 3) {
    openCompare(lineNo, 1);
    return;
  }
  if (ACTIVE_NUSHA === 4) {
    openCompare(lineNo, 1);
    return;
  }
  // default ACTIVE_NUSHA === 1
  if (HAS_N2) return openCompare(lineNo, 2);
  if (HAS_N3) return openCompare(lineNo, 3);
  if (HAS_N4) return openCompare(lineNo, 4);
}

function switchCmp(targetNusha) {
  if (!CMP_LAST_LINE_NO) return;
  openCompare(CMP_LAST_LINE_NO, targetNusha);
}

function openCompare(lineNo, targetNusha) {
  const it = (mapping || []).find(x => x && x.line_no === lineNo);
  if (!it) return;

  const body = document.getElementById("cmpPopBody");
  if (!body) return;
  const titleEl = document.getElementById("cmpTitle");
  CMP_LAST_LINE_NO = lineNo;
  CMP_LAST_TARGET = parseInt(targetNusha, 10);
  // Show switch buttons in popup header:
  // - only for available nushas
  // - never show the currently displayed main nusha (ACTIVE_NUSHA)
  // - never show the currently selected compare target (CMP_LAST_TARGET)
  try {
    const b1 = document.getElementById("btnCmpN1");
    const b2 = document.getElementById("btnCmpN2");
    const b3 = document.getElementById("btnCmpN3");
    const b4 = document.getElementById("btnCmpN4");
    if (b1) b1.style.display = (ACTIVE_NUSHA !== 1 && CMP_LAST_TARGET !== 1) ? "inline-block" : "none";
    if (b2) b2.style.display = (HAS_N2 && ACTIVE_NUSHA !== 2 && CMP_LAST_TARGET !== 2) ? "inline-block" : "none";
    if (b3) b3.style.display = (HAS_N3 && ACTIVE_NUSHA !== 3 && CMP_LAST_TARGET !== 3) ? "inline-block" : "none";
    if (b4) b4.style.display = (HAS_N4 && ACTIVE_NUSHA !== 4 && CMP_LAST_TARGET !== 4) ? "inline-block" : "none";
  } catch(_e) {}

  function pickArr(obj, ocrField, listField, ptrField) {
    if (!obj || typeof obj !== "object") return [];
    const o = obj[ocrField];
    if (Array.isArray(o) && o.length) return o;
    const l = obj[listField];
    if (Array.isArray(l) && l.length) return l;
    const p = obj[ptrField];
    if (p && typeof p === "object" && p.line_image) return [p];
    return [];
  }

  // Determine which target to show
  const tgt = parseInt(targetNusha, 10);
  let title = "Karşılaştırma";
  let arr = [];
  let emptyNote = "Eşleşme bulunamadı.";

  if (ACTIVE_NUSHA === 1) {
    if (tgt === 2 && HAS_N2) {
      title = "Nüsha 2";
      arr = pickArr(it, "ocr_alt_list", "alt_list", "alt");
      const n2cnt = (typeof DATA.lines_count_alt === "number") ? DATA.lines_count_alt : (Array.isArray(altMapping) ? altMapping.length : 0);
      emptyNote = `Bu satır için Nüsha 2 eşleşmesi bulunamadı. (N2 satır sayısı: ${n2cnt})`;
    } else if (tgt === 3 && HAS_N3) {
      title = "Nüsha 3";
      arr = pickArr(it, "ocr_alt3_list", "alt3_list", "alt3");
      const n3cnt = (typeof DATA.lines_count_alt3 === "number") ? DATA.lines_count_alt3 : (Array.isArray(alt3Mapping) ? alt3Mapping.length : 0);
      emptyNote = `Bu satır için Nüsha 3 eşleşmesi bulunamadı. (N3 satır sayısı: ${n3cnt})`;
    } else if (tgt === 4 && HAS_N4) {
      title = "Nüsha 4";
      arr = pickArr(it, "ocr_alt4_list", "alt4_list", "alt4");
      const n4cnt = (typeof DATA.lines_count_alt4 === "number") ? DATA.lines_count_alt4 : (Array.isArray(alt4Mapping) ? alt4Mapping.length : 0);
      emptyNote = `Bu satır için Nüsha 4 eşleşmesi bulunamadı. (N4 satır sayısı: ${n4cnt})`;
    }
  } else if (ACTIVE_NUSHA === 2) {
    if (tgt === 1) {
      title = "Nüsha 1";
      arr = pickArr(it, "ocr_alt_list", "alt_list", "alt");
      emptyNote = "Bu satır için Nüsha 1 eşleşmesi bulunamadı.";
    } else if (tgt === 3 && HAS_N3) {
      title = "Nüsha 3";
      arr = pickArr(it, "ocr_alt3_list", "alt3_list", "alt3");
      const n3cnt = (typeof DATA.lines_count_alt3 === "number") ? DATA.lines_count_alt3 : (Array.isArray(alt3Mapping) ? alt3Mapping.length : 0);
      emptyNote = `Bu satır için Nüsha 3 eşleşmesi bulunamadı. (N3 satır sayısı: ${n3cnt})`;
    }
  } else if (ACTIVE_NUSHA === 3) {
    if (tgt === 1) {
      title = "Nüsha 1";
      arr = pickArr(it, "ocr_alt_list", "alt_list", "alt");
      emptyNote = "Bu satır için Nüsha 1 eşleşmesi bulunamadı.";
    } else if (tgt === 2 && HAS_N2) {
      title = "Nüsha 2";
      arr = pickArr(it, "ocr_alt2_list", "alt2_list", "alt2");
      const n2cnt = (typeof DATA.lines_count_alt === "number") ? DATA.lines_count_alt : (Array.isArray(altMapping) ? altMapping.length : 0);
      emptyNote = `Bu satır için Nüsha 2 eşleşmesi bulunamadı. (N2 satır sayısı: ${n2cnt})`;
    }
  }

  if (titleEl) titleEl.textContent = title;

  if (!arr || !arr.length) {
    body.innerHTML = `
      <div class="cmpCard">
        <div class="pill muted">${escapeHtml(title)}</div>
        <div class="small muted" style="margin-top:8px;">${escapeHtml(emptyNote)}</div>
        <div class="small muted" style="margin-top:8px;">Not: Daha sağlam eşleştirme için GUI'de <b>OCR↔OCR Eşleştir</b> kullanabilirsiniz.</div>
      </div>
    `;
  } else {
    body.innerHTML = `
      <div class="small muted" style="margin-bottom:10px;">Not: Daha sağlam eşleştirme için GUI'de <b>OCR↔OCR Eşleştir</b> kullanabilirsiniz.</div>
      ${arr.slice(0, 10).map((x, idx) => {
        const ln = x.line_no ? `Satır ${x.line_no}` : `Satır ?`;
        const ov = (x.overlap != null) ? ` • overlap=${x.overlap}` : "";
        return `<div class="cmpCard">
          <div class="row" style="justify-content:space-between;align-items:center;">
            <div class="pill muted">${escapeHtml(title)} • ${ln}${ov}</div>
            <div class="pill muted">Eşleşme ${idx+1}/${Math.min(10, arr.length)}</div>
          </div>
          ${x.line_image ? `<div style="margin-top:8px;"><img src="${imgSrc(x.line_image)}" loading="lazy"></div>` : ""}
          <div class="label">OCR</div>
          <pre class="arbox">${escapeHtml(x.ocr_text || '')}</pre>
        </div>`;
      }).join("")}
    `;
  }

  const ov = document.getElementById("cmpPop");
  if (ov) ov.classList.add("open");
}

function _setNushaLabel() {
  const el = document.getElementById("nushaLabel");
  if (!el) return;
  const n = (ACTIVE_NUSHA === 4 && HAS_N4) ? 4 : ((ACTIVE_NUSHA === 3 && HAS_N3) ? 3 : ((ACTIVE_NUSHA === 2 && HAS_N2) ? 2 : 1));
  el.textContent = `Görünen nüsha: ${n}`;
}
_setNushaLabel();
// Hide unavailable nusha buttons
try {
  const b2 = document.getElementById("btnN2");
  const b3 = document.getElementById("btnN3");
  const b4 = document.getElementById("btnN4");
  if (b2 && !HAS_N2) b2.style.display = "none";
  if (b3 && !HAS_N3) b3.style.display = "none";
  if (b4 && !HAS_N4) b4.style.display = "none";
} catch(e) {}

function setNusha(n) {
  // Preserve the currently selected line BEFORE we mutate mapping/PAGES or re-render anything.
  // Prefer a "token-midpoint" anchor (OCR -> dizgi tokens -> other nusha line) instead of OCR<->OCR matching.
  let keepLine = null;
  let keepTokMid = null; // global token index midpoint from best.start_word/end_word
  try {
    if (typeof ACTIVE_LINE_NO === "number") keepLine = ACTIVE_LINE_NO;
    else keepLine = currentActiveLine();
    if (typeof keepLine === "number") {
      const it0 = (mapping || []).find(x => x && typeof x.line_no === "number" && x.line_no === keepLine);
      const b0 = (it0 && it0.best && typeof it0.best === "object") ? it0.best : {};
      const s0 = (typeof b0.start_word === "number") ? b0.start_word : null;
      const e0 = (typeof b0.end_word === "number") ? b0.end_word : null;
      if (s0 != null && e0 != null && e0 > s0) {
        keepTokMid = ((s0 + e0) / 2);
      }
    }
  } catch(e) {}

  n = (n === 4 && HAS_N4) ? 4 : ((n === 3 && HAS_N3) ? 3 : ((n === 2 && HAS_N2) ? 2 : 1));
  ACTIVE_NUSHA = n;
  try { localStorage.setItem(keyActiveNusha, String(ACTIVE_NUSHA)); } catch(e) {}
  // Swap main mapping so left page pane shows the selected nusha
  mapping = (ACTIVE_NUSHA === 4) ? (Array.isArray(mappingAlt4) && mappingAlt4.length ? mappingAlt4 : mappingPrimary)
           : (ACTIVE_NUSHA === 3) ? (Array.isArray(mappingAlt3) && mappingAlt3.length ? mappingAlt3 : mappingPrimary)
           : (ACTIVE_NUSHA === 2) ? (Array.isArray(mappingAlt) && mappingAlt.length ? mappingAlt : mappingPrimary)
           : mappingPrimary;
  // Search is per-mapping; reset when switching nusha to avoid stale hits.
  // IMPORTANT: don't call clearSearch() here because it triggers renderAll() mid-switch (old PAGES vs new mapping).
  try { SEARCH.q = ""; SEARCH.qn = ""; SEARCH.hits = []; SEARCH.idx = -1; } catch(e) {}
  // Ensure highlights exist on the active mapping too
  try { _injectLineMarksFromPP(ACTIVE_PP_FOR_MARKS || [], mapping); } catch(e) {}
  
  // Swap audio cache for the new nusha
  if (typeof ALL_AUDIO_CACHES !== "undefined") {
      cachedAudio = ALL_AUDIO_CACHES[ACTIVE_NUSHA] || {};
  }
  // Rebuild page index for the new mapping
  try {
    PAGES = buildPagesIndex();
    // Prefer the page that contains the kept line; fallback to previous page key; then to first page.
    let desiredKey = null;
    try {
      if (typeof keepLine === "number") {
        const p = _findPageByLine(keepLine);
        if (p && p.key) desiredKey = p.key;
      }
    } catch(e) {}
    if (!desiredKey) {
      const curKey = ACTIVE_PAGE_KEY;
      if (curKey && PAGES.some(p => p && p.key === curKey)) desiredKey = curKey;
    }
    ACTIVE_PAGE_KEY = desiredKey || ((PAGES[0] && PAGES[0].key) ? PAGES[0].key : null);
  } catch(e) {}
  _setNushaLabel();
  _setCompareBtnLabels();
  // Re-select the "same place" in the new nusha.
  // Best effort:
  // 1) Use token midpoint (dizgi token space) to find the line in the new mapping that covers it.
  // 2) Fallback to same line_no (if present), else nearest line_no.
  try {
    let target = null;

    function _pickByTokenMid(mid) {
      if (!isFinite(mid)) return null;
      const m = mid;
      let bestLine = null;
      let bestDist = Infinity;
      for (const it of (mapping || [])) {
        if (!it || typeof it !== "object") continue;
        const ln = (typeof it.line_no === "number") ? it.line_no : null;
        if (ln == null) continue;
        const b = (it.best && typeof it.best === "object") ? it.best : {};
        const s = (typeof b.start_word === "number") ? b.start_word : null;
        const e = (typeof b.end_word === "number") ? b.end_word : null;
        if (s == null || e == null || e <= s) continue;
        if (m >= s && m < e) return ln; // exact cover
        const mm = (s + e) / 2;
        const d = Math.abs(mm - m);
        if (d < bestDist) { bestDist = d; bestLine = ln; }
      }
      return bestLine;
    }

    // 1) Token-midpoint mapping
    if (keepTokMid != null) {
      const ln = _pickByTokenMid(keepTokMid);
      if (typeof ln === "number") target = ln;
    }

    // 2) Fallback: same / nearest line_no
    if (target == null) {
      target = (typeof keepLine === "number") ? keepLine : null;
    }
    if (target != null) {
      const ok = (mapping || []).some(it => it && typeof it.line_no === "number" && it.line_no === target);
      if (!ok) {
        // Find nearest line_no in the new mapping
        const nums = (mapping || []).map(it => (it && typeof it.line_no === "number") ? it.line_no : null).filter(x => typeof x === "number");
        if (nums.length) {
          let best = nums[0], bestD = Math.abs(nums[0] - target);
          for (let i = 1; i < nums.length; i++) {
            const d = Math.abs(nums[i] - target);
            if (d < bestD) { bestD = d; best = nums[i]; }
          }
          target = best;
        }
      }
    }
    if (typeof target === "number") {
      selectLine(target, { scrollBehavior: "auto", preserveTTS: true });
      // Ensure search UI reflects reset state
      try { setSearchLabel(); } catch(e) {}
      try { const inp = document.getElementById("srchInput"); if (inp) inp.value = ""; } catch(e) {}
      return;
    }
  } catch(e) {}
  renderAll();
}

function closeAiReportPop(e) {
  try {
    if (e && e.target && e.target.id !== "aiReportPop") return;
  } catch(_e) {}
  const ov = document.getElementById("aiReportPop");
  if (ov) ov.classList.remove("open");
}

function gotoAiReportTarget(pidxStr, wrongRaw) {
  // Jump from AI report card -> corresponding highlighted word in the dizgi list (all pages).
  try {
    const pidx = parseInt(pidxStr, 10);
    const wn = normalizeArJS(String(wrongRaw || ""));
    let targetLine = null;

    // Prefer exact match by paragraph + wrong_norm in line_marks
    for (const it of (mapping || [])) {
      if (!it || typeof it !== "object") continue;
      const marks = Array.isArray(it.line_marks) ? it.line_marks : [];
      for (const m of marks) {
        if (!m || typeof m !== "object") continue;
        const mp = (typeof m.paragraph_index === "number") ? m.paragraph_index : parseInt(m.paragraph_index || "", 10);
        if (pidx && mp !== pidx) continue;
        const mw = normalizeArJS(String(m.wrong_norm || m.wrong || ""));
        if (wn && mw === wn) {
          targetLine = it.line_no;
          break;
        }
      }
      if (targetLine != null) break;
    }

    // Fallback: any line that has the same paragraph_index
    if (targetLine == null && pidx) {
      for (const it of (mapping || [])) {
        const marks = Array.isArray(it && it.line_marks) ? it.line_marks : [];
        if (marks.some(m => (m && (m.paragraph_index === pidx)))) {
          targetLine = it.line_no;
          break;
        }
      }
    }

    if (targetLine == null) return;

    try { closeAiReportPop(); } catch(e) {}
    selectLine(targetLine);

    // After render, scroll to the exact span if we can find it
    window.setTimeout(() => {
      try {
        const spans = Array.from(document.querySelectorAll("span.err[data-pidx][data-wrong]"));
        const cand = spans.find(el => {
          const ep = parseInt(el.getAttribute("data-pidx") || "", 10);
          if (pidx && ep !== pidx) return false;
          const ew = normalizeArJS(el.getAttribute("data-wrong") || "");
          return wn ? (ew === wn) : true;
        });
        if (cand) _scrollSpanIntoLeft(cand);
      } catch(e) {}
    }, 120);
  } catch(e) {}
}

function showAiErrorReport() {
  const body = document.getElementById("aiReportPopBody");
  if (!body) return;

  // Collect all errors from per_paragraph, grouped by model
  const byModel = {
    gemini: [],
    openai: [],
    claude: []
  };
  const allErrors = [];

  if (Array.isArray(spellPP)) {
    for (const p of spellPP) {
      if (!p || typeof p !== "object") continue;
      const pidx = p.paragraph_index;
      const errs = Array.isArray(p.errors) ? p.errors : [];
      for (const e of errs) {
        if (!e || typeof e !== "object") continue;
        const wrong = String(e.wrong || "");
        const suggestion = String(e.suggestion || "");
        const reason = String(e.reason || "");
        const srcs = Array.isArray(e.sources) ? e.sources : [];
        
        allErrors.push({
          paragraph_index: pidx,
          wrong,
          suggestion,
          reason,
          sources: srcs
        });

        // Group by model
        for (const src of srcs) {
          const s = String(src || "").toLowerCase();
          if (s.includes("gemini")) byModel.gemini.push({ paragraph_index: pidx, wrong, suggestion, reason, sources: srcs });
          if (s.includes("openai") || s.includes("gpt")) byModel.openai.push({ paragraph_index: pidx, wrong, suggestion, reason, sources: srcs });
          if (s.includes("claude")) byModel.claude.push({ paragraph_index: pidx, wrong, suggestion, reason, sources: srcs });
        }
      }
    }
  }

  if (allErrors.length === 0) {
    body.innerHTML = `<div class="popBox"><div class="small muted">AI hata raporu bulunamadı. Spellcheck çalıştırılmamış olabilir.</div></div>`;
    const ov = document.getElementById("aiReportPop");
    if (ov) ov.classList.add("open");
    return;
  }

  let html = `<div style="margin-bottom:16px;"><div class="pill">Toplam hata: ${allErrors.length}</div></div>`;

  // Model bazlı bölümler
  const models = [
    { key: "gemini", label: "Gemini", color: "#ffd9a8" },
    { key: "openai", label: "OpenAI (GPT)", color: "#c7d7ff" },
    { key: "claude", label: "Claude", color: "#d6c7ff" }
  ];

  for (const m of models) {
    const errs = byModel[m.key];
    if (errs.length === 0) continue;

    html += `<div class="popBox" style="margin-bottom:16px;">
      <div style="font-weight:900;font-size:1.1em;margin-bottom:12px;padding:8px;background:${m.color};border-radius:8px;">
        ${escapeHtml(m.label)}: ${errs.length} hata
      </div>`;

    for (const e of errs) {
      const srcsStr = Array.isArray(e.sources) ? e.sources.join(", ") : "";
      const pidx = e.paragraph_index || "";
      const wrong = e.wrong || "";
      html += `<div style="border:1px solid #eee;border-radius:8px;padding:10px;margin-bottom:10px;background:#fff;cursor:pointer;"
        onclick="gotoAiReportTarget('${escapeHtml(String(pidx))}','${escapeHtml(String(wrong))}')"
        title="Tıkla: dizgide ilgili yere git">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="pill"><b>Paragraf:</b> ${e.paragraph_index || "?"}</span>
          <span class="pill"><b>Kaynak:</b> ${escapeHtml(srcsStr || "?")}</span>
        </div>
        <div class="popBox" style="margin-bottom:6px;">
          <div class="k">Yanlış kelime:</div>
          <div class="v">${escapeHtml(e.wrong || "")}</div>
        </div>
        ${e.suggestion ? `<div class="popBox" style="margin-bottom:6px;">
          <div class="k">Öneri:</div>
          <div class="v">${escapeHtml(e.suggestion)}</div>
        </div>` : ""}
        ${e.reason ? `<div class="popBox">
          <div class="k">Açıklama:</div>
          <div class="v">${escapeHtml(e.reason)}</div>
        </div>` : ""}
      </div>`;
    }

    html += `</div>`;
  }

  // Tüm hatalar (model ayrımı olmadan, tekrarlar dahil)
  html += `<div class="popBox" style="margin-top:20px;">
    <div style="font-weight:900;font-size:1.1em;margin-bottom:12px;">Tüm Hatalar (${allErrors.length})</div>`;

  for (const e of allErrors) {
    const srcsStr = Array.isArray(e.sources) ? e.sources.join(", ") : "";
    const pidx = e.paragraph_index || "";
    const wrong = e.wrong || "";
    html += `<div style="border:1px solid #eee;border-radius:8px;padding:10px;margin-bottom:10px;background:#fff;cursor:pointer;"
      onclick="gotoAiReportTarget('${escapeHtml(String(pidx))}','${escapeHtml(String(wrong))}')"
      title="Tıkla: dizgide ilgili yere git">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
        <span class="pill"><b>Paragraf:</b> ${e.paragraph_index || "?"}</span>
        <span class="pill"><b>Model(ler):</b> ${escapeHtml(srcsStr || "?")}</span>
      </div>
      <div class="popBox" style="margin-bottom:6px;">
        <div class="k">Yanlış:</div>
        <div class="v">${escapeHtml(e.wrong || "")}</div>
      </div>
      ${e.suggestion ? `<div class="popBox" style="margin-bottom:6px;">
        <div class="k">Öneri:</div>
        <div class="v">${escapeHtml(e.suggestion)}</div>
      </div>` : ""}
      ${e.reason ? `<div class="popBox">
        <div class="k">Açıklama:</div>
        <div class="v">${escapeHtml(e.reason)}</div>
      </div>` : ""}
    </div>`;
  }

  html += `</div>`;

  body.innerHTML = html;
  const ov = document.getElementById("aiReportPop");
  if (ov) ov.classList.add("open");
}

function restoreArchiveForProcessing() {
  if (!archivePath) {
    alert("Arşiv yolu bulunamadı.");
    return;
  }
  const msg = `Bu arşivi output_lines/ klasörüne geri yüklemek için:\n\n` +
    `1. GUI'deki "Eski Sonuçlar (doc_archives)…" butonuna tıklayın\n` +
    `2. Arşiv listesinden bu arşivi seçin (isim: ${archivePath})\n` +
    `3. "Geri Yükle (output_lines/)" butonuna tıklayın\n\n` +
    `Arşiv yolu:\n${archivePath}\n\n` +
    `Geri yükleme işleminden sonra bu arşivin üzerine ekstra spellcheck veya ikinci nüsha ekleyebilirsiniz.`;
  alert(msg);
}

// Show "Tekrar İşlem Yap" button if viewing from archive
if (archivePath) {
  const btn = document.getElementById("restoreArchiveBtn");
  if (btn) btn.style.display = "inline-block";
  // Enable TTS button by default in archive mode
  _ttsBtnState(true, false);
}

function _availableNushaList() {
  const out = [1];
  if (HAS_N2) out.push(2);
  if (HAS_N3) out.push(3);
  if (HAS_N4) out.push(4);
  return out;
}

function cycleNusha(dir) {
  const avail = _availableNushaList();
  if (avail.length <= 1) return;
  const curIdx = Math.max(0, avail.indexOf(ACTIVE_NUSHA));
  const nextIdx = (curIdx + (dir < 0 ? -1 : 1) + avail.length) % avail.length;
  setNusha(avail[nextIdx]);
}

// --- Line Skip Visualization ---
const skipsN1vsN2 = DATA.skips_n1_vs_n2 || [];
const skipsN2vsN1 = DATA.skips_n2_vs_n1 || [];
const skipsN1vsN3 = DATA.skips_n1_vs_n3 || [];
const skipsN1vsN4 = DATA.skips_n1_vs_n4 || [];

let activeSkips = [];
let activeSkipIdx = -1;

function updateSkipBtnVisibility() {
  const b = document.getElementById("btnShowSkips");
  if (!b) return;
  // Determine relevant skips based on ACTIVE_NUSHA and active mapping
  let count = 0;
  if (ACTIVE_NUSHA === 1) {
      if (HAS_N2) count += skipsN1vsN2.length;
      if (HAS_N3) count += skipsN1vsN3.length;
      if (HAS_N4) count += skipsN1vsN4.length;
  } else if (ACTIVE_NUSHA === 2) {
      count += skipsN2vsN1.length;
  }
  // N3/N4 reverse skips not yet implemented in alignment.py, so we ignore them here
  
  if (count > 0) {
      b.style.display = "inline-block";
      b.textContent = `Olası Satır Atlaması (${count})`;
  } else {
      b.style.display = "none";
  }
  closeSkipNav(); // close panel when context changes
}

function initSkips() {
    activeSkips = [];
    activeSkipIdx = -1;
    
    // Aggregate relevant skips
    if (ACTIVE_NUSHA === 1) {
        if (HAS_N2) activeSkips = activeSkips.concat(skipsN1vsN2);
        if (HAS_N3) activeSkips = activeSkips.concat(skipsN1vsN3);
        if (HAS_N4) activeSkips = activeSkips.concat(skipsN1vsN4);
    } else if (ACTIVE_NUSHA === 2) {
        activeSkips = activeSkips.concat(skipsN2vsN1);
    }
    
    // Sort by line_no
    activeSkips.sort((a,b) => (a.line_no - b.line_no));
    
    if (activeSkips.length === 0) {
        alert("Şu anki görünümde olası satır atlaması tespit edilmedi.");
        return;
    }
    
    const panel = document.getElementById("skipNavContainer");
    const btn = document.getElementById("btnShowSkips");
    if (panel) panel.style.display = "flex";
    if (btn) btn.style.display = "none";
    
    showSkip(0);
}

function closeSkipNav() {
    const panel = document.getElementById("skipNavContainer");
    const btn = document.getElementById("btnShowSkips");
    if (panel) panel.style.display = "none";
    if (btn && btn.textContent !== "Olası Satır Atlaması (0)" && btn.textContent !== "") btn.style.display = "inline-block";
    
    // clear highlight
    try {
        document.querySelectorAll(".highlight-skip").forEach(el => el.classList.remove("highlight-skip"));
    } catch(e) {}
}

function showSkip(idx) {
    if (!activeSkips.length) return;
    idx = (idx + activeSkips.length) % activeSkips.length;
    activeSkipIdx = idx;
    const item = activeSkips[idx];
    
    const lbl = document.getElementById("skipCountLabel");
    if (lbl) lbl.textContent = `${idx + 1} / ${activeSkips.length}`;
    
    if (item && item.line_no) {
        // Go to line
        selectLine(item.line_no);
        
        // Highlight logic
        setTimeout(() => {
            // Find the list item
            // Logic differs if we are looking for N1 or N-alt items.
            // But selectLine simply scrolls to "mapping" item.
            // We assume "mapping" corresponds to the nusha where skip was found.
            // If the skip was "N1 vs N2", and we are viewing N1, item.line_no is checking N1 line.
            // Correct.
            
            // We need to find the DOM element for this line in listPane
            // Cards don't have IDs easily, so we query selectLine's active logic?
            // Actually selectLine sets .active class.
            const activeEl = document.querySelector("#listPane .item.active");
            if (activeEl) {
                activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
                activeEl.classList.add("highlight-skip");
                setTimeout(() => activeEl.classList.remove("highlight-skip"), 3000);
            }
        }, 150);
    }
}

function nextSkip() { showSkip(activeSkipIdx + 1); }
function prevSkip() { showSkip(activeSkipIdx - 1); }

// Update skip visibility initially and on nusha change
// Hook into _setNushaLabel or setNusha
const origSetNusha = setNusha;
setNusha = function(n) {
    origSetNusha(n);
    updateSkipBtnVisibility();
};
// Initial call
setTimeout(updateSkipBtnVisibility, 500);

// Keyboard: ← / → to switch displayed nusha (cycle across 1/2/3 if present).
window.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    cycleNusha(-1);
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    cycleNusha(1);
  }
});
</script>
</body>
</html>
"""
    html = html.replace("__DATA_JSON_PLACEHOLDER__", data_json)
    if out_dir:
        out_path = (out_dir / "viewer_dual.html") if dual else (
            (out_dir / "nusha3" / "viewer.html") if prefer_alt3 else (
                (out_dir / "nusha4" / "viewer.html") if prefer_alt4 else (
                    (out_dir / "nusha2" / "viewer.html") if prefer_alt else (out_dir / "viewer.html")
                )
            )
        )
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    else:
        out_path = VIEWER_DUAL_HTML if dual else (
            NUSHA3_VIEWER_HTML if prefer_alt3 else (
                NUSHA4_VIEWER_HTML if prefer_alt4 else (
                    NUSHA2_VIEWER_HTML if prefer_alt else VIEWER_HTML
                )
            )
        )
    out_path.write_text(html, encoding="utf-8")
