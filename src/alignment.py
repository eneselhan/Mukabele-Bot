# -*- coding: utf-8 -*-
"""
Global Sequence Alignment (Word-level LCS/Levenshtein)
Bu algoritma, tüm OCR metni ile Dizgi metnini tek bir uzun dizi gibi düşünür,
global hizalama (edit distance) yaparak "kesin eşleşen" kelimeleri (anchor) bulur,
ardından satır sınırlarını bu anchor'lara göre belirler.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
from rapidfuzz.distance import Levenshtein
from rapidfuzz import fuzz
from src.config import ALIGNMENT_JSON, BEAM_K, CAND_TOPK, PREFIX_WORDS
from src.document import read_docx_text, tokenize_text
from src.ocr import load_ocr_lines_ordered
from src.config import NUSHA2_LINES_MANIFEST, NUSHA2_OCR_DIR, NUSHA3_LINES_MANIFEST, NUSHA3_OCR_DIR
from src.utils import normalize_ar, take_prefix_words
from src.scoring import score_segment
from src.spellcheck import _normalize_error_word
# (kept above) NUSHA2_*/NUSHA3_* imports

ALGO_VERSION = "v7-global-anchor-refinement"

def find_alignment_anchor(ocr_lines: List[Dict[str, Any]], tahkik_tokens: List[str]) -> int:
    """
    Word dosyasının başlangıcını (imzasını) OCR satırları içinde arar.
    Hata korumalı (Safe Mode) versiyondur. Asla sistemi çökertmez.
    """
    try:
        # GÜVENLİK KONTROLÜ 1: Veri var mı?
        if not tahkik_tokens or not ocr_lines:
            return 0

        # GÜVENLİK KONTROLÜ 2: normalize_ar fonksiyonu erişilebilir mi?
        # Erişilemezse yerel bir lambda kullan (Yedek lastik)
        try:
            # Global scope'ta normalize_ar var mı diye basit bir test yapıyoruz
            test_norm = normalize_ar("test")
            local_normalize = normalize_ar
        except (NameError, Exception):
            print("UYARI: normalize_ar bulunamadı, basit normalizasyon kullanılıyor.")
            local_normalize = lambda x: x.strip()

        # 1. İMZA OLUŞTURMA
        # İlk 40 kelimeyi al
        signature_tokens = [local_normalize(t) for t in tahkik_tokens[:40] if t and len(t) > 1]
        signature_str = "".join(signature_tokens)

        if len(signature_str) < 10: 
            return 0

        best_ratio = 0.0
        best_line_idx = 0
        
        # 2. ARAMA PENCERESİ (İlk 300 satır)
        scan_limit = min(len(ocr_lines), 300)
        
        for i in range(scan_limit):
            # Pencere: i. satırdan sonraki 8 satırın metnini birleştir
            window_tokens = []
            for k in range(i, min(i + 8, len(ocr_lines))):
                txt = ocr_lines[k].get("ocr_text", "") or ""
                # OCR gürültüsünü (tek harflik D, G, ., -) temizle
                clean_tokens = [local_normalize(w) for w in txt.split() if len(w) > 1]
                window_tokens.extend(clean_tokens)
                
            window_str = "".join(window_tokens)
            
            # Karşılaştırma: İmzamız, bu pencerenin içinde "kabaca" var mı?
            check_len = int(len(signature_str) * 1.5)
            compare_part = window_str[:check_len]
            
            if not compare_part: continue

            ratio = 0.0
            try:
                ratio = Levenshtein.normalized_similarity(signature_str, compare_part)
            except Exception:
                pass
            
            # Skoru Kaydet
            if ratio > best_ratio:
                best_ratio = ratio
                best_line_idx = i

        print(f"DEBUG: Anchor Search (Safe) -> Best Score: {best_ratio:.2f} at Line {best_line_idx}")

        # 3. KARAR MEKANİZMASI
        if best_ratio > 0.35:
            return best_line_idx
        else:
            return 0

    except Exception as e:
        print(f"HATA: find_alignment_anchor çöktü: {e}. Varsayılan 0 dönülüyor.")
        return 0

def align_ocr_to_tahkik_segment_dp(
    docx_path: Path,
    spellcheck_payload: Optional[Dict[str, Any]] = None,
    status_callback: Optional[Callable[[str, str], None]] = None,
    ocr_lines_override: Optional[List[Dict[str, Any]]] = None,
    write_json: bool = True,
) -> Dict[str, Any]:
    """
    Word dosyasındaki metni, OCR satırlarına hizalar.
    Yöntem: Global Sequence Alignment (Word-Level).
    """
    
    # 1. Kaynakları Yükle
    if status_callback:
        status_callback("Tahkik metni ve OCR verisi yükleniyor...", "INFO")
        
    tahkik_raw = read_docx_text(docx_path)
    if not tahkik_raw:
        raise RuntimeError("Word (.docx) metni okunamadı.")
        
    tahkik_tokens = tokenize_text(tahkik_raw)
    if not tahkik_tokens:
        raise RuntimeError("Tahkik metni tokenize edilemedi (boş olabilir).")
        
    ocr_lines = ocr_lines_override if ocr_lines_override is not None else load_ocr_lines_ordered()
    if not ocr_lines:
        raise RuntimeError("OCR satırları bulunamadı.")

    # 1. BAŞLANGIÇ NOKTASINI BUL
    start_line_idx = find_alignment_anchor(ocr_lines, tahkik_tokens)
    if status_callback and start_line_idx > 0:
        status_callback(f"Giriş kısmı atlanıyor: İlk {start_line_idx} satır hizalamaya dahil edilmeyecek.", "INFO")

    # 2. LİSTELERİ AYIR
    ignored_ocr_lines = ocr_lines[:start_line_idx]   # Giriş kısmı (Önsöz vb.)
    active_ocr_lines = ocr_lines[start_line_idx:]    # Asıl Metin
    M = len(tahkik_tokens)
    N = len(active_ocr_lines) # ARTIK SADECE AKTİF SATIRLARI SAYIYORUZ

    # 3. Normalizasyon ve Flattening (Düzleştirme)
    # Global hizalama için aktif OCR satırlarını tek bir kelime listesi yapıyoruz.
    # Aynı zamanda hangi kelimenin hangi satırdan geldiğini saklıyoruz.
    
    tahkik_norms = [normalize_ar(t) for t in tahkik_tokens]
    
    ocr_flat_norms = []
    ocr_token_map = [] # index -> (line_idx, word_idx_in_line)
    line_boundaries = [] # line_idx -> (flat_start, flat_end)
    
    current_flat_idx = 0
    for line_idx, item in enumerate(active_ocr_lines):
        txt = item.get("ocr_text") or ""
        # Kelime kelime böl
        words = txt.split()
        start_idx = current_flat_idx
        
        for w_idx, w in enumerate(words):
            n = normalize_ar(w)
            ocr_flat_norms.append(n)
            ocr_token_map.append((line_idx, w_idx))
            
        current_flat_idx += len(words)
        line_boundaries.append({
            "start": start_idx,
            "end": current_flat_idx, # exclusive
            "raw_text": txt,
            "item": item
        })
        
    K = len(ocr_flat_norms)
    if K == 0:
        raise RuntimeError("OCR metni tamamen boş.")

    if status_callback:
        status_callback(f"Hizalama başlıyor: {M} kelime (Word) vs {K} kelime (OCR)...", "INFO")

    # 3. Encoding (Word -> Character)
    # Levenshtein/Opcodes algoritması string üzerinde çok hızlı çalışır.
    # Kelimeleri unique karakterlere (Unicode Private Use Area) dönüştürüp string hizalaması yapacağız.
    
    unique_words = sorted(list(set([w for w in tahkik_norms if w] + [w for w in ocr_flat_norms if w])))
    word2char = {w: chr(0xE000 + i) for i, w in enumerate(unique_words)}
    
    # Boş string (normalize sonucu boşalanlar) için özel bir karakter atamaya gerek yok, atlayabiliriz
    # ama indeks kaymasın diye dummy bir karakter verelim veya boş string olarak birleştirelim.
    # Burada indekslerin korunması kritik. Boş normları 'bilinmeyen' bir karaktere eşleyelim.
    # IMPORTANT: 0xD800-0xDFFF are surrogate code points; avoid them (can crash native libs).
    NULL_CHAR = chr(0xFFFF)  # safe sentinel (noncharacter but valid scalar)
    
    def encode_tokens(token_list):
        chars = []
        for t in token_list:
            if not t:
                chars.append(NULL_CHAR)
            else:
                chars.append(word2char.get(t, NULL_CHAR))
        return "".join(chars)
        
    tahkik_str = encode_tokens(tahkik_norms)
    ocr_str = encode_tokens(ocr_flat_norms)
    
    # 4. Global Alignment (EditOps / Opcodes)
    # OCR stringini Tahkik stringine dönüştüren adımları bul.
    # opcodes: list of (tag, i1, i2, j1, j2)
    # i: ocr (src), j: tahkik (dest)
    try:
        opcodes = Levenshtein.opcodes(ocr_str, tahkik_str)
    except Exception as e:
        # Fallback: Çok büyük metinlerde bellek sorunu olursa
        print(f"Global hizalama hatası (fallback yapılacak): {e}")
        # Basit oran orantı fallback (bunu kodlamak uzun sürer, genelde hata vermez)
        raise e

    # 5. Milestone Extraction (Anchor Points) & FUZZY MATCHING FIX
    ocr_to_tahkik_matches = {} # flat_ocr_idx -> tahkik_idx
    
    # Char -> Word ters dönüşümü (Fuzzy kontrol için)
    char2word_list = unique_words # İndeks erişimi için
    
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'equal':
            # KESİN EŞLEŞME: Zaten mükemmel, direkt ekle
            count = i2 - i1
            for k in range(count):
                if ocr_str[i1 + k] != NULL_CHAR:
                    ocr_to_tahkik_matches[i1 + k] = j1 + k
        
        elif tag == 'replace':
            # YAKLAŞIK EŞLEŞME (Fuzzy Logic): 
            # Kelimeler farklı ama çok benziyorsa, yine de çapa (anchor) olarak kullan.
            # Bu, "Fermuar Kaymasını" (Zipper Slip) engeller.
            
            ocr_len = i2 - i1
            tahkik_len = j2 - j1
            
            # Sadece birebir (1-1) değişimlerde kontrol et
            if ocr_len == tahkik_len:
                for k in range(ocr_len):
                    c_ocr = ocr_str[i1 + k]
                    c_tahkik = tahkik_str[j1 + k]
                    
                    if c_ocr == NULL_CHAR or c_tahkik == NULL_CHAR:
                        continue
                        
                    # Karakterden kelimeye dön
                    w_ocr = char2word_list[ord(c_ocr) - 0xE000]
                    w_tahkik = char2word_list[ord(c_tahkik) - 0xE000]
                    
                    # Benzerlik oranı (0.0 - 100.0)
                    ratio = Levenshtein.normalized_similarity(w_ocr, w_tahkik)
                    
                    # EŞİK DEĞERİ: %65 benzerlik yeterli (Örn: "Kalem" - "Kelem")
                    if ratio > 0.65:
                        ocr_to_tahkik_matches[i1 + k] = j1 + k

    # 6. Satır Sınırlarını Belirleme (Refinement & Interpolation)
    line_segments = [] # (start_idx, end_idx) for each line
    
    # Her satırın "kesin" sınırlarını bul (matches üzerinden)
    # Eğer eşleşme yoksa None
    raw_bounds = []
    for line_idx in range(N):
        info = line_boundaries[line_idx]
        s, e = info["start"], info["end"]
        
        # Bu satıra ait eşleşen indeksleri topla
        matched_tindices = []
        for fi in range(s, e):
            if fi in ocr_to_tahkik_matches:
                matched_tindices.append(ocr_to_tahkik_matches[fi])
        
        if matched_tindices:
            # Satırın Word'deki en erken ve en geç eşleşmesi
            raw_bounds.append((min(matched_tindices), max(matched_tindices) + 1))
        else:
            raw_bounds.append(None)
            
    # Boşlukları Doldurma (Gap Filling / Interpolation)
    # raw_bounds listesindeki None'ları ve aradaki boşlukları mantıklı şekilde doldur.
    
    final_bounds = [(0, 0)] * N
    last_valid_end = 0
    
    # İleriye doğru tara: Bir sonraki "dolu" satırı bul, aradakileri paylaştır
    i = 0
    while i < N:
        if raw_bounds[i] is not None:
            # Zaten sınırları belli, ancak önceki bitişle çakışma/boşluk kontrolü yap
            start, end = raw_bounds[i]
            
            # Monotonluk zorla: Başlangıç, önceki bitişten önce olamaz (küçük tolerans hariç)
            # Global alignment zaten monoton üretir ama kelime içi sıralama oynamış olabilir.
            if start < last_valid_end:
                start = last_valid_end
            if end < start:
                end = start
                
            # Eğer önceki satır ile bu satır arasında büyük boşluk varsa?
            # Şimdilik: Boşluğu önceki satıra mı bu satıra mı verelim?
            # Genelde bir önceki satırın bitişini bu satırın başlangıcına uzatmak (gap closing) iyidir.
            # Ancak "Interpolasyon" döngüsünde halledilecek.
            
            final_bounds[i] = (start, end)
            last_valid_end = end
            i += 1
        else:
            # Boş (None) bölge başladı. Bir sonraki dolu bölgeyi bul.
            j = i + 1
            while j < N and raw_bounds[j] is None:
                j += 1
            
            # i den j-1 e kadar olan satırlar boş.
            # Referans noktaları:
            prev_end = last_valid_end
            
            if j < N:
                next_start = raw_bounds[j][0]
                # Monotonluk düzeltmesi
                if next_start < prev_end:
                    next_start = prev_end
            else:
                # Sona kadar boş
                next_start = M # Word metninin sonu
            
            # Aradaki kelime havuzunu (next_start - prev_end)
            # aradaki boş OCR satırlarının kelime sayılarına (weight) göre paylaştır.
            total_gap_tokens = next_start - prev_end
            
            # Aradaki OCR satırlarının kelime sayılarını topla
            gap_ocr_counts = []
            for k in range(i, j):
                wc = line_boundaries[k]["end"] - line_boundaries[k]["start"]
                gap_ocr_counts.append(wc)
            
            total_ocr_wc = sum(gap_ocr_counts)
            
            current_cursor = prev_end
            for k_idx, k in enumerate(range(i, j)):
                if total_ocr_wc > 0:
                    # Orantılı pay
                    share = int(round(total_gap_tokens * (gap_ocr_counts[k_idx] / total_ocr_wc)))
                else:
                    # OCR satırları da boşsa eşit/sıfır pay (genelde boş satır)
                    share = 0
                
                # Pay en az 0, ama mantıklı sınırlar içinde
                seg_s = current_cursor
                seg_e = current_cursor + share
                
                # Sınırı aşma
                if seg_e > next_start:
                    seg_e = next_start
                
                final_bounds[k] = (seg_s, seg_e)
                current_cursor = seg_e
            
            last_valid_end = current_cursor
            i = j # Döngüyü j'den devam ettir

    # Gap Closing (Son Düzeltme)
    # Bitişik satırlar arasında hizalanmamış kelimeler kaldıysa, bunları dağıt.
    # k. satır bitişi ile k+1. satır başlangıcı arasında boşluk varsa, ortadan böl.
    for i in range(N - 1):
        curr_s, curr_e = final_bounds[i]
        next_s, next_e = final_bounds[i+1]
        
        if curr_e < next_s:
            # Arada boşluk var
            mid = (curr_e + next_s) // 2
            final_bounds[i] = (curr_s, mid)
            final_bounds[i+1] = (mid, next_e)
        elif curr_e > next_s:
            # Çakışma var (overlap) -> Ortadan kes
            mid = (curr_s + next_e) // 2 # Hatalı mantık olabilir, basitçe:
            # curr_e geriye, next_s ileriye alınmalı? 
            # Basitçe: curr_e = next_s yap.
            # Veya: mid = (curr_e + next_s) // 2
            mid = (curr_e + next_s) // 2
            if mid < curr_s: mid = curr_s
            if mid > next_e: mid = next_e
            final_bounds[i] = (curr_s, mid)
            final_bounds[i+1] = (mid, next_e)

    # 7. Sonuçları Oluştur ve Skorla
    spell_errors = (spellcheck_payload or {}).get("errors_merged", []) if spellcheck_payload else []
    err_map = {}
    for e in spell_errors:
        wn = (e.get("wrong_norm") or _normalize_error_word(e.get("wrong", ""))).strip()
        if wn:
            err_map[wn] = e

    aligned_results = []
    
    for i in range(N):
        start, end = final_bounds[i]
        # Sınırları güvenli aralığa çek
        start = max(0, min(start, M))
        end = max(start, min(end, M))
        
        seg_raw = " ".join(tahkik_tokens[start:end]) if start < end else ""
        item = active_ocr_lines[i]
        ocr_txt = item.get("ocr_text") or ""
        
        # Skorlama
        o_norm = normalize_ar(ocr_txt)
        # Prefix hesaplama (scoring için)
        
        o_pref = normalize_ar(take_prefix_words(ocr_txt, PREFIX_WORDS))
        s_norm = normalize_ar(seg_raw)
        s_pref = normalize_ar(take_prefix_words(seg_raw, PREFIX_WORDS))
        
        score = score_segment(o_norm, o_pref, s_norm, s_pref)
        
        # Spellcheck hits
        hits = []
        if err_map and seg_raw:
            for tok in seg_raw.split():
                tn = normalize_ar(tok)
                if tn and tn in err_map:
                    hits.append({"word": tok, "word_norm": tn, "meta": err_map[tn]})
        
        best_cand = {
            "score": score,
            "start_word": start,
            "end_word": end,
            "raw": seg_raw
        }
        
        aligned_results.append({
            "line_no": i + 1,
            "line_image": item.get("line_image", ""),
            "ocr_text": ocr_txt,
            "page_image": item.get("page_image", ""),
            "page_name": item.get("page_name", ""),
            "bbox": item.get("bbox", None),
            "line_index": item.get("line_index", None),
            "best": best_cand,
            "candidates": [best_cand], # Artık tek ve "en iyi" aday var (global aligned)
            "error_hits": hits,
            "error_count": len({h["word_norm"] for h in hits}),
            "is_empty_ocr": (not ocr_txt.strip()),
            "ocr_wc": len(ocr_txt.split()),
            "seg_wc": len(seg_raw.split())
        })

    # --- ADIM 3: EKSİK PARÇALARI BİRLEŞTİRME ---
    final_aligned_results = []
    
    # 1. Atlanan Giriş Satırları (Ignored)
    # Bunları boş ama "bilgi verici" şekilde ekliyoruz
    for item in ignored_ocr_lines:
        final_aligned_results.append({
            "line_no": item.get("line_no"),
            "line_image": item.get("line_image", ""),
            "ocr_text": item.get("ocr_text", ""),
            "best": {
                "raw": "--- [GİRİŞ KISMI / HİZALAMA DIŞI] ---",
                "score": 0
            },
            "is_empty_ocr": False,
            "candidates": [],
            "error_hits": [],
            "error_count": 0,
            "ocr_wc": 0,
            "seg_wc": 0
        })

    # 2. Hizalanmış Satırlar (Active)
    final_aligned_results.extend(aligned_results)

    # Ana değişkeni güncelle ki payload doğru gitsin
    aligned_results = final_aligned_results

    # 8. Payload Hazırla ve Kaydet
    payload = {
        "algo_version": ALGO_VERSION,
        "docx_path": str(docx_path),
        "tahkik_word_count": M,
        "tahkik_tokens": tahkik_tokens,
        "lines_count": N,
        "aligned": aligned_results,
        "spellcheck": spell_errors
    }
    
    if write_json:
        ALIGNMENT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _match_alt_lines_by_token_mid(
    primary_aligned: List[Dict[str, Any]],
    alt_aligned: List[Dict[str, Any]],
    *,
    field: str = "alt",
) -> None:
    """
    Attach best-effort match from each line in `primary_aligned` to a line in `alt_aligned`,
    using the midpoint token index (based on best.start_word/end_word).

    Adds:
      item[field] = { line_no, line_image, ocr_text, best:{start_word,end_word,score} }  (or None)
    """
    if not primary_aligned or not alt_aligned:
        return

    alt_ranges: List[Tuple[int, int, Dict[str, Any]]] = []
    for a in alt_aligned:
        if not isinstance(a, dict):
            continue
        b = a.get("best") if isinstance(a.get("best"), dict) else {}
        s = b.get("start_word")
        e = b.get("end_word")
        if isinstance(s, int) and isinstance(e, int):
            alt_ranges.append((s, e, a))

    if not alt_ranges:
        return

    for it in primary_aligned:
        if not isinstance(it, dict):
            continue
        b = it.get("best") if isinstance(it.get("best"), dict) else {}
        s = b.get("start_word")
        e = b.get("end_word")
        if not isinstance(s, int) or not isinstance(e, int):
            it[field] = None
            continue

        mid = (s + e) // 2 if e > s else s
        best_obj = None
        best_dist = None
        for as_, ae_, aobj in alt_ranges:
            amid = (as_ + ae_) // 2 if ae_ > as_ else as_
            dist = abs(amid - mid)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_obj = aobj

        if not best_obj:
            it[field] = None
            continue

        it[field] = {
            "line_no": best_obj.get("line_no"),
            "line_image": best_obj.get("line_image", ""),
            "ocr_text": best_obj.get("ocr_text", ""),
            "best": best_obj.get("best", {}),
        }


def _attach_bidirectional_alt_links(primary_aligned: List[Dict[str, Any]], alt_aligned: List[Dict[str, Any]]) -> None:
    """
    Ensure both sides have `.alt` pointers so either list can be used as the main viewer mapping.
      - primary[i].alt -> best matching alt item (existing behavior)
      - alt[j].alt     -> best matching primary item (new)
    """
    _match_alt_lines_by_token_mid(primary_aligned, alt_aligned, field="alt")
    _match_alt_lines_by_token_mid(alt_aligned, primary_aligned, field="alt")


def _attach_bidirectional_named_links(
    a_list: List[Dict[str, Any]],
    b_list: List[Dict[str, Any]],
    *,
    field_a: str,
    field_b: str,
) -> None:
    """Attach best-effort pointers in BOTH directions with distinct field names."""
    _match_alt_lines_by_token_mid(a_list, b_list, field=field_a)
    _match_alt_lines_by_token_mid(b_list, a_list, field=field_b)


def _attach_overlap_alt_lists(
    primary_aligned: List[Dict[str, Any]],
    alt_aligned: List[Dict[str, Any]],
    *,
    max_keep: int = 6,
    field: str = "alt_list",
) -> None:
    """
    For each line, attach a list of overlapping lines from the other copy by token-span overlap.
    Adds:
      - item[field] = [ {line_no,line_image,ocr_text,best,overlap}, ... ]
    This supports cases where one nusha line corresponds to multiple lines in the other nusha.
    """
    if not primary_aligned or not alt_aligned:
        return

    alt_spans: List[Tuple[int, int, Dict[str, Any]]] = []
    for a in alt_aligned:
        if not isinstance(a, dict):
            continue
        b = a.get("best") if isinstance(a.get("best"), dict) else {}
        s = b.get("start_word")
        e = b.get("end_word")
        if isinstance(s, int) and isinstance(e, int) and e > s:
            alt_spans.append((s, e, a))

    if not alt_spans:
        return

    for it in primary_aligned:
        if not isinstance(it, dict):
            continue
        b = it.get("best") if isinstance(it.get("best"), dict) else {}
        s = b.get("start_word")
        e = b.get("end_word")
        if not isinstance(s, int) or not isinstance(e, int) or e <= s:
            it[field] = []
            continue

        hits: List[Tuple[int, Dict[str, Any]]] = []
        for as_, ae_, aobj in alt_spans:
            # overlap length
            ov = min(e, ae_) - max(s, as_)
            if ov > 0:
                # prefer higher overlap, tie-break by closer midpoints
                hits.append((ov, aobj))

        hits.sort(key=lambda x: x[0], reverse=True)
        out_list: List[Dict[str, Any]] = []
        for ov, aobj in hits[: max_keep]:
            out_list.append(
                {
                    "line_no": aobj.get("line_no"),
                    "line_image": aobj.get("line_image", ""),
                    "ocr_text": aobj.get("ocr_text", ""),
                    "best": aobj.get("best", {}),
                    "overlap": ov,
                }
            )
        it[field] = out_list


def align_ocr_to_tahkik_segment_dp_multi(
    docx_path: Path,
    spellcheck_payload: Optional[Dict[str, Any]] = None,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Build alignment for primary outputs, and if available, 2nd/3rd-copy (nusha2/nusha3) alignments too.
    The returned payload is backward-compatible:
      - payload["aligned"] is primary
      - payload["aligned_alt"] is nusha2 (optional)
      - payload["aligned_alt3"] is nusha3 (optional)
      - each primary aligned item may include item["alt"] for quick toggle in the viewer
    """
    if status_callback:
        status_callback("ALIGNMENT: Nüsha 1 hizalaması hazırlanıyor...", "INFO")
    primary = align_ocr_to_tahkik_segment_dp(
        docx_path,
        spellcheck_payload=spellcheck_payload,
        status_callback=status_callback,
        ocr_lines_override=None,
        write_json=True,
    )

    payload = dict(primary)
    payload["has_alt"] = False
    payload["aligned_alt"] = []
    payload["lines_count_alt"] = 0
    payload["has_alt3"] = False
    payload["aligned_alt3"] = []
    payload["lines_count_alt3"] = 0

    # Try to build alt alignment if nusha2 outputs exist
    try:
        if NUSHA2_LINES_MANIFEST.exists():
            alt_ocr_lines = load_ocr_lines_ordered(manifest_path=NUSHA2_LINES_MANIFEST, ocr_dir=NUSHA2_OCR_DIR)
        else:
            alt_ocr_lines = []
    except Exception:
        alt_ocr_lines = []

    if alt_ocr_lines:
        if status_callback:
            status_callback("ALIGNMENT: Nüsha 2 hizalaması hazırlanıyor...", "INFO")
        alt_payload = align_ocr_to_tahkik_segment_dp(
            docx_path,
            spellcheck_payload=spellcheck_payload,
            status_callback=status_callback,
            ocr_lines_override=alt_ocr_lines,
            write_json=False,
        )
        # Do NOT overwrite main alignment.json with alt-only payload; merge into combined payload.
        payload["has_alt"] = True
        payload["aligned_alt"] = alt_payload.get("aligned", []) if isinstance(alt_payload, dict) else []
        payload["lines_count_alt"] = alt_payload.get("lines_count", 0) if isinstance(alt_payload, dict) else 0

        # attach bidirectional alt links for fast viewer toggle in either direction
        try:
            _attach_bidirectional_alt_links(payload.get("aligned", []) or [], payload.get("aligned_alt", []) or [])
            _attach_overlap_alt_lists(payload.get("aligned", []) or [], payload.get("aligned_alt", []) or [], max_keep=6, field="alt_list")
            _attach_overlap_alt_lists(payload.get("aligned_alt", []) or [], payload.get("aligned", []) or [], max_keep=6, field="alt_list")
        except Exception:
            pass

        # Also compute OCR↔OCR links (more robust than tahkik-span overlap when one alignment drifts).
        # This populates item["ocr_alt_list"]/["ocr_alt_best"] which the viewer prefers.
            # Keep viewer usable even if OCR↔OCR cannot be computed.
            pass

        # Line Skip Detection (N1 vs N2)
        try:
            if status_callback:
                status_callback("Satır atlama analizi (N1 → N2)...", "INFO")
            
            # Check N1 lines against N2
            skips_n1 = detect_line_skips(payload.get("aligned", []), payload.get("aligned_alt", []), status_callback)
            if skips_n1:
                payload["skips_n1_vs_n2"] = skips_n1
                
            # Check N2 lines against N1 (reverse check)
            skips_n2 = detect_line_skips(payload.get("aligned_alt", []), payload.get("aligned", []), status_callback)
            if skips_n2:
                payload["skips_n2_vs_n1"] = skips_n2
                
        except Exception:
            pass


    # Try to build 3rd-copy alignment if nusha3 outputs exist
    try:
        if NUSHA3_LINES_MANIFEST.exists():
            alt3_ocr_lines = load_ocr_lines_ordered(manifest_path=NUSHA3_LINES_MANIFEST, ocr_dir=NUSHA3_OCR_DIR)
        else:
            alt3_ocr_lines = []
    except Exception:
        alt3_ocr_lines = []

    if alt3_ocr_lines:
        if status_callback:
            status_callback("ALIGNMENT: Nüsha 3 hizalaması hazırlanıyor...", "INFO")
        alt3_payload = align_ocr_to_tahkik_segment_dp(
            docx_path,
            spellcheck_payload=spellcheck_payload,
            status_callback=status_callback,
            ocr_lines_override=alt3_ocr_lines,
            write_json=False,
        )
        payload["has_alt3"] = True
        payload["aligned_alt3"] = alt3_payload.get("aligned", []) if isinstance(alt3_payload, dict) else []
        payload["lines_count_alt3"] = alt3_payload.get("lines_count", 0) if isinstance(alt3_payload, dict) else 0

        # N1 <-> N3 links (N1 uses alt3/alt3_list; N3 uses alt/alt_list pointing back to N1)
        try:
            _attach_bidirectional_named_links(payload.get("aligned", []) or [], payload.get("aligned_alt3", []) or [], field_a="alt3", field_b="alt")
            _attach_overlap_alt_lists(payload.get("aligned", []) or [], payload.get("aligned_alt3", []) or [], max_keep=6, field="alt3_list")
            _attach_overlap_alt_lists(payload.get("aligned_alt3", []) or [], payload.get("aligned", []) or [], max_keep=6, field="alt_list")
        except Exception:
            pass

        # Line Skip Detection (N1 vs N3)
        try:
            if status_callback:
                status_callback("Satır atlama analizi (N1 → N3)...", "INFO")
            skips_n1_n3 = detect_line_skips(payload.get("aligned", []), payload.get("aligned_alt3", []), status_callback)
            if skips_n1_n3:
                payload["skips_n1_vs_n3"] = skips_n1_n3
        except Exception:
            pass

        # N2 <-> N3 links (optional): N2 uses alt3/alt3_list; N3 uses alt2/alt2_list pointing back to N2
        try:
            if payload.get("has_alt") and isinstance(payload.get("aligned_alt"), list) and payload.get("aligned_alt"):
                _attach_bidirectional_named_links(payload.get("aligned_alt", []) or [], payload.get("aligned_alt3", []) or [], field_a="alt3", field_b="alt2")
                _attach_overlap_alt_lists(payload.get("aligned_alt", []) or [], payload.get("aligned_alt3", []) or [], max_keep=6, field="alt3_list")
                _attach_overlap_alt_lists(payload.get("aligned_alt3", []) or [], payload.get("aligned_alt", []) or [], max_keep=6, field="alt2_list")
        except Exception:
            pass

        # OCR↔OCR links (now includes N3 if present)
        try:
            attach_ocr_to_ocr_links(payload, status_callback=status_callback, max_keep=6)
        except Exception:
            pass

    # Try to build 4th-copy alignment if nusha4 outputs exist
    try:
        from src.config import NUSHA4_LINES_MANIFEST, NUSHA4_OCR_DIR
        if NUSHA4_LINES_MANIFEST.exists():
            alt4_ocr_lines = load_ocr_lines_ordered(manifest_path=NUSHA4_LINES_MANIFEST, ocr_dir=NUSHA4_OCR_DIR)
        else:
            alt4_ocr_lines = []
    except Exception:
        alt4_ocr_lines = []

    payload["has_alt4"] = False
    payload["aligned_alt4"] = []
    payload["lines_count_alt4"] = 0

    if alt4_ocr_lines:
        if status_callback:
            status_callback("ALIGNMENT: Nüsha 4 hizalaması hazırlanıyor...", "INFO")
        alt4_payload = align_ocr_to_tahkik_segment_dp(
            docx_path,
            spellcheck_payload=spellcheck_payload,
            status_callback=status_callback,
            ocr_lines_override=alt4_ocr_lines,
            write_json=False,
        )
        payload["has_alt4"] = True
        payload["aligned_alt4"] = alt4_payload.get("aligned", []) if isinstance(alt4_payload, dict) else []
        payload["lines_count_alt4"] = alt4_payload.get("lines_count", 0) if isinstance(alt4_payload, dict) else 0

        # N1 <-> N4 links
        try:
            _attach_bidirectional_named_links(payload.get("aligned", []) or [], payload.get("aligned_alt4", []) or [], field_a="alt4", field_b="alt")
            _attach_overlap_alt_lists(payload.get("aligned", []) or [], payload.get("aligned_alt4", []) or [], max_keep=6, field="alt4_list")
            _attach_overlap_alt_lists(payload.get("aligned_alt4", []) or [], payload.get("aligned", []) or [], max_keep=6, field="alt_list")
        except Exception:
            pass

        # Line Skip Detection (N1 vs N4)
        try:
            if status_callback:
                status_callback("Satır atlama analizi (N1 → N4)...", "INFO")
            skips_n1_n4 = detect_line_skips(payload.get("aligned", []), payload.get("aligned_alt4", []), status_callback)
            if skips_n1_n4:
                payload["skips_n1_vs_n4"] = skips_n1_n4
        except Exception:
            pass

        # N2 <-> N4 links (optional)
        try:
            if payload.get("has_alt") and isinstance(payload.get("aligned_alt"), list) and payload.get("aligned_alt"):
                _attach_bidirectional_named_links(payload.get("aligned_alt", []) or [], payload.get("aligned_alt4", []) or [], field_a="alt4", field_b="alt2")
                _attach_overlap_alt_lists(payload.get("aligned_alt", []) or [], payload.get("aligned_alt4", []) or [], max_keep=6, field="alt4_list")
                _attach_overlap_alt_lists(payload.get("aligned_alt4", []) or [], payload.get("aligned_alt", []) or [], max_keep=6, field="alt2_list")
        except Exception:
            pass

        # N3 <-> N4 links (optional)
        try:
            if payload.get("has_alt3") and isinstance(payload.get("aligned_alt3"), list) and payload.get("aligned_alt3"):
                _attach_bidirectional_named_links(payload.get("aligned_alt3", []) or [], payload.get("aligned_alt4", []) or [], field_a="alt4", field_b="alt3")
                _attach_overlap_alt_lists(payload.get("aligned_alt3", []) or [], payload.get("aligned_alt4", []) or [], max_keep=6, field="alt4_list")
                _attach_overlap_alt_lists(payload.get("aligned_alt4", []) or [], payload.get("aligned_alt3", []) or [], max_keep=6, field="alt3_list")
        except Exception:
            pass
            
        # OCR↔OCR links (now includes N4 if present)
        try:
            attach_ocr_to_ocr_links(payload, status_callback=status_callback, max_keep=6)
        except Exception:
            pass

    # Persist combined payload (overwrites alignment.json with multi info)
    try:
        ALIGNMENT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return payload


