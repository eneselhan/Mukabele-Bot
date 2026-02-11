import json
from pathlib import Path

# Load alignment file
align_path = Path(r"c:\Users\Enes Elhan\Antigravity Projects\Tahkik-Bot-main\tahkik_data\projects\f8a82a08-8e78-47fc-a7b7-27e4a24da94e\nusha_1\alignment.json")

with open(align_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== CHECKING ALL LINES ===\n")

# Count how many are "GİRİŞ KISMI"
giris_count = 0
real_count = 0

for i, line in enumerate(data['aligned']):
    ref = line.get('best', {}).get('raw', '')
    if 'GİRİŞ KISMI' in ref:
        giris_count += 1
    else:
        real_count += 1
        if real_count <= 5:  # Show first 5 real lines
            print(f"Line {line.get('line_no', i+1)} (Index {i}):")
            print(f"  OCR: {line.get('ocr_text', '')[:100]}")
            print(f"  REF: {ref[:100]}")
            print(f"  Token Range: [{line.get('best', {}).get('start_word')}, {line.get('best', {}).get('end_word')})")
            print()

print(f"\n=== SUMMARY ===")
print(f"Total Lines: {len(data['aligned'])}")
print(f"Giriş Kısmı (Ignored): {giris_count}")
print(f"Real Aligned Lines: {real_count}")
print(f"\nTahkik Word Count: {data.get('tahkik_word_count', 'N/A')}")
