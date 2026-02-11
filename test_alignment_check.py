import json
from pathlib import Path

# Load alignment file
align_path = Path(r"c:\Users\Enes Elhan\Antigravity Projects\Tahkik-Bot-main\tahkik_data\projects\f8a82a08-8e78-47fc-a7b7-27e4a24da94e\nusha_1\alignment.json")

with open(align_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== ALIGNMENT CHECK ===\n")
print(f"Algorithm Version: {data.get('algo_version', 'N/A')}")
print(f"Total Lines: {data.get('lines_count', 'N/A')}")
print(f"Total Tahkik Words: {data.get('tahkik_word_count', 'N/A')}\n")

# Check first 10 lines
print("=== FIRST 10 LINES ===\n")
for i, line in enumerate(data['aligned'][:10]):
    ocr = line.get('ocr_text', '')
    ref = line.get('best', {}).get('raw', '')
    start = line.get('best', {}).get('start_word', 'N/A')
    end = line.get('best', {}).get('end_word', 'N/A')
    
    print(f"Line {line.get('line_no', i+1)}:")
    print(f"  OCR: {ocr[:80]}")
    print(f"  REF: {ref[:80]}")
    print(f"  Token Range: [{start}, {end})")
    
    # Check if sequential (problematic)
    if i > 0:
        prev_end = data['aligned'][i-1].get('best', {}).get('end_word', 0)
        if start == prev_end:
            print(f"  ⚠️  SEQUENTIAL! (previous end = {prev_end}, this start = {start})")
    print()
