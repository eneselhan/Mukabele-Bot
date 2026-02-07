# -*- coding: utf-8 -*-
"""
Scoring (alignment) - Gelişmiş hassas benzerlik ölçümü
Birden fazla algoritma birleştirilerek en tutarlı sonuç üretilir.
"""

from typing import List, Set
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from src.config import W_MAIN, W_PREFIX


def _ngrams(s: str, n: int) -> List[str]:
    """Karakter n-gramları üretir."""
    if not s or n <= 0 or len(s) < n:
        return []
    return [s[i:i+n] for i in range(len(s) - n + 1)]


def _jaccard_ngrams(a: str, b: str, n: int) -> float:
    """Karakter n-gram Jaccard benzerliği (0-100)."""
    a = (a or "").replace(" ", "")
    b = (b or "").replace(" ", "")
    if not a or not b:
        return 0.0
    A = set(_ngrams(a, n))
    B = set(_ngrams(b, n))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    uni = len(A | B)
    if uni <= 0:
        return 0.0
    return 100.0 * inter / float(uni)


def _word_overlap_ratio(a: str, b: str) -> float:
    """Kelime kesişim oranı (0-100)."""
    wa = set((a or "").split())
    wb = set((b or "").split())
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    uni = len(wa | wb)
    if uni <= 0:
        return 0.0
    return 100.0 * inter / float(uni)


def _word_order_score(a: str, b: str) -> float:
    """
    Kelime sıra uyumu: ortak kelimeler aynı sırada mı?
    LCS benzeri yaklaşım (0-100).
    """
    wa = (a or "").split()
    wb = (b or "").split()
    if not wa or not wb:
        return 0.0
    
    # B'deki her kelimenin pozisyonunu bul
    b_pos = {}
    for i, w in enumerate(wb):
        if w not in b_pos:
            b_pos[w] = i
    
    # A'daki sırayla B'de eşleşenlerin pozisyon monotonluğu
    matched_positions = []
    for w in wa:
        if w in b_pos:
            matched_positions.append(b_pos[w])
    
    if len(matched_positions) < 2:
        return 50.0  # tek eşleşme varsa nötr
    
    # Kaç tanesi artan sırada?
    increasing = 0
    for i in range(1, len(matched_positions)):
        if matched_positions[i] >= matched_positions[i-1]:
            increasing += 1
    
    ratio = increasing / (len(matched_positions) - 1)
    return 100.0 * ratio


def _boundary_match_score(ocr_words: List[str], seg_words: List[str]) -> float:
    """
    İlk ve son kelimelerin eşleşme skoru (0-100).
    Satır sınırlarının doğru yakalanması için kritik.
    """
    if not ocr_words or not seg_words:
        return 0.0
    
    first_ocr = ocr_words[0]
    last_ocr = ocr_words[-1]
    first_seg = seg_words[0]
    last_seg = seg_words[-1]
    
    # İlk kelime benzerliği
    first_sim = fuzz.ratio(first_ocr, first_seg) if first_ocr and first_seg else 0
    # Son kelime benzerliği  
    last_sim = fuzz.ratio(last_ocr, last_seg) if last_ocr and last_seg else 0
    
    # Ağırlıklı ortalama (son kelime biraz daha önemli)
    return 0.45 * first_sim + 0.55 * last_sim


def _length_ratio_penalty(ocr_wc: int, seg_wc: int) -> float:
    """
    Kelime sayısı oranına göre ceza (0 = iyi, negatif = kötü).
    İdeal: seg_wc ≈ ocr_wc
    """
    if ocr_wc <= 0 or seg_wc <= 0:
        return 0.0
    
    ratio = seg_wc / ocr_wc
    
    if 0.7 <= ratio <= 1.4:
        return 0.0  # İdeal aralık, ceza yok
    elif ratio > 2.0:
        return -25.0  # Çok uzun segment
    elif ratio > 1.4:
        return -10.0 * (ratio - 1.4)  # Biraz uzun
    elif ratio < 0.5:
        return -20.0  # Çok kısa segment
    elif ratio < 0.7:
        return -8.0 * (0.7 - ratio) / 0.2  # Biraz kısa
    return 0.0


