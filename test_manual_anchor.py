import json
from pathlib import Path
from rapidfuzz import fuzz
from src.utils import normalize_ar

# Load alignment
align_path = Path(r"c:\Users\Enes Elhan\Antigravity Projects\Tahkik-Bot-main\tahkik_data\projects\f8a82a08-8e78-47fc-a7b7-27e4a24da94e\nusha_1\alignment.json")

with open(align_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

tahkik_tokens = data.get('tahkik_tokens', [])

# Create signature
signature_tokens = [normalize_ar(t) for t in tahkik_tokens[:80] if t and len(t) > 1]
signature_str = "".join(signature_tokens)

print("=== SIGNATURE ===")
print(f"First 80 words from signature:\n{' '.join(signature_tokens[:30])}\n")

# Now scan OCR lines
print("=== SCANNING OCR LINES FOR MATCH ===\n")

window_size = 15
aligned_lines = data['aligned']

best_matches = []

for i in range(min(200, len(aligned_lines))):
    # Build window
    window_tokens = []
    for k in range(i, min(i + window_size, len(aligned_lines))):
        txt = aligned_lines[k].get("ocr_text", "") or ""
        clean_tokens = [normalize_ar(w) for w in txt.split() if len(w) > 1]
        window_tokens.extend(clean_tokens)
    
    window_str = "".join(window_tokens)
    
    if not window_str:
        continue
    
    # Calculate similarity
    ratio = fuzz.partial_ratio(signature_str, window_str) / 100.0
    
    if ratio > 0.4:  # Show any decent match
        best_matches.append((i, ratio, " ".join(window_tokens[:15])))

# Sort by score
best_matches.sort(key=lambda x: x[1], reverse=True)

print("Top 10 matches:")
for idx, score, preview in best_matches[:10]:
    print(f"\nLine {idx}: Score {score:.3f}")
    print(f"  Preview: {preview}")
