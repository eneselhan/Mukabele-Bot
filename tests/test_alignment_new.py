
import sys
import os
from pathlib import Path
import json

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.alignment import align_texts

def test_alignment():
    print("Testing align_texts...")
    
    ocr_lines = [
        "Bismillahi",
        "Rahman",
        "", # Empty line
        "Raheem",
        "Maliki Yawm Deen"
    ]
    
    reference_text = "Bismillahi Ar-Rahman Ar-Raheem Maliki Yawmid-Deen"
    
    results = align_texts(ocr_lines, reference_text)
    
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Assertions
    assert len(results) == 5
    assert results[0]["aligned_text"].strip().startswith("Bismillahi")
    assert results[2]["status"] == "empty"
    assert results[3]["aligned_text"].strip() == "Ar-Raheem"
    
    print("\nTest Passed!")

if __name__ == "__main__":
    test_alignment()
