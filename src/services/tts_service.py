# -*- coding: utf-8 -*-
import base64
import json
import os
import re
import unicodedata
import datetime
from docx import Document
from typing import Any, Dict, Optional, Tuple, List
from rapidfuzz.distance import Levenshtein
from pathlib import Path
import threading

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from src.config import AUDIO_DIR, AUDIO_MANIFEST, DOC_ARCHIVES_DIR

# =============================================================================
# TTS Service Logic (Ported from tts_server.py)
# =============================================================================

class TTSService:
    def __init__(self):
        self._tts_client = None
        self._voices_cache = {}
        self._openai_client = None
        self.manifest_lock = threading.Lock()

    def _get_client(self):
        if self._tts_client is not None:
            return self._tts_client
        try:
            from google.cloud import texttospeech_v1beta1 as texttospeech
        except Exception as e:
            print(f"[TTS Service] google-cloud-texttospeech import error: {e}")
            return None
        self._tts_client = texttospeech.TextToSpeechClient()
        return self._tts_client

    def _get_openai_client(self):
        if self._openai_client:
            return self._openai_client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        if OpenAI is None:
            print("[TTS Service] OpenAI module not available.")
            return None
        self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def _pick_voice(self, language_code: str, gender: str, voice_name: Optional[str] = None) -> Tuple[str, Any]:
        from google.cloud import texttospeech_v1beta1 as texttospeech

        if voice_name:
            vp = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )
            return voice_name, vp

        cache_key = f"{language_code}"
        if cache_key not in self._voices_cache:
            client = self._get_client()
            if not client:
                return "", None
            try:
                resp = client.list_voices(language_code=language_code)
                self._voices_cache[cache_key] = resp.voices or []
            except Exception:
                self._voices_cache[cache_key] = []

        voices = self._voices_cache.get(cache_key) or []
        want = str(gender or "").upper().strip()
        want_gender = {
            "MALE": texttospeech.SsmlVoiceGender.MALE,
            "FEMALE": texttospeech.SsmlVoiceGender.FEMALE,
            "NEUTRAL": texttospeech.SsmlVoiceGender.NEUTRAL,
        }.get(want, texttospeech.SsmlVoiceGender.MALE)

        chosen = None
        for v in voices:
            try:
                if v and v.ssml_gender == want_gender:
                    chosen = v
                    break
            except Exception:
                continue

        if chosen is None and voices:
            chosen = voices[0]

        if chosen is not None:
            vp = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=getattr(chosen, "name", None) or None,
                ssml_gender=want_gender,
            )
            return getattr(chosen, "name", None) or "", vp

        vp = texttospeech.VoiceSelectionParams(language_code=language_code, ssml_gender=want_gender)
        return "", vp

    def normalize_arabic(self, text):
        # 1. Map Common Variants
        text = text.replace("ک", "ك")
        text = text.replace("ی", "ي")
        text = text.replace("ى", "ي")
        
        valid_chars = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
        pattern = f"[^{re.escape(valid_chars)}]"
        text = re.sub(pattern, '', text)
        return text

    def _count_stats(self, text: str) -> Tuple[int, int]:
        valid_letters = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
        tashkeel_pattern = r'[\u064B-\u0652\u0670]'
        letter_count = 0
        diacritic_count = 0
        for char in text:
            if char in valid_letters:
                letter_count += 1
            elif re.match(tashkeel_pattern, char):
                diacritic_count += 1
        return letter_count, diacritic_count

    def split_into_three_by_sentences(self, text: str) -> List[str]:
        if not text:
            return []
        pattern = r'([.!?;:؟؛\n]+)'
        parts = re.split(pattern, text)
        sentences = []
        current = ""
        for p in parts:
            if p and re.match(pattern, p):
                current += p
                sentences.append(current.strip())
                current = ""
            else:
                current += p
        if current.strip():
            sentences.append(current.strip())
        sentences = [s for s in sentences if s]
        
        if not sentences: return []
        if len(sentences) < 3: return sentences

        counts = [len(s.split()) for s in sentences]
        total_words = sum(counts)
        if total_words == 0: return sentences

        target1 = total_words / 3.0
        target2 = 2.0 * total_words / 3.0
        
        cumsum = []
        c = 0
        for x in counts:
            c += x
            cumsum.append(c)

        best_i = 0
        min_d = float('inf')
        search_end_1 = max(1, len(sentences) - 2) 
        for i in range(search_end_1 + 1):
            d = abs(cumsum[i] - target1)
            if d < min_d:
                min_d = d
                best_i = i
        
        best_j = best_i + 1
        min_d = float('inf')
        search_start_2 = best_i + 1
        search_end_2 = max(search_start_2, len(sentences) - 1)
        for j in range(search_start_2, search_end_2):
            d = abs(cumsum[j] - target2)
            if d < min_d:
                min_d = d
                best_j = j
                
        p1 = " ".join(sentences[:best_i+1])
        p2 = " ".join(sentences[best_i+1 : best_j+1])
        p3 = " ".join(sentences[best_j+1 :])
        
        return [p for p in [p1, p2, p3] if p]

    def _escape_xml(self, s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def vocalize_chunk_with_retry(self, text_chunk: str, log_file_path: str = "test_output.html", page_name: str = None) -> str:
        client = self._get_openai_client()
        if not client:
            return text_chunk
            
        model_name = "gpt-5.2" 
        max_retries = 3
        norm_original = self.normalize_arabic(text_chunk)
        vocalized_text = ""
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": (
                            "You are an expert Arabic linguist. "
                            "Your task is to add full diacritics (Tashkeel) AND correct/add proper punctuation to the following Arabic text. "
                            "Do NOT change any words or their order. "
                            "Return ONLY the fully vocalized and punctuated text."
                        )},
                        {"role": "user", "content": text_chunk}
                    ],
                    temperature=0
                )
                vocalized_text = response.choices[0].message.content
                if not vocalized_text: continue

                # Checks
                l_count, d_count = self._count_stats(vocalized_text)
                if l_count > 2 * d_count:
                    continue # Low diacritics

                norm_vocalized = self.normalize_arabic(vocalized_text)
                if norm_original != norm_vocalized:
                    break # Mismatch, don't retry, go to fallback

                return vocalized_text
            except Exception as e:
                print(f"[TTS Service] OpenAI Error: {e}")

        # Fallback (Simulated) - simplified for API service (skipping complex HTML logging for now to reduce bloat, or can add if critical)
        if not vocalized_text:
            return text_chunk
            
        ws_original = text_chunk.split()
        ws_vocalized = vocalized_text.split()
        norm_w_orig = [self.normalize_arabic(w) for w in ws_original]
        norm_w_voc = [self.normalize_arabic(w) for w in ws_vocalized]
        
        opcodes = Levenshtein.opcodes(norm_w_orig, norm_w_voc)
        final_words = []
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                for k in range(i2-i1): final_words.append(ws_vocalized[j1+k])
            elif tag == 'replace':
                for k in range(i2-i1): final_words.append(ws_original[i1+k])
            elif tag == 'delete':
                for k in range(i2-i1): final_words.append(ws_original[i1+k])
            elif tag == 'insert':
                pass # Ignore insertions
                
        return " ".join(final_words)

    def process_tts_request(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for TTS request processing.
        """
        try:
            from google.cloud import texttospeech_v1beta1 as texttospeech
        except:
             return {"error": "google-cloud-texttospeech not installed"}

        action = obj.get("action")
        page_key = obj.get("page_key")
        archive_path_name = obj.get("archive_path")
        
        # 1. Lazy Archive Lookup
        if action != "batch_save" and page_key and archive_path_name:
            # Simplified lookup logic (skipping strict NFC normalization loop for performance, assuming standard path)
            target_dir = DOC_ARCHIVES_DIR / archive_path_name
            if target_dir.exists():
                nusha_id = obj.get("nusha_id", 1)
                try: nusha_id = int(nusha_id)
                except: nusha_id = 1
                
                manifest_filename = f"audio_manifest_n{nusha_id}.json" if nusha_id > 1 else "audio_manifest.json"
                target_manifest = target_dir / manifest_filename
                
                if target_manifest.exists():
                    try:
                        manifest = json.loads(target_manifest.read_text(encoding="utf-8"))
                        if page_key in manifest:
                            chunks_data = manifest[page_key]
                            output_chunks = []
                            for c in chunks_data:
                                rel = c.get("audio_path")
                                if not rel: continue
                                full_path = target_dir / rel
                                if full_path.exists():
                                    b64 = base64.b64encode(full_path.read_bytes()).decode('utf-8')
                                    output_chunks.append({"audio_b64": b64, "timepoints": c.get("timepoints")})
                            
                            if output_chunks:
                                return {"chunks": output_chunks, "source": "archive_cache"}
                    except: pass
        
        if action == "check_only":
            return {"error": "Audio not prepared (check_only)", "status": 404}

        # 2. Synthesis
        ssml = (obj.get("ssml") or "").strip()
        tokens = obj.get("tokens")
        if tokens is not None and not isinstance(tokens, list): tokens = None
        
        if not ssml and not tokens:
             return {"error": "ssml or tokens is required", "status": 400}

        language_code = (obj.get("language_code") or "ar-XA").strip()
        gender = (obj.get("gender") or "MALE").strip()
        voice_name = obj.get("voice_name")
        speaking_rate = float(obj.get("speaking_rate", 1.0))
        
        client = self._get_client()
        if not client: return {"error": "TTS client unavailable", "status": 500}
        
        chosen_name, voice = self._pick_voice(language_code, gender, voice_name)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=speaking_rate)

        def _synth_one(ssml_text: str) -> Dict[str, Any]:
            synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
            req = texttospeech.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
                enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK],
            )
            resp = client.synthesize_speech(request=req)
            audio_b64 = base64.b64encode(resp.audio_content or b"").decode("ascii")
            tps = [{"mark": tp.mark_name, "time": float(tp.time_seconds)} for tp in (resp.timepoints or [])]
            return {"audio_b64": audio_b64, "timepoints": tps}

        if tokens:
            toks = [str(t).strip() for t in tokens if str(t).strip()]
            openai_chunk_size = 300
            final_chunks_output = []
            batch_files_created = []
            token_start = int(obj.get("token_start", 0))
            current_global_token_index = token_start
            
            for i in range(0, len(toks), openai_chunk_size):
                part = toks[i : i + openai_chunk_size]
                chunk_text_raw = " ".join(part)
                
                # Vocalize
                vocalized_text = self.vocalize_chunk_with_retry(chunk_text_raw, log_file_path="test_output.html", page_name=page_key)
                
                # Split for Google
                sub_chunks = self.split_into_three_by_sentences(vocalized_text)
                
                voc_idx_counter = 0
                for sc in sub_chunks:
                    sc_words = sc.split()
                    if not sc_words: continue
                    sc_ssml_fragments = []
                    for t in sc_words:
                        if voc_idx_counter < len(part):
                            real_idx = current_global_token_index + voc_idx_counter
                            mark = f'<mark name="w{real_idx}"/>'
                            voc_idx_counter += 1
                        else:
                            mark = ""
                        sc_ssml_fragments.append(f'{mark}{self._escape_xml(t)}')
                    
                    final_ssml = f"<speak>{' '.join(sc_ssml_fragments)}</speak>"
                    
                    try:
                        out = _synth_one(final_ssml)
                        
                        if action == "batch_save" and page_key:
                            # Save Logic
                            nusha_id = int(obj.get("nusha_id", 1))
                            if archive_path_name:
                                target_audio_dir = DOC_ARCHIVES_DIR / archive_path_name / "audio"
                                if nusha_id > 1: target_audio_dir = target_audio_dir / f"n{nusha_id}"
                            else:
                                target_audio_dir = AUDIO_DIR
                            
                            target_audio_dir.mkdir(parents=True, exist_ok=True)
                            filename = f"{page_key}_chunk_{len(batch_files_created)}.mp3"
                            file_path = target_audio_dir / filename
                            
                            with open(file_path, "wb") as f:
                                f.write(base64.b64decode(out["audio_b64"]))
                                
                            rel_prefix = f"audio/n{nusha_id}/" if nusha_id > 1 else "audio/"
                            batch_files_created.append({"audio_path": f"{rel_prefix}{filename}", "timepoints": out["timepoints"]})
                        else:
                            final_chunks_output.append(out)
                    except Exception as e:
                        print(f"Synth Error: {e}")

                current_global_token_index += len(part)

            if action == "batch_save" and page_key and batch_files_created:
                with self.manifest_lock:
                    nusha_id = int(obj.get("nusha_id", 1))
                    target_manifest = AUDIO_MANIFEST
                    if archive_path_name:
                        name = f"audio_manifest_n{nusha_id}.json" if nusha_id > 1 else "audio_manifest.json"
                        target_manifest = DOC_ARCHIVES_DIR / archive_path_name / name
                    
                    manifest = {}
                    if target_manifest.exists():
                         try: manifest = json.loads(target_manifest.read_text(encoding="utf-8"))
                         except: pass
                    manifest[page_key] = batch_files_created
                    target_manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
                
                return {"ok": True, "saved_chunks": batch_files_created}

            return {"chunks": final_chunks_output, "voice": chosen_name}

        # SSML only
        out = _synth_one(ssml)
        return {"audio_b64": out["audio_b64"], "timepoints": out["timepoints"], "voice": chosen_name}
