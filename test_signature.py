import json
from pathlib import Path
from docx import Document

# Load alignment to see what signature was created
align_path = Path(r"c:\Users\Enes Elhan\Antigravity Projects\Tahkik-Bot-main\tahkik_data\projects\f8a82a08-8e78-47fc-a7b7-27e4a24da94e\nusha_1\alignment.json")

with open(align_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== TAHKIK DOCUMENT INFO ===")
print(f"Total Tahkik Words: {data.get('tahkik_word_count', 'N/A')}")

tahkik_tokens = data.get('tahkik_tokens', [])
if tahkik_tokens:
    print(f"\nFirst 80 tokens (SIGNATURE):")
    print(" ".join(tahkik_tokens[:80]))
    
    print(f"\n\nFirst 10 OCR lines:")
    for i in range(min(10, len(data['aligned']))):
        line = data['aligned'][i]
        print(f"\nOCR Line {i}: {line.get('ocr_text', '')[:100]}")

# Also check the Word document directly
docx_path = Path(r"c:\Users\Enes Elhan\Antigravity Projects\Tahkik-Bot-main\tahkik_data\projects\f8a82a08-8e78-47fc-a7b7-27e4a24da94e\tahkik.docx")

if docx_path.exists():
    print("\n\n=== WORD DOCUMENT CONTENT ===")
    doc = Document(docx_path)
    text_parts = []
    for para in doc.paragraphs[:20]:  # First 20 paragraphs
        if para.text.strip():
            text_parts.append(para.text.strip())
    
    full_text = " ".join(text_parts)
    words = full_text.split()[:80]
    print(f"First 80 words from Word doc:")
    print(" ".join(words))
