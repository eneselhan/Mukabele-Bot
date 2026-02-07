# -*- coding: utf-8 -*-
"""
Word -> tahkik tokens + paragraphs
"""

from pathlib import Path
from typing import List
from docx import Document


def read_docx_paragraphs(docx_path: Path) -> List[str]:
    doc = Document(str(docx_path))
    paras = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            paras.append(t)
    return paras

def read_docx_text(docx_path: Path) -> str:
    paras = read_docx_paragraphs(docx_path)
    return "\n".join(paras).strip()

def tokenize_text(text: str) -> List[str]:
    return text.split()

