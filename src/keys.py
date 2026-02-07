# -*- coding: utf-8 -*-
"""
API Key Management
"""

import os
from typing import List, Optional


# =========================
# KEY MANAGEMENT
# =========================
def get_google_vision_api_key() -> str:
    # Cloud Vision için ayrı key önerilir
    for k in ("GOOGLE_VISION_API_KEY", "VISION_API_KEY", "GOOGLE_API_KEY"):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    raise RuntimeError("Google Vision API Key bulunamadı. Env: GOOGLE_VISION_API_KEY ayarla.")


def get_gemini_api_key() -> str:
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    raise RuntimeError("Gemini API Key bulunamadı. Env: GEMINI_API_KEY ayarla.")


def get_google_access_token(scopes: Optional[List[str]] = None) -> str:
    """
    Get OAuth access token for Google Cloud APIs (Vertex AI).
    Uses Application Default Credentials:
      - GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
      - or 'gcloud auth application-default login'
    """
    scopes = scopes or ["https://www.googleapis.com/auth/cloud-platform"]
    try:
        gac = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
        if gac and not os.path.exists(gac):
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS dosyası bulunamadı.\n"
                f"  GOOGLE_APPLICATION_CREDENTIALS={gac}\n"
                "Dosya yolunu düzelt veya env'i kaldırıp 'gcloud auth application-default login' kullan."
            )
        # google-auth is the recommended way
        import google.auth  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore

        creds, _ = google.auth.default(scopes=scopes)
        creds.refresh(Request())
        tok = getattr(creds, "token", None)
        if not tok:
            raise RuntimeError("OAuth token alınamadı (google-auth credentials.token boş).")
        return str(tok)
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Vertex AI için google-auth paketi gerekli. Kurulum:\n"
            "  pip install google-auth\n"
            f"Detay: {e}"
        )
    except Exception as e:
        msg = str(e)
        # Common missing deps / ADC problems -> add actionable hints
        if "cryptography" in msg.lower():
            msg = (
                msg
                + "\n\nEksik bağımlılık: cryptography.\n"
                + "Kurulum: pip install cryptography\n"
            )
        if ("default credentials" in msg.lower()) or ("could not automatically determine credentials" in msg.lower()):
            msg = (
                msg
                + "\n\nGoogle ADC bulunamadı.\n"
                + "Seçenekler:\n"
                + "- Service account: GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json\n"
                + "- User ADC: gcloud auth application-default login\n"
            )
        raise RuntimeError(msg)


def get_openai_api_key() -> str:
    v = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not v:
        raise RuntimeError("OpenAI API Key bulunamadı. Env (OPENAI_API_KEY) ayarla.")
    return v


def get_claude_api_key() -> str:
    for k in ("CLAUDE_API_KEY", "ANTHROPIC_API_KEY"):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    raise RuntimeError("Claude API Key bulunamadı. Env: CLAUDE_API_KEY veya ANTHROPIC_API_KEY ayarla.")