def _char_level_similarity(a: str, b: str) -> float:
    """
    Karakter seviyesi benzerlik ensemble:
    - Levenshtein normalize
    - Multiple n-gram Jaccard
    - Partial ratio
    """
    a_clean = (a or "").replace(" ", "")
    b_clean = (b or "").replace(" ", "")
    
    if not a_clean or not b_clean:
        return 0.0
    
    # Levenshtein normalized similarity
    lev_sim = 100.0 * Levenshtein.normalized_similarity(a_clean, b_clean)
    
    # N-gram Jaccard (2, 3, 4-gram)
    j2 = _jaccard_ngrams(a, b, 2)
    j3 = _jaccard_ngrams(a, b, 3)
    j4 = _jaccard_ngrams(a, b, 4)
    ngram_avg = (j2 + j3 + j4) / 3.0
    
    # Partial ratio (kısmen eşleşme)
    pr = fuzz.partial_ratio(a, b)
    
    # Weighted combination
    return 0.40 * lev_sim + 0.35 * ngram_avg + 0.25 * pr


def _token_level_similarity(a: str, b: str) -> float:
    """
    Token/kelime seviyesi benzerlik ensemble:
    - Token set ratio
    - Token sort ratio
    - Word overlap
    - Word order
    """
    if not a or not b:
        return 0.0
    
    tsr = fuzz.token_set_ratio(a, b)
    tsor = fuzz.token_sort_ratio(a, b)
    wov = _word_overlap_ratio(a, b)
    wor = _word_order_score(a, b)
    
    return 0.30 * tsr + 0.25 * tsor + 0.25 * wov + 0.20 * wor


def score_segment(ocr_norm: str, ocr_prefix_norm: str, seg_norm: str, seg_prefix_norm: str) -> int:
    """
    Gelişmiş hassas scoring - birden fazla algoritma birleştirilir.
    
    Bileşenler:
    1. Karakter seviyesi benzerlik (Levenshtein, n-gram, partial)
    2. Token seviyesi benzerlik (set/sort ratio, overlap, order)
    3. Sınır eşleşmesi (ilk/son kelime)
    4. Prefix eşleşmesi
    5. Uzunluk oranı cezası
    
    Returns: 0-100+ arası skor (100 = mükemmel eşleşme)
    """
    if not ocr_norm or not seg_norm:
        return 0
    
    ocr_words = ocr_norm.split()
    seg_words = seg_norm.split()
    ocr_wc = len(ocr_words)
    seg_wc = len(seg_words)
    
    # 1. Karakter seviyesi (0-100)
    char_sim = _char_level_similarity(ocr_norm, seg_norm)
    
    # 2. Token seviyesi (0-100)
    token_sim = _token_level_similarity(ocr_norm, seg_norm)
    
    # 3. Sınır eşleşmesi (0-100)
    boundary_sim = _boundary_match_score(ocr_words, seg_words)
    
    # 4. WRatio (genel fuzzy) (0-100)
    wratio = fuzz.WRatio(ocr_norm, seg_norm)
    
    # Ana skor: weighted ensemble
    main_score = (
        0.28 * char_sim +
        0.27 * token_sim +
        0.20 * boundary_sim +
        0.25 * wratio
    )
    
    # 5. Prefix bonus (satır başı uyumu)
    prefix_bonus = 0.0
    if ocr_prefix_norm and seg_prefix_norm:
        pref_char = _char_level_similarity(ocr_prefix_norm, seg_prefix_norm)
        pref_wr = fuzz.WRatio(ocr_prefix_norm, seg_prefix_norm)
        prefix_bonus = 0.5 * pref_char + 0.5 * pref_wr
    
    # 6. Uzunluk cezası
    len_penalty = _length_ratio_penalty(ocr_wc, seg_wc)
    
    # Final skor
    total = W_MAIN * main_score + W_PREFIX * prefix_bonus + len_penalty
    
    return int(round(total))


def score_segment_detailed(ocr_norm: str, seg_norm: str) -> dict:
    """
    Debug için detaylı skor breakdown.
    """
    if not ocr_norm or not seg_norm:
        return {"total": 0, "components": {}}
    
    ocr_words = ocr_norm.split()
    seg_words = seg_norm.split()
    
    char_sim = _char_level_similarity(ocr_norm, seg_norm)
    token_sim = _token_level_similarity(ocr_norm, seg_norm)
    boundary_sim = _boundary_match_score(ocr_words, seg_words)
    wratio = fuzz.WRatio(ocr_norm, seg_norm)
    len_pen = _length_ratio_penalty(len(ocr_words), len(seg_words))
    
    main = 0.28 * char_sim + 0.27 * token_sim + 0.20 * boundary_sim + 0.25 * wratio
    
    return {
        "total": int(round(main + len_pen)),
        "components": {
            "char_similarity": round(char_sim, 1),
            "token_similarity": round(token_sim, 1),
            "boundary_match": round(boundary_sim, 1),
            "wratio": wratio,
            "length_penalty": round(len_pen, 1),
            "main_score": round(main, 1),
        }
    }
