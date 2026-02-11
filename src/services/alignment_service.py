
import threading
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from src.config import ALIGNMENT_JSON
from src.utils import normalize_ar

# =============================================================================
# Highlighting Logic Ported from viewer.py
# =============================================================================

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

# =============================================================================
# Alignment Service Class
# =============================================================================

class AlignmentService:
    def __init__(self):
        self.lock = threading.Lock()

    def _load_data(self, file_path=None):
        try:
            target_path = file_path if file_path else ALIGNMENT_JSON
            if isinstance(target_path, str): target_path = Path(target_path)

            if not target_path.exists():
                return None, None

            with target_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                return data, data
            elif isinstance(data, dict) and "aligned" in data:
                return data["aligned"], data
            
            return None, None

        except Exception as e:
            print(f"Error loading data from {target_path}: {e}")
            return None, None

    def update_line(self, line_no, new_text, file_path=None):
        with self.lock:
            aligned_list, full_data = self._load_data(file_path)
            if aligned_list is None:
                return False

            found = False
            for item in aligned_list:
                if item.get("line_no") == line_no:
                    if "best" not in item:
                        item["best"] = {}
                    item["best"]["raw"] = new_text
                    found = True
                    break
            
            if not found:
                return False

            try:
                target_path = file_path if file_path else ALIGNMENT_JSON
                if isinstance(target_path, str): target_path = Path(target_path)
                
                with target_path.open("w", encoding="utf-8") as f:
                    json.dump(full_data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"Error saving data to {target_path}: {e}")
                return False

    def process_highlighting(self, alignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies highlighting logic to the alignment data.
        Expects 'spellcheck_per_paragraph' or 'spellcheck.per_paragraph' in the data.
        """
        # Checks if we have keys for different nushas and process them all
        # similar to viewer.py's multiple calls to _inject_line_marks
        
        # 1. Try to find the spellcheck data
        pp_data = alignment_data.get("spellcheck_per_paragraph")
        
        # 2. If valid, inject into all aligned lists found
        if pp_data and isinstance(pp_data, list):
            # Main alignment
            if "aligned" in alignment_data:
                _inject_line_marks(alignment_data, pp_data, aligned_override=alignment_data["aligned"])
            
            # Alt alignments (Nusha 2, 3, 4)
            for key in ["aligned_alt", "aligned_alt3", "aligned_alt4"]:
                if key in alignment_data and isinstance(alignment_data[key], list):
                    _inject_line_marks(alignment_data, pp_data, aligned_override=alignment_data[key])
                    
        return alignment_data

    def enrich_alignment_data(self, alignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriches alignment data for the frontend editor:
        1. Converts token-based line_marks into character-based 'highlights'.
        2. Resolves absolute file paths to /static/ URLs for images.
        """
        import re
        from pathlib import Path

        def _resolve_image_url(path_str: str) -> str:
            if not path_str:
                return ""
            # Assuming paths are like .../output_lines/lines/image.png
            # We want /static/lines/image.png or /static/nusha2/lines/image.png
            # This is a heuristic based on standard folder structure.
            p = Path(path_str)
            parts = p.parts
            
            # Find 'lines' and capture it and everything after
            try:
                idx = parts.index("lines")
                # Check if parent is a nusha folder
                if idx > 0 and parts[idx-1].startswith("nusha"):
                    return f"/static/{parts[idx-1]}/{'/'.join(parts[idx:])}"
                return f"/static/{'/'.join(parts[idx:])}"
            except ValueError:
                # Fallback: just return the filename in lines/
                return f"/static/lines/{p.name}"

        def _compute_highlights(text: str, start_word: int, line_marks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not text or not line_marks:
                return []
            
            # Map gidx -> error meta
            by_idx = {m["gidx"]: m for m in line_marks if "gidx" in m}
            if not by_idx:
                return []

            highlights = []
            # Split by whitespace, keeping delimiters to track accurate offsets
            # Regex group (\s+) captures separators
            tokens = re.split(r'(\s+)', text)
            
            char_idx = 0
            token_count = 0
            
            for part in tokens:
                if not part:
                    continue
                
                # Check if it's purely whitespace
                if part.strip() == "":
                    char_idx += len(part)
                    continue
                
                # It's a token
                current_gidx = start_word + token_count
                
                if current_gidx in by_idx:
                    meta = by_idx[current_gidx]
                    
                    # Determine color/type based on sources (simplified logic from viewer.js)
                    srcs = meta.get("sources", [])
                    color = "red" # default
                    if "gemini" in srcs and "openai" in srcs and "claude" in srcs:
                         color = "green" # all agree (err-all)
                    elif len(srcs) > 1:
                         color = "orange" # multiple agree
                    
                    highlights.append({
                        "start": char_idx,
                        "end": char_idx + len(part),
                        "type": "mismatch", # generic type
                        "color": color,
                        "metadata": {
                            "wrong": meta.get("wrong"),
                            "suggestion": meta.get("suggestion"),
                            "reason": meta.get("reason"),
                            "sources": srcs
                        }
                    })
                
                token_count += 1
                char_idx += len(part)
                
            return highlights

        # Process lists
        for list_key in ["aligned", "aligned_alt", "aligned_alt3", "aligned_alt4"]:
            if list_key not in alignment_data or not isinstance(alignment_data[list_key], list):
                continue
                
            for item in alignment_data[list_key]:
                if not isinstance(item, dict):
                    continue
                
                best = item.get("best", {})
                raw = best.get("raw", "")
                start_word = best.get("start_word", 0)
                line_marks = item.get("line_marks", [])
                
                # 1. Compute Highlights
                item["highlights"] = _compute_highlights(raw, start_word, line_marks)
                
                # 2. Resolve Image URL
                line_image = item.get("line_image", "")
                item["image_url"] = _resolve_image_url(line_image)

                # 3. Inject page_image for frontend sync
                # We need to link this line to a page.
                # line_image usually looks like: .../page_0001_01R_line_001.png
                # We want: page_0001_01R.png
                if line_image:
                    try:
                        p_name = Path(line_image).name
                        # Standard Kraken/Tahkik naming: {page}_line_{idx}.png
                        # Split by '_line_'
                        if "_line_" in p_name:
                             base_page = p_name.split("_line_")[0]
                             # Assume original was .png? Or matches get_pages glob.
                             # get_pages globs *.png.
                             # So we reconstruct filename.
                             item["page_image"] = base_page + ".png"
                             item["page_name"] = base_page
                    except Exception:
                        pass
        
        return alignment_data

    def update_line(self, line_no: int, new_text: str, file_path: Path) -> bool:
        """
        Updates the text content of a specific line in the alignment file.
        Searches across all alignment keys (aligned, aligned_alt, etc.)
        """
        try:
            if not file_path.exists():
                return False

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = False
            # Check all possible keys
            keys = ["aligned", "aligned_alt", "aligned_alt3", "aligned_alt4"]
            
            for key in keys:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        # Check type and line_no
                        if isinstance(item, dict) and item.get("line_no") == line_no:
                            # Update the text
                            if "best" not in item:
                                item["best"] = {}
                            item["best"]["raw"] = new_text
                            # Also update legacy/flat text field if present
                            if "text" in item:
                                item["text"] = new_text
                                
                            updated = True
                            break
                if updated:
                    break
            
            if updated:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                return True
                
            return False

        except Exception as e:
            print(f"Error updating line: {e}")
            return False