def detect_line_skips(
    lines_source: List[Dict[str, Any]],
    lines_target: List[Dict[str, Any]],
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect lines in source that have a consecutive block of 3 or more missing tokens 
    compared to the target. (User-requested logic: "yanyana 3 kelime ve daha fazla eksik")
    
    Returns a list of flagged items:
      [ { "line_no": ..., "ocr_text": ..., "max_consecutive_miss": 3, ... }, ... ]
    """
    try:
        if not lines_source or not lines_target:
            return []

        # 1. Flatten source to tokens
        src_tokens = []
        src_map = [] # global_token_index -> source_line_index
        
        for l_idx, item in enumerate(lines_source):
            txt = (item.get("ocr_text") or "") if isinstance(item, dict) else ""
            # We use simple split + normalize for token identity
            for w in txt.split():
                n = normalize_ar(w)
                if n:
                    src_tokens.append(n)
                    src_map.append(l_idx)
        
        # 2. Flatten target to tokens
        tgt_tokens = []
        for item in lines_target:
            txt = (item.get("ocr_text") or "") if isinstance(item, dict) else ""
            for w in txt.split():
                n = normalize_ar(w)
                if n:
                    tgt_tokens.append(n)
                    
        if not src_tokens or not tgt_tokens:
            return []

        # 3. Global Alignment
        # This gives us the edit operations to transform src -> tgt.
        # "equal" means the token exists in both.
        # "replace" or "delete" means the source token is missing/changed in target.
        matcher = Levenshtein.opcodes(src_tokens, tgt_tokens)
        
        # 4. Mark matched tokens
        is_matched = [False] * len(src_tokens)
        for tag, i1, i2, j1, j2 in matcher:
            if tag == "equal":
                for k in range(i1, i2):
                    is_matched[k] = True
                    
        # 5. Analyze consecutive misses per line
        # We'll compute the max_consecutive_miss for each line.
        line_miss_stats = {} # l_idx -> max_consecutive
        
        current_streak = 0
        prev_line = -1
        
        # We iterate through all source tokens. 
        # Whenever line changes, we reset streak.
        for i, matched in enumerate(is_matched):
            l_idx = src_map[i]
            
            if l_idx != prev_line:
                # New line started
                current_streak = 0
                prev_line = l_idx
            
            if not matched:
                current_streak += 1
            else:
                current_streak = 0
                
            # Update max for this line
            old_max = line_miss_stats.get(l_idx, 0)
            if current_streak > old_max:
                line_miss_stats[l_idx] = current_streak

        # 6. Flag lines with >= 3 consecutive misses
        flagged_skips = []
        for l_idx, max_miss in line_miss_stats.items():
            if max_miss >= 3:
                item = lines_source[l_idx]
                flagged_skips.append({
                    "line_no": item.get("line_no") if isinstance(item.get("line_no"), int) else (l_idx + 1),
                    "ocr_text": item.get("ocr_text", ""),
                    "max_consecutive_miss": max_miss,
                    "match_ratio": 0.0, # Deprecated but kept for schema compat if needed
                    "matched_tokens": 0,
                    "total_tokens": 0
                })
                
        return flagged_skips
        
    except Exception as e:
        if status_callback:
            status_callback(f"Satır atlama tespiti hatası: {e}", "WARNING")
        return []


def attach_ocr_to_ocr_links(
    payload: Dict[str, Any],
    status_callback: Optional[Callable[[str, str], None]] = None,
    max_keep: int = 6,
) -> Dict[str, Any]:
    """
    Compute OCR↔OCR alignments independent of tahkik.

    Backward compatible behavior (Nüsha 2):
      - N1 items: item["ocr_alt_list"] / ["ocr_alt_best"]   (points to N2)
      - N2 items: item["ocr_alt_list"] / ["ocr_alt_best"]   (points back to N1)

    Nüsha 3 behavior:
      - N1 items: item["ocr_alt3_list"] / ["ocr_alt3_best"] (points to N3)
      - N3 items: item["ocr_alt_list"] / ["ocr_alt_best"]   (points back to N1)

    If both N2 and N3 exist:
      - N2 items: item["ocr_alt3_list"] / ["ocr_alt3_best"] (points to N3)
      - N3 items: item["ocr_alt2_list"] / ["ocr_alt2_best"] (points to N2)
    """
    try:
        aligned1 = payload.get("aligned") if isinstance(payload, dict) else None
        if not isinstance(aligned1, list) or not aligned1:
            raise RuntimeError("alignment payload boş: 'aligned' yok.")

        aligned2 = payload.get("aligned_alt") if isinstance(payload, dict) else None
        if not isinstance(aligned2, list):
            aligned2 = []
        aligned3 = payload.get("aligned_alt3") if isinstance(payload, dict) else None
        if not isinstance(aligned3, list):
            aligned3 = []

        def _as_ocr_view(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for i, it in enumerate(lines):
                if not isinstance(it, dict):
                    continue
                out.append(
                    {
                        "line_no": it.get("line_no") if isinstance(it.get("line_no"), int) else (i + 1),
                        "line_image": it.get("line_image", "") or "",
                        "ocr_text": it.get("ocr_text", "") or "",
                    }
                )
            return out

        def _tokens_for_lines(lines: List[Dict[str, Any]]) -> Tuple[List[str], List[int]]:
            flat: List[str] = []
            t2l: List[int] = []
            for li, it in enumerate(lines):
                txt = (it.get("ocr_text") or "") if isinstance(it, dict) else ""
                toks = [normalize_ar(w) for w in txt.split()]
                for t in toks:
                    if not t:
                        continue
                    flat.append(t)
                    t2l.append(li)
            return flat, t2l

        def _pair_counts(lines_a: List[Dict[str, Any]], lines_b: List[Dict[str, Any]]) -> Dict[Tuple[int, int], int]:
            flat_a, t2l_a = _tokens_for_lines(lines_a)
            flat_b, t2l_b = _tokens_for_lines(lines_b)
            if not flat_a or not flat_b:
                return {}
            unique_words = sorted(list(set(flat_a + flat_b)))
            word2char = {w: chr(0xE000 + i) for i, w in enumerate(unique_words)}
            NULL_CHAR = chr(0xFFFF)
            s_a = "".join([word2char.get(w, NULL_CHAR) if w else NULL_CHAR for w in flat_a])
            s_b = "".join([word2char.get(w, NULL_CHAR) if w else NULL_CHAR for w in flat_b])
            opcodes = Levenshtein.opcodes(s_a, s_b)
            out: Dict[Tuple[int, int], int] = {}
            for tag, i1, i2, j1, j2 in opcodes:
                if tag != "equal":
                    continue
                n = i2 - i1
                for k in range(n):
                    a = t2l_a[i1 + k]
                    b = t2l_b[j1 + k]
                    key = (a, b)
                    out[key] = out.get(key, 0) + 1
            return out

        def _attach_lists(
            src_items: List[Dict[str, Any]],
            tgt_items: List[Dict[str, Any]],
            *,
            field_list: str,
            field_best: str,
            pair: Dict[Tuple[int, int], int],
        ) -> Tuple[List[List[Dict[str, Any]]], List[List[Dict[str, Any]]]]:
            # returns (src->tgt lists, tgt->src lists)
            src2tgt: List[List[Dict[str, Any]]] = [[] for _ in range(len(src_items))]
            tgt2src: List[List[Dict[str, Any]]] = [[] for _ in range(len(tgt_items))]

            hits_src: Dict[int, List[Tuple[int, int]]] = {}
            hits_tgt: Dict[int, List[Tuple[int, int]]] = {}
            for (a, b), c in pair.items():
                hits_src.setdefault(a, []).append((b, c))
                hits_tgt.setdefault(b, []).append((a, c))

            for a, lst in hits_src.items():
                lst.sort(key=lambda x: x[1], reverse=True)
                out_list: List[Dict[str, Any]] = []
                for b, c in lst[: max_keep]:
                    obj = tgt_items[b] if 0 <= b < len(tgt_items) else {}
                    out_list.append(
                        {
                            "line_no": obj.get("line_no") if isinstance(obj, dict) and obj.get("line_no") else (b + 1),
                            "line_image": (obj.get("line_image") or "") if isinstance(obj, dict) else "",
                            "ocr_text": (obj.get("ocr_text") or "") if isinstance(obj, dict) else "",
                            "overlap": c,
                        }
                    )
                if 0 <= a < len(src2tgt):
                    src2tgt[a] = out_list

            for b, lst in hits_tgt.items():
                lst.sort(key=lambda x: x[1], reverse=True)
                out_list = []
                for a, c in lst[: max_keep]:
                    obj = src_items[a] if 0 <= a < len(src_items) else {}
                    out_list.append(
                        {
                            "line_no": obj.get("line_no") if isinstance(obj, dict) and obj.get("line_no") else (a + 1),
                            "line_image": (obj.get("line_image") or "") if isinstance(obj, dict) else "",
                            "ocr_text": (obj.get("ocr_text") or "") if isinstance(obj, dict) else "",
                            "overlap": c,
                        }
                    )
                if 0 <= b < len(tgt2src):
                    tgt2src[b] = out_list

            for i, it in enumerate(src_items):
                if not isinstance(it, dict):
                    continue
                lst = src2tgt[i] if i < len(src2tgt) else []
                it[field_list] = lst
                it[field_best] = lst[0] if lst else None
            for i, it in enumerate(tgt_items):
                if not isinstance(it, dict):
                    continue
                lst = tgt2src[i] if i < len(tgt2src) else []
                it[field_list] = lst
                it[field_best] = lst[0] if lst else None

            return src2tgt, tgt2src

        # Load N2/N3 OCR from manifests (preferred, because it includes correct line_image paths)
        ocr2_lines: List[Dict[str, Any]] = []
        ocr3_lines: List[Dict[str, Any]] = []
        try:
            if NUSHA2_LINES_MANIFEST.exists():
                ocr2_lines = load_ocr_lines_ordered(manifest_path=NUSHA2_LINES_MANIFEST, ocr_dir=NUSHA2_OCR_DIR)
        except Exception:
            ocr2_lines = []
        try:
            if NUSHA3_LINES_MANIFEST.exists():
                ocr3_lines = load_ocr_lines_ordered(manifest_path=NUSHA3_LINES_MANIFEST, ocr_dir=NUSHA3_OCR_DIR)
        except Exception:
            ocr3_lines = []

        # N1<->N2 (backward compatible fields)
        if ocr2_lines:
            if status_callback:
                status_callback("OCR↔OCR: N1↔N2 token hizalama...", "INFO")
            lines1 = _as_ocr_view(aligned1)
            pair = _pair_counts(lines1, ocr2_lines)
            # Attach on N1 side to N2 using ocr_alt_list; on N2 aligned list back to N1 also using ocr_alt_list
            _attach_lists(aligned1, aligned2 if aligned2 else ocr2_lines, field_list="ocr_alt_list", field_best="ocr_alt_best", pair=pair)


        # N1<->N4
        try:
            from src.config import NUSHA4_LINES_MANIFEST, NUSHA4_OCR_DIR
            ocr4_lines: List[Dict[str, Any]] = []
            if NUSHA4_LINES_MANIFEST.exists():
                ocr4_lines = load_ocr_lines_ordered(manifest_path=NUSHA4_LINES_MANIFEST, ocr_dir=NUSHA4_OCR_DIR)
        except Exception:
            ocr4_lines = []

        aligned4 = payload.get("aligned_alt4") if isinstance(payload, dict) else None
        if not isinstance(aligned4, list):
            aligned4 = []

        if ocr4_lines and aligned4:
            if status_callback:
                status_callback("OCR↔OCR: N1↔N4 token hizalama...", "INFO")
            lines1 = _as_ocr_view(aligned1)
            pair = _pair_counts(lines1, ocr4_lines)
            src2tgt, tgt2src = _attach_lists(lines1, ocr4_lines, field_list="__tmp", field_best="__tmpb", pair=pair)
            for i, it in enumerate(aligned1):
                lst = src2tgt[i] if i < len(src2tgt) else []
                it["ocr_alt4_list"] = lst
                it["ocr_alt4_best"] = lst[0] if lst else None
            for i, it in enumerate(aligned4):
                lst = tgt2src[i] if i < len(tgt2src) else []
                it["ocr_alt_list"] = lst # points back to N1
                it["ocr_alt_best"] = lst[0] if lst else None

        # N2 <-> N4
        if ocr4_lines and aligned4 and ocr2_lines and aligned2:
            lines2 = _as_ocr_view(aligned2)
            pair = _pair_counts(lines2, ocr4_lines)
            src2tgt, tgt2src = _attach_lists(lines2, ocr4_lines, field_list="__tmp", field_best="__tmpb", pair=pair)
            for i, it in enumerate(aligned2):
                lst = src2tgt[i] if i < len(src2tgt) else []
                it["ocr_alt4_list"] = lst # N2 -> N4
                it["ocr_alt4_best"] = lst[0] if lst else None
            for i, it in enumerate(aligned4):
                lst = tgt2src[i] if i < len(tgt2src) else []
                it["ocr_alt2_list"] = lst # N4 -> N2
                it["ocr_alt2_best"] = lst[0] if lst else None

        # N3 <-> N4
        if ocr4_lines and aligned4 and ocr3_lines and aligned3:
            lines3 = _as_ocr_view(aligned3)
            pair = _pair_counts(lines3, ocr4_lines)
            src2tgt, tgt2src = _attach_lists(lines3, ocr4_lines, field_list="__tmp", field_best="__tmpb", pair=pair)
            for i, it in enumerate(aligned3):
                lst = src2tgt[i] if i < len(src2tgt) else []
                it["ocr_alt4_list"] = lst # N3 -> N4
                it["ocr_alt4_best"] = lst[0] if lst else None
            for i, it in enumerate(aligned4):
                lst = tgt2src[i] if i < len(tgt2src) else []
                it["ocr_alt3_list"] = lst # N4 -> N3
                it["ocr_alt3_best"] = lst[0] if lst else None

        # N1<->N3
        if ocr3_lines and aligned3:
            if status_callback:
                status_callback("OCR↔OCR: N1↔N3 token hizalama...", "INFO")
            lines1 = _as_ocr_view(aligned1)
            pair = _pair_counts(lines1, ocr3_lines)
            src2tgt, tgt2src = _attach_lists(lines1, ocr3_lines, field_list="__tmp", field_best="__tmpb", pair=pair)
            for i, it in enumerate(aligned1):
                lst = src2tgt[i] if i < len(src2tgt) else []
                it["ocr_alt3_list"] = lst
                it["ocr_alt3_best"] = lst[0] if lst else None
            for i, it in enumerate(aligned3):
                lst = tgt2src[i] if i < len(tgt2src) else []
                it["ocr_alt_list"] = lst
                it["ocr_alt_best"] = lst[0] if lst else None
            for it in ocr3_lines:
                if isinstance(it, dict):
                    it.pop("__tmp", None)
                    it.pop("__tmpb", None)

        # N2<->N3 (optional)
        if aligned2 and ocr3_lines and aligned3:
            if status_callback:
                status_callback("OCR↔OCR: N2↔N3 token hizalama...", "INFO")
            lines2 = _as_ocr_view(aligned2)
            pair = _pair_counts(lines2, ocr3_lines)
            src2tgt, tgt2src = _attach_lists(lines2, ocr3_lines, field_list="__tmp", field_best="__tmpb", pair=pair)
            for i, it in enumerate(aligned2):
                if not isinstance(it, dict):
                    continue
                lst = src2tgt[i] if i < len(src2tgt) else []
                it["ocr_alt3_list"] = lst
                it["ocr_alt3_best"] = lst[0] if lst else None
            for i, it in enumerate(aligned3):
                if not isinstance(it, dict):
                    continue
                lst = tgt2src[i] if i < len(tgt2src) else []
                it["ocr_alt2_list"] = lst
                it["ocr_alt2_best"] = lst[0] if lst else None
            for it in ocr3_lines:
                if isinstance(it, dict):
                    it.pop("__tmp", None)
                    it.pop("__tmpb", None)

        payload["has_ocr_ocr_links"] = True
        payload["ocr_ocr_max_keep"] = int(max_keep)
        if status_callback:
            status_callback("OCR↔OCR: eşleştirme tamamlandı (payload güncellendi).", "INFO")
        return payload
    except Exception as e:
        if status_callback:
            status_callback(f"OCR↔OCR eşleştirme hatası: {e}", "ERROR")
        raise
