"""
Test script to re-run alignment with fixed anchor detection
"""
import sys
from pathlib import Path

# Make sure we're using the updated alignment.py
sys.path.insert(0, str(Path(__file__).parent))

from src.alignment import align_ocr_to_tahkik_segment_dp
from src.config import PROJECTS_DIR
import json

project_id = "f8a82a08-8e78-47fc-a7b7-27e4a24da94e"
nusha_dir = PROJECTS_DIR / project_id / "nusha_1"

# Load inputs
manifest_path = nusha_dir / "lines_manifest.json"
docx_path = PROJECTS_DIR / project_id / "tahkik.docx"

if not manifest_path.exists():
    print(f"ERROR: Manifest not found at {manifest_path}")
    sys.exit(1)

if not docx_path.exists():
    print(f"ERROR: Word doc not found at {docx_path}")
    sys.exit(1)

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

ocr_lines = manifest.get('lines', [])

print(f"=== RE-RUNNING ALIGNMENT WITH FIXED THRESHOLD ===")
print(f"OCR Lines: {len(ocr_lines)}")
print(f"Word Doc: {docx_path}")
print()

# Run alignment
result = align_ocr_to_tahkik_segment_dp(
    ocr_lines=ocr_lines,
    docx_path=str(docx_path),
    output_json_path=str(nusha_dir / "alignment_NEW.json")
)

print(f"\n=== RESULT ===")
print(f"Success: {result.get('success', False)}")
if result.get('success'):
    print(f"Lines: {result.get('lines', 0)}")
    print(f"Output: {result.get('output_path', 'N/A')}")
    
    # Quick check
    with open(nusha_dir / "alignment_NEW.json", 'r', encoding='utf-8') as f:
        new_data = json.load(f)
    
    giris_count = sum(1 for line in new_data['aligned'] if 'GİRİŞ KISMI' in line.get('best', {}).get('raw', ''))
    real_count = len(new_data['aligned']) - giris_count
    
    print(f"\n=== QUICK CHECK ===")
    print(f"Total Aligned: {len(new_data['aligned'])}")
    print(f"Giriş Kısmı: {giris_count}")
    print(f"Real Lines: {real_count}")
    
    # Show first real line
    for i, line in enumerate(new_data['aligned']):
        if 'GİRİŞ KISMI' not in line.get('best', {}).get('raw', ''):
            print(f"\nFirst Real Line (index {i}):")
            print(f"  OCR: {line.get('ocr_text', '')[:80]}")
            print(f"  REF: {line.get('best', {}).get('raw', '')[:80]}")
            print(f"  Token Range: [{line.get('best', {}).get('start_word')}, {line.get('best', {}).get('end_word')})")
            break
else:
    print(f"Error: {result.get('error', 'Unknown')}")
