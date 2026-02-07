# -*- coding: utf-8 -*-
"""
Kraken Satır Böl + Goo
e Vision OCR + Tahkik (Word) Satır-Satır Hizalama
+ Tahkik imla kontrolü (Gemini + OpenAI GPT-5.2) ve hataları vurgulama
+ Hatalara hızlı git butonları (viewer.html)

ÖNEMLİ:
- Google Vision API Key environment'ten okunur.
- Gemini API Key environment'ten okunur (spellcheck için).
- OpenAI API Key environment'ten okunur (OPENAI_API_KEY).

Önerilen env değişkenleri:
  export GOOGLE_VISION_API_KEY="..."   # Cloud Vision için
  export GEMINI_API_KEY="..."          # Gemini spellcheck için
  export OPENAI_API_KEY="..."          # OpenAI spellcheck için

Çalıştır:
  python main.py
"""

from dotenv import load_dotenv
load_dotenv()

from src.gui import start_gui


if __name__ == "__main__":
    start_gui()
