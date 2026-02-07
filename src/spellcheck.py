# -*- coding: utf-8 -*-
"""
Spellcheck helpers and API integrations (Gemini + OpenAI + Claude)
"""

import json
import re
import requests
import time
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable, Set
from src.config import (
    GEMINI_PROVIDER,
    SPELLCHECK_GEMINI_MODEL,
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    VERTEX_GEMINI_MODEL,
    OPENAI_MODEL,
    CLAUDE_MODEL,
    SPELLCHECK_MAX_PARAS,
    SPELLCHECK_SAVE_JSON,
    SPELLCHECK_JSON,
    SPELLCHECK_BACKUPS_DIR,
)
from src.keys import get_gemini_api_key, get_google_access_token, get_openai_api_key, get_claude_api_key
from src.utils import normalize_ar
from src.document import read_docx_paragraphs


# =========================
# Spellcheck helpers
# =========================
def _extract_json_from_text(text: str) -> Optional[Any]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
    if not m:
        return None
    chunk = m.group(0)
    try:
        return json.loads(chunk)
    except Exception:
        return None

def _normalize_error_word(w: str) -> str:
    return normalize_ar(w or "")

def _extract_items_from_tsv(text: str) -> List[Dict[str, str]]:
    """
    Parse plain-text spellcheck output:
      WRONG<TAB>SUGGESTION<TAB>REASON
    One item per line. Robust to numbering/bullets and a few common separators.
    """
    if not text:
        return []
    out: List[Dict[str, str]] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # strip common bullets/numbering prefixes
        line = re.sub(r"^\s*[\-\*\u2022]+\s*", "", line)
        line = re.sub(r"^\s*\(?\d+\)?[\).\-\:]\s*", "", line)

        wrong = sug = reason = ""

        # Prefer TSV
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
            wrong = parts[0].strip() if len(parts) >= 1 else ""
            sug = parts[1].strip() if len(parts) >= 2 else ""
            reason = " ".join([p.strip() for p in parts[2:]]).strip() if len(parts) >= 3 else ""
        else:
            # Fallback separators: "wrong -> sug | reason" or "wrong | sug | reason"
            if "->" in line:
                a, b = line.split("->", 1)
                wrong = a.strip()
                rest = b.strip()
                if "|" in rest:
                    s, r = rest.split("|", 1)
                    sug = s.strip()
                    reason = r.strip()
                else:
                    sug = rest
            elif "|" in line:
                parts = [p.strip() for p in line.split("|")]
                wrong = parts[0].strip() if len(parts) >= 1 else ""
                sug = parts[1].strip() if len(parts) >= 2 else ""
                reason = " ".join(parts[2:]).strip() if len(parts) >= 3 else ""

        wrong = (wrong or "").strip()
        sug = (sug or "").strip()
        reason = (reason or "").strip()
        if not wrong:
            continue
        # Skip header-ish lines
        if wrong.lower() in ("wrong", "hatalı", "hata", "error"):
            continue
        out.append({"wrong": wrong, "suggestion": sug, "reason": reason})
    return out

def _merge_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mp: Dict[str, Dict[str, Any]] = {}
    for e in errors:
        wrong = (e.get("wrong") or "").strip()
        if not wrong:
            continue
        nw = _normalize_error_word(wrong)
        if not nw:
            continue
        # Kaynaklar:
        # - Ham model çıktısı: {"source": "gemini"/"openai"/"claude"}
        # - Önceden merge edilmiş kayıtlar: {"sources": ["openai", ...]}
        srcs: List[str] = []
        src = (e.get("source") or "").strip()
        if src:
            srcs.append(src)
        sources = e.get("sources")
        if isinstance(sources, str) and sources.strip():
            srcs.append(sources.strip())
        elif isinstance(sources, list):
            for s in sources:
                if isinstance(s, str) and s.strip():
                    srcs.append(s.strip())
        # uniq + stable sort
        srcs = sorted(set([s for s in srcs if s]))
        if nw not in mp:
            mp[nw] = {
                "wrong": wrong,
                "wrong_norm": nw,
                "suggestion": (e.get("suggestion") or "").strip(),
                "reason": (e.get("reason") or "").strip(),
                "sources": srcs,
            }
        else:
            if not mp[nw].get("suggestion") and (e.get("suggestion") or "").strip():
                mp[nw]["suggestion"] = (e.get("suggestion") or "").strip()
            if not mp[nw].get("reason") and (e.get("reason") or "").strip():
                mp[nw]["reason"] = (e.get("reason") or "").strip()
            for s in srcs:
                if s and s not in mp[nw]["sources"]:
                    mp[nw]["sources"].append(s)
            mp[nw]["sources"].sort()
    return list(mp.values())


_AR_STOPWORDS = {
    "من", "الى", "إلى", "على", "عن", "في", "ب", "و", "ف", "ثم", "او", "أو", "أن", "ان",
    "هذا", "هذه", "ذلك", "تلك", "هو", "هي", "هم", "هن", "كما", "لكن", "بل", "قد", "لم", "لن",
    "ما", "لا", "ولا", "إلا", "الا", "كل", "بعض", "أي", "اي", "أين", "اين", "اذا", "إذ", "اذ",
}


