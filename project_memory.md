# 🧠 Proje Hafızası ve API Rehberi

Bu dosya, projedeki API entegrasyonlarını, anahtar yönetimini ve özel çalışma yöntemlerini belgeleyen **hafıza** dosyasıdır. Geliştirme sürecinde "bunu nasıl yapıyorduk?" veya "hangi modeli kullanmalıyım?" soruları için tek doğruluk kaynağıdır.

## 🔑 API Anahtarları ve Yetkilendirme

Tüm hassas anahtarlar `.env` dosyasından veya environment variable'lardan (ortam değişkenleri) okunur. Kod içerisine **asla** hardcoded key yazılmaz.

### 1. Google Gemini (DeepMind)
- **Amaç:** Spellcheck (Tahkik), metin analizi, karmaşık dil işleme görevleri.
- **Yöntemler:** İki farklı sağlayıcı desteklenir (`GEMINI_PROVIDER` env ile seçilir):
    1.  **AI Studio (Varsayılan):** API Key tabanlı.
        -   **Env Değişkeni:** `GEMINI_API_KEY` veya `GOOGLE_API_KEY`
        -   **Varsayılan Model:** `gemini-3-pro-preview` (Env: `GEMINI_MODEL`)
    2.  **Vertex AI (Google Cloud):** OAuth / Service Account tabanlı.
        -   **Kimlik Doğrulama:** `GOOGLE_APPLICATION_CREDENTIALS` (JSON dosya yolu) veya `gcloud auth application-default login`.
        -   **Env Değişkenleri:** `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_GEMINI_MODEL` (varsayılan: `gemini-3-pro-preview`).

### 2. OpenAI
- **Amaç:** Arapça metin harekeleme (Tashkeel), TTS için metin hazırlığı (`tts_server.py` içinde `gpt-4o` kullanımı).
- **Yöntem:** API Key tabanlı.
- **Env Değişkeni:** `OPENAI_API_KEY`
- **Modeller:**
    -   Genel kullanım yapılandırılabilir: `OPENAI_MODEL` (varsayılan `gpt-5.2` olarak ayarlı ancak `tts_server.py` içinde `gpt-4o` hardcoded kullanılıyor!).
    -   **Özel Talimat:** `tts_server.py` içinde `vocalize_chunk_with_retry` fonksiyonu, metni harekelemek için `gpt-4o` kullanır ve Arapça dil uzmanı promtı ile çalışır.

### 3. Claude (Anthropic)
- **Amaç:** Yedek model veya alternatif dil işleme.
- **Yöntem:** API Key tabanlı.
- **Env Değişkeni:** `CLAUDE_API_KEY` veya `ANTHROPIC_API_KEY`
- **Model:** `CLAUDE_MODEL` (varsayılan: `claude-opus-4-5-20251101`)

### 4. Google Cloud Vision (OCR)
- **Amaç:** PDF sayfalarından metin okuma (OCR).
- **Yöntem:** API Key tabanlı (daha basit) veya Service Account.
- **Env Değişkeni:** `GOOGLE_VISION_API_KEY`, `VISION_API_KEY` veya `GOOGLE_API_KEY`.
- **Ayarlar:** `config.py` içinde timeout, retry ve backoff ayarları bulunur (`VISION_TIMEOUT`, `VISION_RETRIES`).

### 5. Google Cloud Text-to-Speech (TTS)
- **Amaç:** Metni sese çevirme ve zaman damgalarını (timepoints) alma.
- **Yöntem:** Service Account (Kimlik Doğrulama zorunlu).
- **Env Değişkeni:** `GOOGLE_APPLICATION_CREDENTIALS`
- **Kritik Detay:** Basit API Key ile çalışmaz, `google-auth` ve servis hesabı gerektirir.
- **Sunucu:** `src.tts_server` modülü ile yerel bir HTTP sunucusu (`http://127.0.0.1:8765`) olarak çalıştırılır çünkü tarayıcı (istemci) tarafında güvenli credential saklanamaz.

---

## 🛠️ Özel Çalışma Yöntemleri ve Notlar

### TTS Sunucusu (`src/tts_server.py`)
- **Neden Var?** HTML Viewer (`viewer.html`) doğrudan Google TTS API'sine güvenli bir şekilde bağlanamaz. Bu Python sunucusu bir proxy görevi görür.
- **Özellikleri:**
    -   **Uzun Cümle Bölme:** Google TTS limitlerine takılmamak için uzun metinleri cümle sonlarından böler (`split_into_three_by_sentences`).
    -   **Hareke Düzeltme (Vocalization):** Gönderilen metni önce OpenAI (`gpt-4o`) ile harekeler, sonra Google TTS'e gönderir. Orijinal metin ile OpenAI çıktısı arasında uyumsuzluk olursa kelime bazlı "fallback" mekanizması çalıştırır (`Levenshtein` mesafesi kullanarak).
    -   **Loglama:** Hata ayıklama için `test_output.html` ve `test_wordu.docx` dosyalarına detaylı log basar.

### Dosya Yapısı ve Çıktılar (`src/config.py`)
- **Çıktı Klasörü:** `output_lines/` ana çıktı dizinidir.
- **Nüsha Yönetimi:**
    -   Ana kopya: `output_lines/lines`, `output_lines/pages`
    -   2. Nüsha: `output_lines/nusha2/`
    -   3. Nüsha: `output_lines/nusha3/`
    -   4. Nüsha: `output_lines/nusha4/`
- **Amaç:** Farklı PDF versiyonlarını veya çalışmalarını birbirinin üzerine yazmadan saklamak.

### Arapça Normalizasyon
- **Kural:** Projede "Strict Arabic Normalization" kuralları geçerlidir.
- **Fonksiyon:** `normalize_arabic` (genellikle `utils.py` veya `tts_server.py` içinde).
- **Detay:** Sadece standart Arapça harfleri kabul eder, hareke, tatweel, noktalama ve diğer tüm sembolleri siler. Eşleştirmeler bu normalize edilmiş metin üzerinden yapılır.

---

## 🤖 Yapay Zeka Talimatları (AI Instructions)

1.  **Model Seçimi:** "Gemini kullan" denildiğinde varsayılan olarak `gemini-3-pro-preview` modelini anla. Eğer "Vertex" belirtilirse servis hesabı üzerinden işlem yap.
2.  **Hata Yönetimi:** API key eksikse `RuntimeError` fırlat ve hangi Env değişkeninin eksik olduğunu net bir şekilde söyle (`src/keys.py` içindeki mantığı koru).
3.  **Değişiklik Yaparken:** Yeni bir API eklerken `src/keys.py` dosyasına erişim fonksiyonunu ve `src/config.py` dosyasına varsayılan ayarlarını eklemeyi unutma.
4.  **Güvenlik:** Asla kodu commit ederken API key'leri dosya içine yazma. Her zaman `os.getenv` kullan.