def _filter_suspicious_errors(
    merged_errors: List[Dict[str, Any]],
    token_counts: Counter,
    total_tokens: int,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Özellikle Claude kaynaklı (tek başına) çok sık geçen/çok kısa kelimeleri
    yanlış-pozitif olup tüm metni boyamasın diye filtreler.
    """
    if not merged_errors:
        return merged_errors

    # Çok sık geçen token eşiği: mutlak veya oransal
    freq_abs = 25
    freq_rel = int(max(20, total_tokens * 0.015))  # ~%1.5
    freq_thresh = max(freq_abs, freq_rel)

    filtered: List[Dict[str, Any]] = []
    dropped = 0
    for e in merged_errors:
        wn = (e.get("wrong_norm") or _normalize_error_word(e.get("wrong", ""))).strip()
        if not wn:
            continue
        sources = e.get("sources") or []
        if isinstance(sources, str):
            sources = [sources]
        sources = [s for s in sources if isinstance(s, str)]

        suggestion = (e.get("suggestion") or "").strip()
        reason = (e.get("reason") or "").strip()

        # Çok kısa (1-2 harf) şeyleri genelde at (özellikle Claude-only)
        if len(wn) <= 2 and sources == ["claude"]:
            dropped += 1
            continue

        # Stopword'ler Claude-only ise at (çok sık yanlış-pozitif)
        if wn in {normalize_ar(x) for x in _AR_STOPWORDS} and sources == ["claude"]:
            dropped += 1
            continue

        # Metinde aşırı sık geçen kelime Claude-only ise ve sağlam gerekçe yoksa at
        cnt = int(token_counts.get(wn, 0))
        if cnt >= freq_thresh and sources == ["claude"]:
            # Eğer güçlü bir düzeltme önerisi yoksa / aynıysa / açıklama yoksa filtrele
            sn = _normalize_error_word(suggestion)
            if (not suggestion) or (sn == wn) or (not reason):
                dropped += 1
                continue

        filtered.append(e)

    if dropped and status_callback:
        status_callback(
            f"UYARI: Opus(Claude) kaynaklı {dropped} şüpheli/çok sık geçen hata filtreden geçti (toplu vurgulama engellendi).",
            "WARNING",
        )
    return filtered


_AR_DIAC = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")

def _strip_diacritics_keep_letters(s: str) -> str:
    """Remove Arabic diacritics/harakat/tatweel but keep letters for comparison."""
    if not s:
        return ""
    s = s.replace("ـ", "")
    s = _AR_DIAC.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

_NON_ORTHO_KWS = [
    # Turkish
    "hareke", "irab", "i'rab", "tenvin", "şedde", "sedde", "cezim", "cazm", "jazm", "nasb", "nصب",
    # Arabic
    "إعراب", "اعراب", "إعرابي", "اعرابي", "حركة", "حركات", "تشكيل", "ضبط", "تنوين", "شدّة", "شدة",
    "سكون", "جزم", "نصب",
    # English
    "diacritic", "diacritics", "harakat", "tanwin", "shadda", "sukun", "case ending", "i'rab",
]

def _is_non_orthographic_suggestion(wrong: str, suggestion: str, reason: str) -> bool:
    """
    Returns True if the suggestion is about harakat/i'rab/tanwin/shadda/sukun/jazm/nasb,
    or generally not an orthography/letter-level correction.
    """
    w = (wrong or "").strip()
    s = (suggestion or "").strip()
    r = (reason or "").strip()

    # Many models sometimes output "no error" items — drop them
    r_low = r.lower()
    if "لا خطأ" in r or "لا يوجد خطأ" in r or "الكلمة صحيحة" in r or "no error" in r_low:
        return True

    # Keyword-based: if it's explicitly about diacritics/case endings, drop
    blob = f"{w}\n{s}\n{r}".lower()
    for kw in _NON_ORTHO_KWS:
        if kw.lower() in blob:
            return True

    # If suggestion differs only by diacritics (including shadda/tanwin/sukun), drop
    if w and s and _strip_diacritics_keep_letters(w) == _strip_diacritics_keep_letters(s) and w != s:
        return True

    # Tanwin-alif / nasb-style endings: treat as non-orthographic per user request
    # If the only difference is a terminal alif (ا) (often used with tanwin fath), drop.
    ww = _strip_diacritics_keep_letters(w)
    ss = _strip_diacritics_keep_letters(s)
    if ww and ss and ww != ss:
        if (ww.endswith("ا") and ww[:-1] == ss) or (ss.endswith("ا") and ss[:-1] == ww):
            return True

    return False

def _filter_non_orthographic_errors(
    errors: List[Dict[str, Any]],
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Drop errors that are only about harakat/i'rab/tanwin/shadda/sukun/jazm/nasb, etc."""
    if not errors:
        return errors
    out: List[Dict[str, Any]] = []
    dropped = 0
    for e in errors:
        if not isinstance(e, dict):
            continue
        w = (e.get("wrong") or "").strip()
        s = (e.get("suggestion") or "").strip()
        r = (e.get("reason") or "").strip()
        if _is_non_orthographic_suggestion(w, s, r):
            dropped += 1
            continue
        out.append(e)
    if dropped and status_callback:
        status_callback(
            f"Filtre: {dropped} kayıt haraka/irab/tenvin/şedde/cezim/nasb vb. olduğu için kaldırıldı.",
            "INFO",
        )
    return out


def _load_existing_spellcheck_json() -> Optional[Dict[str, Any]]:
    try:
        if not SPELLCHECK_JSON.exists():
            return None
        obj = json.loads(SPELLCHECK_JSON.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _merge_spellcheck_payloads(
    existing: Dict[str, Any],
    delta: Dict[str, Any],
    docx_path: Path,
    paras: List[str],
    token_counts: Counter,
    total_tokens: int,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Merge newly computed spellcheck payload (delta) into an existing spellcheck.json.
    Keeps existing results and adds new ones (union by wrong_norm, union sources).
    """
    ex_docx = (existing.get("docx_path") or "").strip()
    if ex_docx:
        try:
            if Path(ex_docx).resolve() != Path(docx_path).resolve():
                raise RuntimeError(
                    f"Mevcut spellcheck.json farklı bir Word dosyasına ait.\n"
                    f"Mevcut: {ex_docx}\nYeni: {str(docx_path)}"
                )
        except Exception as e:
            raise RuntimeError(str(e))

    # Index existing per_paragraph by paragraph_index
    ex_pp = existing.get("per_paragraph") or []
    ex_map: Dict[int, Dict[str, Any]] = {}
    if isinstance(ex_pp, list):
        for blk in ex_pp:
            if not isinstance(blk, dict):
                continue
            pidx = blk.get("paragraph_index")
            if isinstance(pidx, int):
                ex_map[pidx] = blk

    # Index delta per_paragraph by paragraph_index
    d_pp = delta.get("per_paragraph") or []
    d_map: Dict[int, Dict[str, Any]] = {}
    if isinstance(d_pp, list):
        for blk in d_pp:
            if not isinstance(blk, dict):
                continue
            pidx = blk.get("paragraph_index")
            if isinstance(pidx, int):
                d_map[pidx] = blk

    merged_pp: List[Dict[str, Any]] = []
    all_errors: List[Dict[str, Any]] = []

    for i, p in enumerate(paras):
        pidx = i + 1
        old_errs = (ex_map.get(pidx, {}) or {}).get("errors") or []
        new_errs = (d_map.get(pidx, {}) or {}).get("errors") or []
        if not isinstance(old_errs, list):
            old_errs = []
        if not isinstance(new_errs, list):
            new_errs = []

        merged = _merge_errors(old_errs + new_errs)
        merged = _filter_non_orthographic_errors(merged, status_callback=status_callback)
        merged = _filter_suspicious_errors(merged, token_counts, total_tokens, status_callback=status_callback)
        for e in merged:
            e["paragraph_index"] = pidx

        merged_pp.append({"paragraph_index": pidx, "text": p, "errors": merged})
        all_errors.extend(merged)

    merged_global = _merge_errors(all_errors)
    merged_global = _filter_non_orthographic_errors(merged_global, status_callback=status_callback)
    merged_global = _filter_suspicious_errors(merged_global, token_counts, total_tokens, status_callback=status_callback)

    # Merge call_errors (append)
    merged_call_errors: List[Dict[str, Any]] = []
    ce1 = existing.get("call_errors") or []
    ce2 = delta.get("call_errors") or []
    if isinstance(ce1, list):
        merged_call_errors.extend([x for x in ce1 if isinstance(x, dict)])
    if isinstance(ce2, list):
        merged_call_errors.extend([x for x in ce2 if isinstance(x, dict)])

    # Merge runs metadata (append)
    merged_runs: List[Dict[str, Any]] = []
    r1 = existing.get("runs") or []
    r2 = delta.get("runs") or []
    if isinstance(r1, list):
        merged_runs.extend([x for x in r1 if isinstance(x, dict)])
    if isinstance(r2, list):
        merged_runs.extend([x for x in r2 if isinstance(x, dict)])

    out = dict(existing)
    out["docx_path"] = str(docx_path)
    out["paragraphs_count"] = len(paras)
    if delta.get("start_paragraph") is not None:
        out["start_paragraph"] = delta.get("start_paragraph")
    if delta.get("selected_paragraphs") is not None:
        out["selected_paragraphs"] = delta.get("selected_paragraphs")
    if delta.get("gemini_model"):
        out["gemini_model"] = delta.get("gemini_model")
    if delta.get("openai_model"):
        out["openai_model"] = delta.get("openai_model")
    if delta.get("claude_model"):
        out["claude_model"] = delta.get("claude_model")

    out["per_paragraph"] = merged_pp
    out["errors_merged"] = merged_global
    out["call_errors"] = merged_call_errors
    out["runs"] = merged_runs
    return out


def _backup_spellcheck_json(payload: Dict[str, Any], status_callback: Optional[Callable[[str, str], None]] = None) -> None:
    """
    Save a timestamped backup copy of the *previous* spellcheck.json (if exists) and the *new* payload.
    Backups live under output_lines/spellcheck_backups/.
    """
    try:
        SPELLCHECK_BACKUPS_DIR.mkdir(exist_ok=True)
    except Exception:
        pass

    ts = time.strftime("%Y%m%d_%H%M%S")

    def _safe_stem(s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[^\w\u0600-\u06FF]+", "_", s, flags=re.UNICODE)
        s = s.strip("_")
        return s[:60] if s else "doc"

    docx_path = (payload.get("docx_path") or "").strip()
    stem = _safe_stem(Path(docx_path).stem if docx_path else "doc")

    # 1) Backup existing current file (if any)
    try:
        if SPELLCHECK_JSON.exists():
            prev = SPELLCHECK_JSON.read_text(encoding="utf-8")
            prev_path = SPELLCHECK_BACKUPS_DIR / f"{ts}__{stem}__prev.json"
            prev_path.write_text(prev, encoding="utf-8")
    except Exception as e:
        if status_callback:
            status_callback(f"SPELLCHECK: Önceki spellcheck.json yedeklenemedi: {e}", "WARNING")

    # 2) Backup new payload
    try:
        new_path = SPELLCHECK_BACKUPS_DIR / f"{ts}__{stem}__new.json"
        new_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if status_callback:
            status_callback(f"SPELLCHECK: Yedek kaydedildi: {new_path.name}", "INFO")
    except Exception as e:
        if status_callback:
            status_callback(f"SPELLCHECK: Yeni sonuç yedeklenemedi: {e}", "WARNING")

    # 3) Best-effort retention: keep last 50 newest
    try:
        files = sorted([p for p in SPELLCHECK_BACKUPS_DIR.glob("*.json") if p.is_file()], key=lambda p: p.name)
        if len(files) > 50:
            for p in files[:-50]:
                try:
                    p.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def _looks_like_quota_or_rate_limit(err: str) -> bool:
    e = (err or "").lower()
    if not e:
        return False
    return (
        ("http 429" in e)
        or ("status_code\": 429" in e)
        or ("status code 429" in e)
        or ("insufficient_quota" in e)
        or ("exceeded your current quota" in e)
        or ("rate limit" in e)
        or ("rate-limit" in e)
        or ("billing" in e)
        or ("quota" in e)
    )


def _gemini_prompt(paragraph: str) -> str:
    # IMPORTANT: output should be plain text (no JSON). One error per line:
    # WRONG<TAB>SUGGESTION<TAB>REASON
    return (
        "أنت مدقق إملائي عربي شديد الدقة لنص محقق.\n"
        "أخرج فقط نصًا عاديًا (بدون JSON وبدون Markdown).\n"
        "سطر لكل خطأ بالشكل التالي تمامًا:\n"
        "WRONG\\tSUGGESTION\\tREASON\n"
        "قواعد:\n"
        "- لا تقترح أي تصحيح للحركات/التشكيل/الإعراب/التنوين/الشدة/السكون/الجزم/النصب.\n"
        "- تجاهل الحركات والإعراب تمامًا (لا تعتبرها أخطاء).\n"
        "- إذا كان الفرق فقط في التشكيل أو علامات الإعراب أو (ألف التنوين في آخر الكلمة) فلا تذكره.\n"
        "- ركّز فقط على أخطاء الرسم/الإملاء/الحروف.\n"
        "- لا تذكر أكثر من 30 خطأ.\n"
        "- إذا لا توجد أخطاء، أخرج سطرًا واحدًا فقط: NONE\n"
        "النص:\n"
        f"{paragraph}\n"
    )


# =========================
# Gemini Spellcheck (AI Studio - Generative Language API)
# =========================
def gemini_spellcheck_paragraph(
    paragraph: str,
    api_key: str,
    model: str,
    paragraph_index: Optional[int] = None,
    debug_callback: Optional[Callable[[str, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    paragraph = (paragraph or "").strip()
    if not paragraph:
        return [], None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    prompt = _gemini_prompt(paragraph)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    }

    # Rate limit / transient hata için retry + backoff
    retries = 2
    backoff_base = 1.8
    last_err: Optional[str] = None

    try:
        for attempt in range(retries):
            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                p = prompt or ""
                debug_callback(
                    f"AI İSTEK (Gemini) {tag} deneme {attempt+1}/{retries} PROMPT:\n{p}",
                    "INFO",
                )
            r = requests.post(url, headers=headers, json=payload, timeout=(20, 240))
            if r.status_code == 200:
                # Even with HTTP 200, model output can be malformed.
                # Treat parse failures as retryable, and include attempt counters in the error.
                try:
                    data = r.json()
                except Exception as e:
                    last_err = f"Gemini: JSON decode hatası (deneme {attempt+1}/{retries}): {e}"
                    time.sleep(1.0)
                    continue

                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    debug_callback(
                        f"AI CEVAP (Gemini) {tag} deneme {attempt+1}/{retries} RAW:\n{(r.text or '')[:8000]}",
                        "INFO",
                    )

                text_out = ""
                cands = data.get("candidates", [])
                if cands and isinstance(cands, list):
                    content = cands[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and isinstance(parts, list):
                        text_out = "".join([(p.get("text") or "") for p in parts])

                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    snippet = (text_out or "").replace("\n", "\\n")
                    debug_callback(f"AI ÇIKTI (Gemini) {tag}: {snippet[:600]}", "INFO")

                if (text_out or "").strip().upper() == "NONE":
                    return [], None

                # Parse TSV text output
                items = _extract_items_from_tsv(text_out)

                # Backward compat: if model still returns JSON, try to parse it
                if not items:
                    obj = _extract_json_from_text(text_out)
                    if isinstance(obj, list):
                        for it in obj:
                            if not isinstance(it, dict):
                                continue
                            items.append({
                                "wrong": it.get("wrong", "") or it.get("error", "") or "",
                                "suggestion": it.get("suggestion", "") or it.get("fix", "") or "",
                                "reason": it.get("reason", "") or it.get("note", "") or "",
                            })

                if not items:
                    last_err = (
                        f"Gemini: çıktı parse edilemedi (deneme {attempt+1}/{retries}). "
                        f"Beklenen: WRONG<TAB>SUGGESTION<TAB>REASON. "
                        f"Text: {(text_out or '')[:120]}..."
                    )
                    if debug_callback is not None:
                        tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                        debug_callback(
                            f"Gemini parse retry {tag}: deneme {attempt+1}/{retries} (çıktı parse edilemedi)",
                            "WARNING",
                        )
                    time.sleep(1.0)
                    continue

                out = []
                for it in items:
                    out.append({
                        "wrong": it.get("wrong", "") or "",
                        "suggestion": it.get("suggestion", "") or "",
                        "reason": it.get("reason", "") or "",
                        "source": "gemini",
                    })
                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    prev = [f"{x.get('wrong','')}→{x.get('suggestion','')}" for x in out[:6]]
                    debug_callback(
                        f"AI PARSE (Gemini) {tag}: {len(out)} hata. İlkler: {', '.join(prev)}",
                        "INFO",
                    )
                return out, None

            # 429/5xx -> retry
            if r.status_code in (429, 500, 502, 503, 504):
                # Quota exhausted: don't bother retrying (instant feedback)
                if r.status_code == 429:
                    body_l = (r.text or "").lower()
                    if ("exceeded your current quota" in body_l) or ("billing" in body_l) or ("rate-limits" in body_l):
                        if debug_callback is not None:
                            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                            debug_callback(
                                f"AI CEVAP (Gemini) {tag} HTTP 429 (quota) RAW:\n{(r.text or '')[:8000]}",
                                "ERROR",
                            )
                        return [], f"Gemini HTTP 429 (quota): {r.text[:500]}"
                last_err = f"Gemini HTTP {r.status_code}: {r.text[:300]}"
                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    debug_callback(
                        f"AI CEVAP (Gemini) {tag} HTTP {r.status_code} RAW:\n{(r.text or '')[:8000]}",
                        "WARNING",
                    )
                ra = r.headers.get("Retry-After")
                if ra:
                    try:
                        sleep_s = float(ra)
                    except Exception:
                        sleep_s = backoff_base ** attempt
                else:
                    sleep_s = backoff_base ** attempt
                time.sleep(min(30.0, sleep_s))
                continue

            return [], f"Gemini HTTP {r.status_code}: {r.text[:500]}"

        return [], (last_err or f"Gemini: işlem başarısız oldu (max retries: {retries}).")
    except Exception as e:
        return [], f"Gemini exception: {e}"


# =========================
# Gemini Spellcheck (Vertex AI - Gemini for Google Cloud API)
# =========================
def vertex_gemini_spellcheck_paragraph(
    paragraph: str,
    project_id: str,
    location: str,
    model: str,
    paragraph_index: Optional[int] = None,
    debug_callback: Optional[Callable[[str, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    paragraph = (paragraph or "").strip()
    if not paragraph:
        return [], None
    if not project_id:
        return [], "Vertex: VERTEX_PROJECT_ID boş. Env: VERTEX_PROJECT_ID ayarla."
    if not location:
        return [], "Vertex: VERTEX_LOCATION boş. Env: VERTEX_LOCATION ayarla."
    if not model:
        return [], "Vertex: VERTEX_GEMINI_MODEL boş. Env: VERTEX_GEMINI_MODEL ayarla."

    # Normalize common location typos (user env mistakes)
    loc = (location or "").strip()
    if loc == "us-centrall":
        loc = "us-central1"

    # Vertex endpoint (v1)
    # NOTE: some publisher models may be available under location "global".
    # For "global", the host is aiplatform.googleapis.com (no region prefix).
    host = "https://aiplatform.googleapis.com" if loc == "global" else f"https://{loc}-aiplatform.googleapis.com"
    url = (
        f"{host}/v1/projects/{project_id}"
        f"/locations/{loc}/publishers/google/models/{model}:generateContent"
    )
    
    # Retry settings
    retries = 4
    backoff_base = 1.8
    last_err: Optional[str] = None

    for attempt in range(retries):
        try:
            try:
                tok = get_google_access_token()
            except Exception as e:
                return [], f"Vertex auth error: {e}"
            
            headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
            prompt = _gemini_prompt(paragraph)
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
            }

            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                debug_callback(
                    f"AI İSTEK (Vertex Gemini) {tag} deneme {attempt+1}/{retries} PROMPT:\n{prompt}",
                    "INFO",
                )
            r = requests.post(url, headers=headers, json=body, timeout=(20, 240))
            
            # HTTP Error handling
            if r.status_code != 200:
                last_err = f"Vertex HTTP {r.status_code}: {r.text[:500]}"
                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    debug_callback(
                        f"AI CEVAP (Vertex Gemini) {tag} HTTP {r.status_code} RAW:\n{(r.text or '')[:8000]}",
                        "WARNING",
                    )
                # 429/5xx -> retry
                if r.status_code in (429, 500, 502, 503, 504):
                    sleep_s = backoff_base ** attempt
                    time.sleep(min(30.0, sleep_s))
                    continue
                # Other errors -> stop
                return [], last_err

            # Parsing
            data = r.json()
            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                debug_callback(
                    f"AI CEVAP (Vertex Gemini) {tag} deneme {attempt+1}/{retries} RAW:\n{(r.text or '')[:8000]}",
                    "INFO",
                )
            text_out = ""
            cands = data.get("candidates", [])
            if cands and isinstance(cands, list):
                content = cands[0].get("content", {})
                parts = content.get("parts", [])
                if parts and isinstance(parts, list):
                    text_out = "".join([(p.get("text") or "") for p in parts])

            if (text_out or "").strip().upper() == "NONE":
                return [], None

            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                snippet = (text_out or "").replace("\n", "\\n")
                debug_callback(f"AI ÇIKTI (Vertex Gemini) {tag}: {snippet[:600]}", "INFO")

            items = _extract_items_from_tsv(text_out)
            if not items:
                obj = _extract_json_from_text(text_out)
                if isinstance(obj, list):
                    for it in obj:
                        if not isinstance(it, dict):
                            continue
                        items.append({
                            "wrong": it.get("wrong", "") or it.get("error", "") or "",
                            "suggestion": it.get("suggestion", "") or it.get("fix", "") or "",
                            "reason": it.get("reason", "") or it.get("note", "") or "",
                        })

            if not items:
                last_err = f"Vertex: çıktı parse edilemedi (deneme {attempt+1}/{retries}). Text: {text_out[:100]}..."
                if debug_callback is not None:
                    tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                    debug_callback(
                        f"Vertex Gemini parse retry {tag}: deneme {attempt+1}/{retries} (çıktı parse edilemedi)",
                        "WARNING",
                    )
                time.sleep(1.0)
                continue

            out = []
            for it in items:
                out.append({
                    "wrong": it.get("wrong", "") or "",
                    "suggestion": it.get("suggestion", "") or "",
                    "reason": it.get("reason", "") or "",
                    "source": "gemini",
                })
            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                prev = [f"{x.get('wrong','')}→{x.get('suggestion','')}" for x in out[:6]]
                debug_callback(
                    f"AI PARSE (Vertex Gemini) {tag}: {len(out)} hata. İlkler: {', '.join(prev)}",
                    "INFO",
                )
            return out, None

        except Exception as e:
            last_err = f"Vertex exception: {e}"
            time.sleep(1.0)
            continue

    return [], (last_err or "Vertex: işlem başarısız oldu (max retries).")


def _is_vertex_auth_or_perm_error(err: str) -> bool:
    e = (err or "").lower()
    if not e:
        return False
    # OAuth/ADC errors + HTTP 401/403
    return (
        ("vertex auth error" in e)
        or ("default credentials" in e)
        or ("could not automatically determine credentials" in e)
        or ("permission_denied" in e)
        or ("permission denied" in e)
        or ("http 401" in e)
        or ("http 403" in e)
        or ("status code 401" in e)
        or ("status code 403" in e)
        or ("unauthenticated" in e)
        or ("insufficient authentication scopes" in e)
        or ("invalid_grant" in e)
    )

def _is_vertex_model_not_found(err: str) -> bool:
    e = (err or "").lower()
    if not e:
        return False
    # Typical Vertex model/region not available case
    return ("http 404" in e) and ("publisher model" in e) and ("not found" in e)


# =========================
# OpenAI Spellcheck (Responses API via HTTP)
# =========================
def openai_spellcheck_paragraph(
    paragraph: str,
    api_key: str,
    model: str,
    paragraph_index: Optional[int] = None,
    debug_callback: Optional[Callable[[str, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    paragraph = (paragraph or "").strip()
    if not paragraph:
        return [], None

    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    prompt = (
        "You are an extremely strict Arabic spelling proofreader for a critical edition (tahqiq).\n"
        "Return ONLY valid JSON (an array). No extra text.\n"
        "Each item must be: {\"wrong\":\"...\",\"suggestion\":\"...\",\"reason\":\"...\"}\n"
        "Rules:\n"
        "- DO NOT suggest or flag any changes that are only about: harakat/diacritics, i'rab/case endings, tanwin, shadda, sukun/jazm, nasb endings.\n"
        "- Ignore Arabic diacritics and i'rab marks completely (do not flag them).\n"
        "- Focus on orthography/spelling/letter-level mistakes.\n"
        "- Max 30 items.\n"
        "Text:\n"
        f"{paragraph}"
    )

    body = {
        "model": model,
        "input": prompt,
        "temperature": 0.1,
        "max_output_tokens": 8192,
    }

    def parse_output_text(resp_json: dict) -> str:
        ot = resp_json.get("output_text")
        if isinstance(ot, str) and ot.strip():
            return ot
        out = resp_json.get("output", [])
        if isinstance(out, list):
            texts = []
            for item in out:
                content = item.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if c.get("type") == "output_text" and isinstance(c.get("text"), str):
                            texts.append(c["text"])
                        elif isinstance(c.get("text"), str):
                            texts.append(c.get("text"))
            if texts:
                return "".join([t for t in texts if isinstance(t, str)])
        return ""

    try:
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            debug_callback(f"AI İSTEK (GPT/OpenAI) {tag} PROMPT:\n{prompt}", "INFO")
        r = requests.post(url, headers=headers, json=body, timeout=(20, 240))
        if r.status_code != 200:
            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                debug_callback(
                    f"AI CEVAP (GPT/OpenAI) {tag} HTTP {r.status_code} RAW:\n{(r.text or '')[:8000]}",
                    "WARNING",
                )
            return [], f"OpenAI HTTP {r.status_code}: {r.text[:500]}"
        data = r.json()
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            debug_callback(f"AI CEVAP (GPT/OpenAI) {tag} RAW:\n{(r.text or '')[:8000]}", "INFO")

        text_out = parse_output_text(data)
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            snippet = (text_out or "").replace("\n", "\\n")
            debug_callback(f"AI ÇIKTI (GPT/OpenAI) {tag}: {snippet[:600]}", "INFO")
        obj = _extract_json_from_text(text_out)
        if not isinstance(obj, list):
            return [], "OpenAI: JSON parse edilemedi (model metin döndürdü)."

        out = []
        for it in obj:
            if not isinstance(it, dict):
                continue
            out.append({
                "wrong": it.get("wrong", "") or it.get("error", "") or "",
                "suggestion": it.get("suggestion", "") or it.get("fix", "") or "",
                "reason": it.get("reason", "") or it.get("note", "") or "",
                "source": "openai",
            })
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            prev = [f"{x.get('wrong','')}→{x.get('suggestion','')}" for x in out[:6]]
            debug_callback(
                f"AI PARSE (GPT/OpenAI) {tag}: {len(out)} hata. İlkler: {', '.join(prev)}",
                "INFO",
            )
        return out, None
    except Exception as e:
        return [], f"OpenAI exception: {e}"


# =========================
# Claude Spellcheck (Anthropic API)
# =========================
def claude_spellcheck_paragraph(
    paragraph: str,
    api_key: str,
    model: str,
    paragraph_index: Optional[int] = None,
    debug_callback: Optional[Callable[[str, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    paragraph = (paragraph or "").strip()
    if not paragraph:
        return [], None

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    prompt = (
        "أنت مدقق إملائي عربي شديد الدقة لنص محقق.\n"
        "أخرج فقط JSON (مصفوفة) بدون أي كلام إضافي.\n"
        "كل عنصر بالشكل:\n"
        "{\"wrong\":\"...\",\"suggestion\":\"...\",\"reason\":\"...\"}\n"
        "قواعد:\n"
        "- لا تقترح أي تصحيح للحركات/التشكيل/الإعراب/التنوين/الشدة/السكون/الجزم/النصب.\n"
        "- تجاهل الحركات والإعراب (لا تعتبرها أخطاء).\n"
        "- إذا كان التصحيح فقط في التشكيل أو علامات الإعراب أو (ألف التنوين في آخر الكلمة) فلا تذكره.\n"
        "- ركّز على أخطاء الرسم/الإملاء/الحروف (همزات، تاء مربوطة/هاء، ألف/ياء، ...).\n"
        "- لا تذكر أكثر من 30 خطأ.\n"
        "النص:\n"
        f"{paragraph}\n"
    )

    body = {
        "model": model,
        "max_tokens": 8192,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            debug_callback(f"AI İSTEK (Claude) {tag} PROMPT:\n{prompt}", "INFO")
        r = requests.post(url, headers=headers, json=body, timeout=(20, 240))
        if r.status_code != 200:
            if debug_callback is not None:
                tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
                debug_callback(
                    f"AI CEVAP (Claude) {tag} HTTP {r.status_code} RAW:\n{(r.text or '')[:8000]}",
                    "WARNING",
                )
            return [], f"Claude HTTP {r.status_code}: {r.text[:500]}"
        data = r.json()
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            debug_callback(f"AI CEVAP (Claude) {tag} RAW:\n{(r.text or '')[:8000]}", "INFO")

        text_out = ""
        content = data.get("content", [])
        if content and isinstance(content, list):
            for item in content:
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_out += item["text"]

        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            snippet = (text_out or "").replace("\n", "\\n")
            debug_callback(f"AI ÇIKTI (Claude) {tag}: {snippet[:600]}", "INFO")
        obj = _extract_json_from_text(text_out)
        if not isinstance(obj, list):
            return [], "Claude: JSON parse edilemedi (model metin döndürdü)."

        out = []
        for it in obj:
            if not isinstance(it, dict):
                continue
            out.append({
                "wrong": it.get("wrong", "") or it.get("error", "") or "",
                "suggestion": it.get("suggestion", "") or it.get("fix", "") or "",
                "reason": it.get("reason", "") or it.get("note", "") or "",
                "source": "claude",
            })
        if debug_callback is not None:
            tag = f"P{paragraph_index}" if isinstance(paragraph_index, int) else "P?"
            prev = [f"{x.get('wrong','')}→{x.get('suggestion','')}" for x in out[:6]]
            debug_callback(
                f"AI PARSE (Claude) {tag}: {len(out)} hata. İlkler: {', '.join(prev)}",
                "INFO",
            )
        return out, None
    except Exception as e:
        return [], f"Claude exception: {e}"


def spellcheck_tahkik_paragraphs(
    docx_path: Path,
    use_gemini: bool = True,
    use_openai: bool = True,
    use_claude: bool = False,
    start_paragraph: int = 1,
    selected_paragraphs: Optional[List[int]] = None,
    append_to_existing: bool = False,
    status_callback: Optional[Callable[[str, str], None]] = None,
    debug_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    if status_callback:
        status_callback(f"Word dosyası okunuyor: {docx_path.name}...", "INFO")
    paras = read_docx_paragraphs(docx_path)
    paras = paras[:min(len(paras), SPELLCHECK_MAX_PARAS)]
    
    if status_callback:
        status_callback(f"✓ {len(paras)} paragraf bulundu, imla kontrolü başlatılıyor...", "INFO")

    # Start offset (1-based)
    try:
        start_paragraph = int(start_paragraph)
    except Exception:
        start_paragraph = 1
    if start_paragraph < 1:
        start_paragraph = 1
    if start_paragraph > len(paras):
        start_paragraph = len(paras) if paras else 1
    if status_callback and start_paragraph > 1:
        status_callback(f"SPELLCHECK: Başlangıç paragrafı: P{start_paragraph} (öncekiler atlanacak).", "INFO")

    # Optional explicit selection list (1-based paragraph indices)
    sel_set: Optional[Set[int]] = None
    if selected_paragraphs is not None:
        try:
            cand = [int(x) for x in list(selected_paragraphs)]
        except Exception:
            cand = []
        cand = sorted({x for x in cand if 1 <= x <= len(paras)})
        sel_set = set(cand)
        if status_callback:
            if cand:
                status_callback(f"SPELLCHECK: Seçili paragraflar: {len(cand)} adet (min=P{cand[0]}, max=P{cand[-1]}).", "INFO")
            else:
                status_callback("SPELLCHECK: Seçili paragraf yok (liste boş). Hiçbir paragraf kontrol edilmeyecek.", "WARNING")

    all_errors: List[Dict[str, Any]] = []
    per_para: List[Dict[str, Any]] = []
    call_errors: List[Dict[str, Any]] = []

    gem_provider = (GEMINI_PROVIDER or "ai_studio").strip().lower()
    # User request: stop using Vertex; always use AI Studio API key for Gemini spellcheck.
    if use_gemini and gem_provider == "vertex":
        if status_callback:
            status_callback("GEMINI_PROVIDER=vertex tespit edildi ama Vertex devre dışı: AI Studio kullanılacak.", "WARNING")
        gem_provider = "ai_studio"
    gem_key = None
    if use_gemini and gem_provider not in ("vertex", "ai_studio"):
        raise RuntimeError("GEMINI_PROVIDER geçersiz. Değer: ai_studio veya vertex olmalı.")
    if use_gemini and gem_provider == "ai_studio":
        gem_key = get_gemini_api_key()

    oa_key = get_openai_api_key() if use_openai else None
    claude_key = get_claude_api_key() if use_claude else None

    # Döküman token frekansları: Claude yanlış-pozitif filtreleme için
    all_text = "\n".join([p for p in paras if isinstance(p, str)])
    all_tokens_norm = [normalize_ar(t) for t in all_text.split() if normalize_ar(t)]
    token_counts = Counter(all_tokens_norm)
    total_tokens = len(all_tokens_norm)

    # If a model hits quota/rate-limit, disable it for remaining paragraphs to avoid wasting time.
    # [MODIFIED]: User requested NOT to auto-disable models on error, so we keep flags but don't set them false.
    gem_enabled = bool(use_gemini)
    oa_enabled = bool(use_openai)
    claude_enabled = bool(use_claude)
    
    # Track "quota exceeded" errors to auto-skip only when absolutely necessary (hard quota, not rate-limit)
    gem_quota_busted = False
    
    for idx, p in enumerate(paras):
        # If selection is set, only run selected paragraphs (but keep stable indexing)
        if sel_set is not None and (idx + 1) not in sel_set:
            per_para.append({"paragraph_index": idx + 1, "text": p, "errors": []})
            continue
        # Skip early paragraphs if requested (but still keep a per_paragraph entry for stable indexing)
        if (idx + 1) < start_paragraph:
            per_para.append({"paragraph_index": idx + 1, "text": p, "errors": []})
            continue
        if status_callback and (idx + 1) % 5 == 0:
            status_callback(f"  Paragraf {idx + 1}/{len(paras)} kontrol ediliyor...", "INFO")
        e1, err1 = ([], None)
        e2, err2 = ([], None)
        e3, err3 = ([], None)

        if gem_enabled:
            # If quota is busted (hard stop), skip calls to avoid spamming errors
            if gem_quota_busted:
                pass 
            else:
                if gem_provider == "vertex":
                    e1, err1 = vertex_gemini_spellcheck_paragraph(
                        p,
                        project_id=VERTEX_PROJECT_ID,
                        location=VERTEX_LOCATION,
                        model=VERTEX_GEMINI_MODEL,
                        paragraph_index=idx + 1,
                        debug_callback=debug_callback,
                    )
                    # If the model is not found (common with region/model-id mismatch), try known Gemini 3 Pro variants
                    if err1 and _is_vertex_model_not_found(err1):
                        # 1) try preview id in same location
                        alt_models = []
                        m0 = (VERTEX_GEMINI_MODEL or "").strip()
                        if m0 and m0 != "gemini-3-pro-preview":
                            alt_models.append("gemini-3-pro-preview")
                        # 2) try global location (some models are only under global)
                        tried = False
                        for am in alt_models:
                            tried = True
                            if status_callback:
                                status_callback(f"Vertex 404: '{m0}' bulunamadı. Alternatif deneniyor: {am}", "WARNING")
                            e1a, err1a = vertex_gemini_spellcheck_paragraph(
                                p,
                                project_id=VERTEX_PROJECT_ID,
                                location=VERTEX_LOCATION,
                                model=am,
                                paragraph_index=idx + 1,
                                debug_callback=debug_callback,
                            )
                            if not err1a:
                                e1, err1 = e1a, None
                                break
                        if err1:
                            tried = True
                            if status_callback:
                                status_callback("Vertex 404: global lokasyonda tekrar denenecek (location=global).", "WARNING")
                            e1g, err1g = vertex_gemini_spellcheck_paragraph(
                                p,
                                project_id=VERTEX_PROJECT_ID,
                                location="global",
                                model=(VERTEX_GEMINI_MODEL or "gemini-3-pro-preview"),
                                paragraph_index=idx + 1,
                                debug_callback=debug_callback,
                            )
                            if not err1g:
                                e1, err1 = e1g, None
                        if tried and err1 and status_callback:
                            status_callback(
                                "Vertex tarafında model/region uyumsuzluğu devam ediyor. "
                                "İstersen GEMINI_PROVIDER=ai_studio ile devam edebiliriz.",
                                "WARNING",
                            )
                    # If Vertex fails due to auth/perm and we have an AI Studio key, fallback once for this paragraph
                    if err1 and gem_key and _is_vertex_auth_or_perm_error(err1):
                        if status_callback:
                            status_callback(
                                f"Vertex auth/izin hatası alındı, bu paragraf için AI Studio fallback deneniyor. (P{idx+1})",
                                "WARNING",
                            )
                        e1b, err1b = gemini_spellcheck_paragraph(
                            p,
                            api_key=gem_key,
                            model=SPELLCHECK_GEMINI_MODEL,
                            paragraph_index=idx + 1,
                            debug_callback=debug_callback,
                        )
                        if not err1b:
                            # Mark that this paragraph was served by fallback (still counts as gemini)
                            err1 = None
                            e1 = e1b
                else:
                    e1, err1 = gemini_spellcheck_paragraph(
                        p,
                        api_key=gem_key,
                        model=SPELLCHECK_GEMINI_MODEL,
                        paragraph_index=idx + 1,
                        debug_callback=debug_callback,
                    )
                
                if err1:
                    call_errors.append({"paragraph_index": idx + 1, "source": "gemini", "error": err1})
                    if status_callback:
                        status_callback(f"API HATASI (Gemini) P{idx+1}: {err1[:220]}", "ERROR")
                    
                    # Check for hard quota error to stop wasting calls
                    if "exceeded your current quota" in str(err1).lower():
                        gem_quota_busted = True
                        if status_callback:
                            status_callback("KOTA BİTTİ (Gemini): Kalan paragraflar atlanacak.", "WARNING")
                            
            # Gemini rate-limit'e takılmamak için küçük throttle
            time.sleep(0.35)

        if oa_enabled:
            e2, err2 = openai_spellcheck_paragraph(
                p,
                api_key=oa_key,
                model=OPENAI_MODEL,
                paragraph_index=idx + 1,
                debug_callback=debug_callback,
            )
            if err2:
                call_errors.append({"paragraph_index": idx + 1, "source": "openai", "error": err2})
                if status_callback:
                    status_callback(f"API HATASI (GPT/OpenAI) P{idx+1}: {err2[:220]}", "ERROR")

        if claude_enabled:
            e3, err3 = claude_spellcheck_paragraph(
                p,
                api_key=claude_key,
                model=CLAUDE_MODEL,
                paragraph_index=idx + 1,
                debug_callback=debug_callback,
            )
            if err3:
                call_errors.append({"paragraph_index": idx + 1, "source": "claude", "error": err3})
                if status_callback:
                    status_callback(f"API HATASI (Claude) P{idx+1}: {err3[:220]}", "ERROR")

        merged = _merge_errors(e1 + e2 + e3)
        merged = _filter_non_orthographic_errors(merged, status_callback=status_callback)
        merged = _filter_suspicious_errors(merged, token_counts, total_tokens, status_callback=status_callback)
        for e in merged:
            e["paragraph_index"] = idx + 1

        per_para.append({
            "paragraph_index": idx + 1,
            "text": p,
            "errors": merged
        })
        all_errors.extend(merged)

    global_merged = _merge_errors(all_errors)
    global_merged = _filter_non_orthographic_errors(global_merged, status_callback=status_callback)
    global_merged = _filter_suspicious_errors(global_merged, token_counts, total_tokens, status_callback=status_callback)

    payload = {
        "docx_path": str(docx_path),
        "paragraphs_count": len(paras),
        "start_paragraph": start_paragraph,
        "selected_paragraphs": sorted(sel_set) if sel_set is not None else None,
        "gemini_model": (
            (VERTEX_GEMINI_MODEL if gem_provider == "vertex" else SPELLCHECK_GEMINI_MODEL) if use_gemini else None
        ),
        "openai_model": OPENAI_MODEL if use_openai else None,
        "claude_model": CLAUDE_MODEL if use_claude else None,
        "errors_merged": global_merged,
        "per_paragraph": per_para,
        "call_errors": call_errors,
    }

    # Run metadata (for viewer transparency / audit)
    payload["runs"] = [
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "start_paragraph": start_paragraph,
            "selected_paragraphs": sorted(sel_set) if sel_set is not None else None,
            "provider": gem_provider if use_gemini else None,
            "models": {
                "gemini": bool(use_gemini),
                "openai": bool(use_openai),
                "claude": bool(use_claude),
            },
        }
    ]

    if append_to_existing and SPELLCHECK_JSON.exists():
        ex = _load_existing_spellcheck_json()
        if isinstance(ex, dict):
            if status_callback:
                status_callback("SPELLCHECK: Mevcut sonuçlara ekleniyor (append)...", "INFO")
            payload = _merge_spellcheck_payloads(
                existing=ex,
                delta=payload,
                docx_path=docx_path,
                paras=paras,
                token_counts=token_counts,
                total_tokens=total_tokens,
                status_callback=status_callback,
            )

    if SPELLCHECK_SAVE_JSON:
        _backup_spellcheck_json(payload, status_callback=status_callback)
        SPELLCHECK_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload

