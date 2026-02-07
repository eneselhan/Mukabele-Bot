# -*- coding: utf-8 -*-
"""
GUI
"""

import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog
from pathlib import Path
import traceback
from datetime import datetime
import threading
import json
from typing import Optional
from src.config import (
    DPI_DEFAULT, ENABLE_SPELLCHECK_DEFAULT, VIEWER_HTML, ALIGNMENT_JSON,
    SPELLCHECK_JSON, OUT, LINES_MANIFEST, DOC_ARCHIVES_DIR,
    NUSHA2_OUT, NUSHA2_PAGES_DIR, NUSHA2_LINES_DIR, NUSHA2_OCR_DIR, NUSHA2_LINES_MANIFEST,
    NUSHA3_OUT, NUSHA3_PAGES_DIR, NUSHA3_LINES_DIR, NUSHA3_OCR_DIR, NUSHA3_LINES_MANIFEST, NUSHA3_VIEWER_HTML,
    NUSHA4_OUT, NUSHA4_PAGES_DIR, NUSHA4_LINES_DIR, NUSHA4_OCR_DIR, NUSHA4_LINES_MANIFEST, NUSHA4_VIEWER_HTML
)
from src.services.alignment_service import AlignmentService
from src.keys import get_google_vision_api_key, get_gemini_api_key, get_openai_api_key, get_claude_api_key
from src.utils import (
    hard_cleanup_output,
    check_pages_exist, check_lines_exist, check_ocr_exist,
    check_spellcheck_exist, check_alignment_exist
)
#
# NOTE: Heavy optional dependencies (Pillow / kraken / pypdfium2 / etc.) are imported
# lazily inside stage handlers so the GUI can still start and show a clear error
# message even if some packages are missing.
#


# =========================
# GUI
# =========================
def start_gui():
    root = tk.Tk()
    root.title("Kraken Satir Bol + Vision OCR + Satir Satir Hizalama")
    # Start fullscreen every time (user request)
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        pass
    # Esc to exit fullscreen (safe on macOS)
    try:
        root.bind("<Escape>", lambda _e: root.attributes("-fullscreen", False))
    except Exception:
        pass
    # Keep a reasonable default size if fullscreen is turned off later
    root.geometry("1000x850")
    root.minsize(980, 760)

    # Font ayarları
    default_font_size = 16
    font_size_var = tk.IntVar(value=default_font_size)

    # Modern ttk tema/stil
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Scrollable sol panel için canvas referansı (update_fonts içinde arka planı güncellemek için)
    left_canvas = None

    def update_fonts(size):
        """Tüm arayüz fontlarını güncelle"""
        size = int(size)
        base_font = ("Arial", size)
        small_font = ("Arial", max(11, size - 2))
        mono_font = ("Courier", max(10, size - 3))

        # Renk paleti (light, modern)
        bg = "#F6F7FB"
        card = "#FFFFFF"
        border = "#E5E7EB"
        text = "#111827"
        muted = "#6B7280"
        accent = "#2563EB"
        accent_hover = "#1D4ED8"

        root.configure(bg=bg)

        # TTK temel stiller
        style.configure(".", font=base_font, foreground=text)
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card, relief="flat")
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("Card.TLabel", background=card, foreground=text)
        style.configure("TLabelframe", background=bg, bordercolor=border)
        style.configure("TLabelframe.Label", background=bg, foreground=text, font=small_font)

        style.configure("TButton", padding=(12, 8))
        style.map("TButton", foreground=[("disabled", muted)])

        style.configure("Accent.TButton", padding=(12, 10), foreground="#FFFFFF", background=accent)
        style.map(
            "Accent.TButton",
            background=[("active", accent_hover), ("pressed", accent_hover), ("disabled", border)],
            foreground=[("disabled", muted)],
        )

        style.configure("TRadiobutton", background=bg)
        style.configure("TCheckbutton", background=bg)

        style.configure("Monospace.TLabel", font=mono_font, background=card, foreground=text)

        # Text log özel (tk widget)
        try:
            if log_text:
                log_text.configure(font=mono_font)
        except Exception:
            pass
        # Sol panel canvas bg
        try:
            if left_canvas is not None:
                left_canvas.configure(bg=bg, highlightthickness=0)
        except Exception:
            pass

        # Legacy tk widget'lar kalırsa diye minimal recursion
        for widget in root.winfo_children():
            update_widget_font(widget, base_font, small_font, mono_font)
    
    def update_widget_font(widget, font_tuple, small_font, mono_font):
        """Widget ve alt widget'ların fontlarını güncelle"""
        try:
            if isinstance(widget, (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton)):
                widget.config(font=font_tuple)
            elif isinstance(widget, tk.Entry):
                widget.config(font=font_tuple)
            elif isinstance(widget, scrolledtext.ScrolledText):
                widget.config(font=mono_font)
        except Exception:
            pass
        
        # Alt widget'ları da güncelle
        for child in widget.winfo_children():
            update_widget_font(child, font_tuple, small_font, mono_font)

    pdf_var = tk.StringVar(value="")
    pdf2_var = tk.StringVar(value="")
    pdf3_var = tk.StringVar(value="")
    pdf4_var = tk.StringVar(value="")
    dpi_var = tk.StringVar(value=str(DPI_DEFAULT))

    ocr_var = tk.BooleanVar(value=True)
    docx_var = tk.StringVar(value="")
    align_var = tk.BooleanVar(value=True)
    
    # AI model seçimi: "none", "gemini", "openai", "claude", "both", "all"
    ai_model_var = tk.StringVar(value="both")
    # Spellcheck her zaman append modunda çalışır (eski sonuçlar korunur)
    # Spellcheck başlangıç paragrafı (1-based)
    sc_start_para_var = tk.IntVar(value=1)
    # Seçili paragraf listesi (1-based). None => tüm paragraflar.
    sc_selected_paras = {"indices": None}
    # AI API trace penceresi aç + çıktı olarak kaydet
    sc_verbose_ai_var = tk.BooleanVar(value=False)

    def _open_ai_trace_window() -> dict:
        """
        Returns a dict with:
          - win: Toplevel
          - text: ScrolledText
          - lines: list[str]
          - trace_path: Path
          - alive: threading.Event (set while UI exists)
        """
        from src.config import OUT

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        trace_path = OUT / f"ai_trace_spellcheck_{ts}.txt"

        win = tk.Toplevel(root)
        win.title("AI API Trace (Spellcheck)")
        win.geometry("980x720")

        # prevent user from killing it mid-run; we'll close automatically
        alive = threading.Event()
        alive.set()

        def _on_close():
            # allow closing but keep collecting to file; just hide UI
            try:
                alive.clear()
            except Exception:
                pass
            try:
                win.withdraw()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _on_close)

        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=10, pady=(10, 6))
        ttk.Label(top, text="Spellcheck sırasında her AI çağrısı için giden PROMPT + gelen RAW RESPONSE burada akar.").pack(anchor="w")
        ttk.Label(top, text=f"Kayıt: {trace_path}", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        text = scrolledtext.ScrolledText(
            win,
            height=20,
            wrap=tk.WORD,
            bg="#0B1220",
            fg="#E5E7EB",
            insertbackground="#E5E7EB",
            relief="flat",
            borderwidth=0,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        text.insert(tk.END, "=== AI API TRACE BAŞLADI ===\n")
        text.see(tk.END)

        return {"win": win, "text": text, "lines": [], "trace_path": trace_path, "alive": alive}

    def _make_ai_trace_callback(trace_state: dict):
        """Thread-safe callback for spellcheck.debug_callback that also collects for saving."""
        def _cb(message: str, level: str = "INFO"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            line = f"[{timestamp}] [{level}] {message}\n"
            try:
                trace_state["lines"].append(line)
            except Exception:
                pass

            def _ui():
                try:
                    if trace_state.get("alive") is not None and trace_state["alive"].is_set():
                        txt = trace_state.get("text")
                        if txt:
                            txt.insert(tk.END, line)
                            txt.see(tk.END)
                except Exception:
                    pass

            root.after(0, _ui)

        return _cb

    # Aşama durumları
    stage_status = {
        # Nüsha 1
        "pages": tk.StringVar(value="Bekliyor"),
        "lines": tk.StringVar(value="Bekliyor"),
        "ocr": tk.StringVar(value="Bekliyor"),
        "spellcheck": tk.StringVar(value="Bekliyor"),
        "alignment": tk.StringVar(value="Bekliyor"),
        "viewer": tk.StringVar(value="Bekliyor"),
        # Nüsha 2
        "pages2": tk.StringVar(value="Bekliyor"),
        "lines2": tk.StringVar(value="Bekliyor"),
        "ocr2": tk.StringVar(value="Bekliyor"),
        "alignment2": tk.StringVar(value="Bekliyor"),
        "viewer2": tk.StringVar(value="Bekliyor"),
        # Nüsha 3
        "pages3": tk.StringVar(value="Bekliyor"),
        "lines3": tk.StringVar(value="Bekliyor"),
        "ocr3": tk.StringVar(value="Bekliyor"),
        "alignment3": tk.StringVar(value="Bekliyor"),
        "viewer3": tk.StringVar(value="Bekliyor"),
        # Nüsha 4
        "pages4": tk.StringVar(value="Bekliyor"),
        "lines4": tk.StringVar(value="Bekliyor"),
        "ocr4": tk.StringVar(value="Bekliyor"),
        "alignment4": tk.StringVar(value="Bekliyor"),
        "viewer4": tk.StringVar(value="Bekliyor"),
    }

    # Aşama sonuçlarını sakla
    stage_results = {
        "pages_count": 0,
        "lines_count": 0,
        "sc_payload": None,
        "alignment_payload": None,
    }

    # Log alanı
    log_text = None
    log_auto_scroll_var = tk.BooleanVar(value=True)

    def choose_pdf():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            pdf_var.set(path)

    def choose_pdf2():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")], title="2. Nüsha PDF seç")
        if path:
            pdf2_var.set(path)
            log_message(f"2. Nüsha PDF seçildi: {path}", "INFO")

    def choose_pdf3():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")], title="3. Nüsha PDF seç")
        if path:
            pdf3_var.set(path)
            log_message(f"3. Nüsha PDF seçildi: {path}", "INFO")

    def choose_pdf4():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")], title="4. Nüsha PDF seç")
        if path:
            pdf4_var.set(path)
            log_message(f"4. Nüsha PDF seçildi: {path}", "INFO")

    def choose_docx():
        path = filedialog.askopenfilename(filetypes=[("Word (.docx)", "*.docx")])
        if path:
            docx_var.set(path)

    def log_message(message: str, level: str = "INFO"):
        """Log mesajı ekle (thread-safe)"""
        def _log():
            if log_text:
                timestamp = datetime.now().strftime("%H:%M:%S")
                prefix = f"[{timestamp}] [{level}]"
                log_text.insert(tk.END, f"{prefix} {message}\n")
                if log_auto_scroll_var.get():
                    log_text.see(tk.END)
                root.update_idletasks()
        
        # Ana thread'de çalıştır
        root.after(0, _log)

    # -------------------------
    # Local TTS server (Google Cloud proxy) for viewer
    # -------------------------
    try:
        _tts_started = {"ok": False}

        def _start_tts_server_once():
            if _tts_started["ok"]:
                return
            _tts_started["ok"] = True
            try:
                from src.tts_server import serve

                def _run():
                    try:
                        serve(host="127.0.0.1", port=8765)
                    except Exception as e:
                        log_message(f"TTS server başlatılamadı: {e}", "WARNING")

                th = threading.Thread(target=_run, daemon=True)
                th.start()
                log_message("TTS server başlatıldı: http://127.0.0.1:8765/tts", "INFO")
            except Exception as e:
                log_message(f"TTS server import edilemedi: {e}", "WARNING")

        _start_tts_server_once()
    except Exception:
        pass

    def update_stage_status(stage_key: str, status: str):
        """Aşama durumunu güncelle (thread-safe)"""
        def _update():
            if stage_key in stage_status:
                stage_status[stage_key].set(status)
                root.update_idletasks()
        
        # Ana thread'de çalıştır
        root.after(0, _update)

    def validate_inputs():
        """Giriş parametrelerini kontrol et"""
        if not pdf_var.get():
            messagebox.showerror("Hata", "PDF secilmedi.")
            return False

        try:
            dpi = int(dpi_var.get().strip())
            if dpi < 100 or dpi > 600:
                raise ValueError
        except Exception:
            messagebox.showerror("Hata", "DPI 100-600 arasi bir sayi olmali (orn: 300).")
            return False

        return True

    # =========================
    # Nüsha 2 helpers
    # =========================
    def _check_pages_exist_dir(pages_dir: Path) -> tuple[bool, int]:
        try:
            pages = list(pages_dir.glob("*.png"))
            return (len(pages) > 0, len(pages))
        except Exception:
            return (False, 0)

    def _check_lines_exist_dir(lines_dir: Path, manifest_path: Path) -> tuple[bool, int]:
        try:
            lines = list(lines_dir.glob("*.png"))
            return (len(lines) > 0 and manifest_path.exists(), len(lines))
        except Exception:
            return (False, 0)

    def _check_ocr_exist_dir(ocr_dir: Path) -> tuple[bool, int]:
        try:
            ocr_files = list(ocr_dir.glob("*.txt"))
            return (len(ocr_files) > 0, len(ocr_files))
        except Exception:
            return (False, 0)

    def validate_inputs2() -> bool:
        """Nüsha 2 için PDF + DPI kontrolü"""
        if not pdf2_var.get().strip():
            messagebox.showerror("Hata", "2. Nüsha PDF seçilmedi.")
            return False
        try:
            dpi = int(dpi_var.get().strip())
            if dpi < 100 or dpi > 600:
                raise ValueError
        except Exception:
            messagebox.showerror("Hata", "DPI 100-600 arası bir sayı olmalı (örn: 300).")
            return False
        return True

    def run_pages2():
        """AŞAMA: Pages (Nüsha 2)"""
        def _run():
            if not validate_inputs2():
                return False
            update_stage_status("pages2", "Çalışıyor...")
            log_message("PAGES (N2): PDF işleniyor (PNG'e dönüştürülüyor)...")
            try:
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf2_var.get()), dpi=dpi, pages_dir=NUSHA2_PAGES_DIR)
                log_message(f"✓ PAGES (N2) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages2", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (PAGES N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - PAGES (Nüsha 2)", f"PDF işleme sırasında hata:\n{e}"))
                update_stage_status("pages2", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_lines2():
        """AŞAMA: Lines (Nüsha 2)"""
        def _run():
            pages_exist, pages_count = _check_pages_exist_dir(NUSHA2_PAGES_DIR)
            if not pages_exist:
                log_message("HATA: Nüsha 2 sayfa PNG'leri bulunamadı. Önce PAGES (N2) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 2 sayfa PNG'leri bulunamadı. Önce PAGES (N2) çalıştırın."))
                update_stage_status("lines2", "Hata!")
                return False

            update_stage_status("lines2", "Çalışıyor...")
            log_message(f"LINES (N2): {pages_count} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
            try:
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA2_LINES_MANIFEST.exists():
                    NUSHA2_LINES_MANIFEST.unlink()
                with NUSHA2_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA2_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N2) Sayfa {idx + 1}/{pages_count} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA2_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA2_LINES_MANIFEST)
                log_message(f"✓ LINES (N2) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines2", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (LINES N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - LINES (Nüsha 2)", f"Satır segmentasyonu sırasında hata:\n{e}"))
                update_stage_status("lines2", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_ocr2():
        """AŞAMA: OCR (Nüsha 2)"""
        def _run():
            if not ocr_var.get():
                ocr_exist, ocr_count = _check_ocr_exist_dir(NUSHA2_OCR_DIR)
                if ocr_exist:
                    log_message(f"OCR (N2) atlandı (kapalı) ama {ocr_count} mevcut OCR dosyası bulundu.", "INFO")
                    update_stage_status("ocr2", f"Mevcut ({ocr_count})")
                else:
                    log_message("OCR (N2) atlandı (kapalı)", "INFO")
                    update_stage_status("ocr2", "Atlandı")
                return True

            lines_exist, lines_count = _check_lines_exist_dir(NUSHA2_LINES_DIR, NUSHA2_LINES_MANIFEST)
            if not lines_exist:
                log_message("HATA: Nüsha 2 satır kayıtları bulunamadı. Önce LINES (N2) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 2 satır kayıtları bulunamadı. Önce LINES (N2) çalıştırın."))
                update_stage_status("ocr2", "Hata!")
                return False

            update_stage_status("ocr2", "Çalışıyor...")
            log_message(f"OCR (N2): Google Vision OCR yapılıyor... ({lines_count} satır)", "INFO")
            try:
                from src.kraken_processor import load_line_records_ordered
                from src.ocr import ocr_lines_with_google_vision_api
                recs = load_line_records_ordered(manifest_path=NUSHA2_LINES_MANIFEST)
                ordered_line_paths = [Path(r["line_image"]) for r in recs]
                vkey = get_google_vision_api_key()
                from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                ok, total = ocr_lines_with_google_vision_api(
                    ordered_line_paths,
                    api_key=vkey,
                    timeout=VISION_TIMEOUT,
                    retries=VISION_RETRIES,
                    backoff_base=VISION_BACKOFF_BASE,
                    max_dim=VISION_MAX_DIM,
                    jpeg_quality=VISION_JPEG_QUALITY,
                    sleep_s=0.10,
                    status_callback=log_message,
                    ocr_dir=NUSHA2_OCR_DIR,
                )
                log_message(f"✓ OCR (N2) tamamlandı: {ok}/{total} başarılı", "INFO")
                update_stage_status("ocr2", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (OCR N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - OCR (Nüsha 2)", f"OCR sırasında hata:\n{e}"))
                update_stage_status("ocr2", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_alignment2():
        """AŞAMA: Alignment (Nüsha 2) - N2 çıktılarını da içeren hizalamayı üret"""
        def _run():
            if not docx_var.get().strip():
                root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) seçilmedi."))
                return False

            # N2 OCR/lines exist?
            l2_exist, _ = _check_lines_exist_dir(NUSHA2_LINES_DIR, NUSHA2_LINES_MANIFEST)
            if not l2_exist:
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 2 satırları yok. Önce Pages/Lines/OCR (N2) çalıştırın."))
                update_stage_status("alignment2", "Hata!")
                return False

            update_stage_status("alignment2", "Çalışıyor...")
            log_message("ALIGNMENT (N2): Nüsha 2 hizalaması (ve birleşik payload) hazırlanıyor...", "INFO")
            try:
                from src.alignment import align_ocr_to_tahkik_segment_dp_multi
                payload = align_ocr_to_tahkik_segment_dp_multi(
                    Path(docx_var.get()),
                    spellcheck_payload=stage_results["sc_payload"],
                    status_callback=log_message,
                )
                stage_results["alignment_payload"] = payload
                update_stage_status("alignment2", "✓ Tamamlandı")
                log_message("✓ ALIGNMENT (N2) tamamlandı", "INFO")
                return True
            except Exception as e:
                log_message(f"HATA (ALIGNMENT N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - ALIGNMENT (Nüsha 2)", f"Hizalama sırasında hata:\n{e}"))
                update_stage_status("alignment2", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_pages():
        """AŞAMA: Pages - PDF'den PNG'e dönüştürme"""
        def _run():
            if not validate_inputs():
                return False
            
            update_stage_status("pages", "Çalışıyor...")
            log_message("PAGES: PDF işleniyor (PNG'e dönüştürülüyor)...")
            
            try:
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf_var.get()), dpi=dpi)
                log_message(f"✓ PAGES tamamlandı: {len(pages)} sayfa PNG'e dönüştürüldü")
                update_stage_status("pages", "✓ Tamamlandı")
                stage_results["pages_count"] = len(pages)
                return True
            except Exception as e:
                log_message(f"HATA (PAGES): PDF işleme sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - PAGES", f"PDF işleme sırasında hata oluştu:\n{e}"))
                update_stage_status("pages", "Hata!")
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_lines():
        """AŞAMA: Lines - Sayfaları satırlara bölme"""
        def _run():
            # Önce mevcut dosyaları kontrol et
            pages_exist, pages_count = check_pages_exist()
            if not pages_exist:
                log_message("HATA: Sayfa PNG'leri bulunamadı. Önce PAGES aşamasını çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Sayfa PNG'leri bulunamadı. Önce PAGES aşamasını çalıştırın."))
                update_stage_status("lines", "Hata!")
                return False
            
            update_stage_status("lines", "Çalışıyor...")
            log_message(f"LINES: {pages_count} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...")
            
            try:
                from src.kraken_processor import split_page_to_lines
                # Pages klasöründeki tüm PNG'leri bul
                from src.config import PAGES_DIR
                page_files = sorted(PAGES_DIR.glob("*.png"))
                
                # Manifest'i temizle
                if LINES_MANIFEST.exists():
                    LINES_MANIFEST.unlink()
                
                with LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(page_files):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  Sayfa {idx + 1}/{len(page_files)} işleniyor...", "INFO")
                        records = split_page_to_lines(page)
                        for rec in records:
                            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                
                from src.kraken_processor import load_line_records_ordered
                ordered_recs = load_line_records_ordered()
                log_message(f"✓ LINES tamamlandı: {len(ordered_recs)} satır oluşturuldu")
                update_stage_status("lines", "✓ Tamamlandı")
                stage_results["lines_count"] = len(ordered_recs)
                return True
            except Exception as e:
                log_message(f"HATA (LINES): Satır segmentasyonu sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - LINES", f"Satır segmentasyonu sırasında hata oluştu:\n{e}"))
                update_stage_status("lines", "Hata!")
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_ocr():
        """AŞAMA: OCR - Google Vision OCR"""
        def _run():
            if not ocr_var.get():
                # OCR kapalı ama mevcut OCR dosyalarını kontrol et
                ocr_exist, ocr_count = check_ocr_exist()
                if ocr_exist:
                    log_message(f"OCR atlandı (kapalı) ama {ocr_count} mevcut OCR dosyası bulundu.", "INFO")
                    update_stage_status("ocr", f"Mevcut ({ocr_count})")
                else:
                    log_message("OCR atlandı (kapalı)", "INFO")
                    update_stage_status("ocr", "Atlandı")
                return True
            
            # Önce mevcut dosyaları kontrol et
            lines_exist, lines_count = check_lines_exist()
            if not lines_exist:
                log_message("HATA: Satır kayıtları bulunamadı. Önce LINES aşamasını çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Satır kayıtları bulunamadı. Önce LINES aşamasını çalıştırın."))
                update_stage_status("ocr", "Hata!")
                return False
            
            # Mevcut OCR dosyalarını kontrol et
            ocr_exist, ocr_count = check_ocr_exist()
            if ocr_exist:
                response = messagebox.askyesno(
                    "Mevcut OCR Dosyaları",
                    f"{ocr_count} mevcut OCR dosyası bulundu.\n\n"
                    f"Yeniden OCR yapmak ister misiniz?\n"
                    f"Hayır derseniz mevcut dosyalar kullanılacak."
                )
                if not response:
                    log_message(f"Mevcut {ocr_count} OCR dosyası kullanılıyor.", "INFO")
                    update_stage_status("ocr", f"Mevcut ({ocr_count})")
                    return True
            
            update_stage_status("ocr", "Çalışıyor...")
            log_message("OCR: Google Vision OCR yapılıyor...")
            
            try:
                from src.kraken_processor import load_line_records_ordered
                from src.ocr import ocr_lines_with_google_vision_api
                ordered_recs = load_line_records_ordered()
                if not ordered_recs:
                    log_message("HATA: Satır kayıtları bulunamadı. Önce LINES aşamasını çalıştırın.", "ERROR")
                    root.after(0, lambda: messagebox.showerror("Hata", "Satır kayıtları bulunamadı. Önce LINES aşamasını çalıştırın."))
                    update_stage_status("ocr", "Hata!")
                    return False
                
                ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
                vkey = get_google_vision_api_key()
                
                from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                ocr_ok, total = ocr_lines_with_google_vision_api(
                    ordered_line_paths,
                    api_key=vkey,
                    timeout=VISION_TIMEOUT,
                    retries=VISION_RETRIES,
                    backoff_base=VISION_BACKOFF_BASE,
                    max_dim=VISION_MAX_DIM,
                    jpeg_quality=VISION_JPEG_QUALITY,
                    sleep_s=0.10,
                    status_callback=log_message
                )
                log_message(f"✓ OCR tamamlandı: {ocr_ok}/{total} başarılı")
                update_stage_status("ocr", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (OCR): OCR sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - OCR", f"OCR sırasında hata oluştu:\n{e}"))
                update_stage_status("ocr", "Hata!")
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_spellcheck():
        """AŞAMA: Spellcheck - İmla kontrolü"""
        def _run():
            sc_exist, sc_path = check_spellcheck_exist()
            ai_model = ai_model_var.get()
            if ai_model == "none":
                log_message("AI model seçilmedi, imla kontrolü atlanıyor...")
                update_stage_status("spellcheck", "Atlandı")
                stage_results["sc_payload"] = None
                return True

            # Docx yolu: seçilmemişse mevcut spellcheck.json içinden al (append her zaman aktif)
            docx_path_str = docx_var.get().strip()
            if not docx_path_str:
                if sc_exist:
                    import json
                    try:
                        sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
                        docx_path_str = (sc_data.get("docx_path") or "").strip()
                        if docx_path_str:
                            log_message(f"Word seçilmedi. Mevcut spellcheck.json içinden docx kullanılıyor: {docx_path_str}", "INFO")
                        else:
                            root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) seçilmedi ve mevcut spellcheck.json içinde docx_path yok."))
                            return False
                    except Exception as e:
                        root.after(0, lambda: messagebox.showerror("Hata", f"Mevcut spellcheck.json okunamadı: {e}"))
                        return False
                elif sc_exist:
                    import json
                    try:
                        sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
                        stage_results["sc_payload"] = sc_data
                        log_message(f"Mevcut spellcheck dosyası yüklendi: {sc_path.name}", "INFO")
                        error_count = len(sc_data.get("errors_merged", []))
                        log_message(f"Mevcut spellcheck: {error_count} hata bulundu", "INFO")
                        update_stage_status("spellcheck", f"Mevcut ({error_count} hata)")
                        return True
                    except Exception as e:
                        log_message(f"Mevcut spellcheck dosyası okunamadı: {e}", "WARNING")
                        root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) secilmedi."))
                        return False
                else:
                    root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) secilmedi."))
                    return False

            # Spellcheck her zaman append modunda (eski sonuçlar korunur)
            update_stage_status("spellcheck", "Çalışıyor...")
            log_message("SPELLCHECK: İmla kontrolü yapılıyor... Mevcut sonuçlara eklenecek (append her zaman aktif).", "INFO")
            
            try:
                # If user wants to start later, append is almost always intended (to keep earlier results).
                # Append her zaman aktif (eski sonuçlar korunur)

                trace_state = None
                debug_cb = None
                if sc_verbose_ai_var.get():
                    ev = threading.Event()
                    holder = {}

                    def _create():
                        try:
                            holder["state"] = _open_ai_trace_window()
                        finally:
                            ev.set()

                    root.after(0, _create)
                    ev.wait(timeout=5.0)
                    trace_state = holder.get("state")
                    if trace_state:
                        debug_cb = _make_ai_trace_callback(trace_state)

                use_gemini = ai_model in ("gemini", "both", "all")
                use_openai = ai_model in ("openai", "both", "all")
                use_claude = ai_model in ("claude", "all")
                
                from src.spellcheck import spellcheck_tahkik_paragraphs
                sc_payload = spellcheck_tahkik_paragraphs(
                    Path(docx_path_str), 
                    use_gemini=use_gemini, 
                    use_openai=use_openai,
                    use_claude=use_claude,
                    start_paragraph=int(sc_start_para_var.get() or 1),
                    selected_paragraphs=sc_selected_paras.get("indices"),
                    append_to_existing=True,  # Her zaman append (eski sonuçlar korunur)
                    status_callback=log_message,
                    debug_callback=debug_cb,
                )
                error_count = len(sc_payload.get("errors_merged", []))
                log_message(f"✓ SPELLCHECK tamamlandı: {error_count} hata bulundu")
                update_stage_status("spellcheck", "✓ Tamamlandı")
                stage_results["sc_payload"] = sc_payload

                # close + save trace output
                if trace_state:
                    try:
                        trace_state["lines"].append("=== AI API TRACE BİTTİ (OK) ===\n")
                        trace_state["trace_path"].write_text("".join(trace_state["lines"]), encoding="utf-8")
                        log_message(f"AI trace kaydedildi: {trace_state['trace_path']}", "INFO")
                    except Exception as e:
                        log_message(f"AI trace kaydedilemedi: {e}", "WARNING")
                    def _close():
                        try:
                            trace_state["win"].destroy()
                        except Exception:
                            pass
                    root.after(0, _close)
                return True
            except Exception as e:
                log_message(f"HATA (SPELLCHECK): İmla kontrolü sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - SPELLCHECK", f"İmla kontrolü sırasında hata oluştu:\n{e}"))
                update_stage_status("spellcheck", "Hata!")
                stage_results["sc_payload"] = None
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_alignment():
        """AŞAMA: Alignment - Hizalama"""
        def _run():
            # Önce gerekli dosyaları kontrol et
            ocr_exist, ocr_count = check_ocr_exist()
            if not ocr_exist:
                log_message("HATA: OCR dosyaları bulunamadı. Önce OCR aşamasını çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "OCR dosyaları bulunamadı. Önce OCR aşamasını çalıştırın."))
                update_stage_status("alignment", "Hata!")
                return False
            
            if not docx_var.get().strip():
                # Word dosyası seçilmedi ama mevcut alignment dosyası var mı kontrol et
                align_exist, align_path = check_alignment_exist()
                if align_exist:
                    import json
                    try:
                        align_data = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = align_data
                        log_message(f"Mevcut alignment dosyası yüklendi: {align_path.name}", "INFO")
                        lines_count = align_data.get("lines_count", 0)
                        log_message(f"Mevcut alignment: {lines_count} satır hizalandı", "INFO")
                        update_stage_status("alignment", f"Mevcut ({lines_count} satır)")
                        return True
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}", "WARNING")
                
                root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) secilmedi."))
                return False
            
            # Mevcut alignment dosyası var mı kontrol et
            align_exist, align_path = check_alignment_exist()
            if align_exist:
                # Algo version mismatch ise eski dosyayı kullanma (yanlış sonuç gösteriyor olabilir)
                try:
                    import json
                    existing = json.loads(align_path.read_text(encoding="utf-8"))
                    ver = (existing.get("algo_version") or "").strip()
                    from src.alignment import ALGO_VERSION as ALIGNMENT_ALGO_VERSION
                    if ver and ver != ALIGNMENT_ALGO_VERSION:
                        log_message(
                            f"UYARI: Mevcut alignment eski sürüm ({ver}). Yeni sürüm ({ALIGNMENT_ALGO_VERSION}) ile yeniden hizalama yapılacak.",
                            "WARNING",
                        )
                        align_exist = False
                except Exception:
                    pass

            if align_exist:
                response = messagebox.askyesno(
                    "Mevcut Alignment Dosyası",
                    f"Mevcut alignment dosyası bulundu: {align_path.name}\n\n"
                    f"Yeniden hizalama yapmak ister misiniz?\n"
                    f"Hayır derseniz mevcut dosya kullanılacak."
                )
                if not response:
                    import json
                    try:
                        align_data = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = align_data
                        log_message(f"Mevcut alignment dosyası yüklendi: {align_path.name}", "INFO")
                        lines_count = align_data.get("lines_count", 0)
                        log_message(f"Mevcut alignment: {lines_count} satır hizalandı", "INFO")
                        update_stage_status("alignment", f"Mevcut ({lines_count} satır)")
                        return True
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}, yeniden yapılıyor...", "WARNING")
            
            # Spellcheck payload'u yükle (eğer varsa)
            if stage_results["sc_payload"] is None:
                sc_exist, sc_path = check_spellcheck_exist()
                if sc_exist:
                    import json
                    try:
                        sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
                        stage_results["sc_payload"] = sc_data
                        log_message(f"Mevcut spellcheck dosyası yüklendi: {sc_path.name}", "INFO")
                    except Exception as e:
                        log_message(f"Mevcut spellcheck dosyası okunamadı: {e}", "WARNING")
            
            update_stage_status("alignment", "Çalışıyor...")
            log_message("ALIGNMENT: OCR ve tahkik metni hizalanıyor...")
            
            try:
                from src.alignment import align_ocr_to_tahkik_segment_dp_multi
                payload = align_ocr_to_tahkik_segment_dp_multi(
                    Path(docx_var.get()), 
                    spellcheck_payload=stage_results["sc_payload"],
                    status_callback=log_message
                )
                log_message(f"✓ ALIGNMENT tamamlandı: {payload.get('lines_count', 0)} satır hizalandı")
                update_stage_status("alignment", "✓ Tamamlandı")
                stage_results["alignment_payload"] = payload
                return True
            except Exception as e:
                log_message(f"HATA (ALIGNMENT): Hizalama sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - ALIGNMENT", f"Hizalama sırasında hata oluştu:\n{e}"))
                update_stage_status("alignment", "Hata!")
                stage_results["alignment_payload"] = None
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_viewer():
        """AŞAMA: Viewer - Viewer oluşturma"""
        def _run():
            payload = stage_results["alignment_payload"]
            
            # Eğer payload yoksa, mevcut alignment dosyasını yükle
            if payload is None:
                align_exist, align_path = check_alignment_exist()
                if align_exist:
                    import json
                    try:
                        payload = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = payload
                        log_message(f"Mevcut alignment dosyası yüklendi: {align_path.name}", "INFO")
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}", "ERROR")
                        root.after(0, lambda: messagebox.showerror("Hata", f"Alignment dosyası okunamadı: {e}"))
                        return False
                else:
                    root.after(0, lambda: messagebox.showerror("Hata", "Hizalama verisi yok. Önce ALIGNMENT aşamasını çalıştırın."))
                    return False
            
            update_stage_status("viewer", "Çalışıyor...")
            log_message("VIEWER: HTML viewer oluşturuluyor...")
            
            # --- NEW: Reload from disk directly to ensure latest edits ---
            try:
                loaded_list, loaded_full = AlignmentService()._load_data()
                if loaded_full:
                    stage_results["alignment_payload"] = loaded_full
                    payload = loaded_full
                    log_message("VIEWER: Diskten güncel hizalama verisi yüklendi.", "INFO")
            except Exception as e:
                log_message(f"VIEWER UYARI: Güncel veri diskten okunamadı: {e}", "WARNING")
            # -------------------------------------------------------------

            try:
                from src.viewer import write_viewer_html
                from src.doc_archive import archive_current_outputs
                write_viewer_html(payload, prefer_alt=False)
                log_message("✓ VIEWER tamamlandı: Viewer HTML oluşturuldu")
                update_stage_status("viewer", "✓ Tamamlandı")

                # Snapshot outputs so switching to another Word won't overwrite old lines/tahkik/alignment
                try:
                    dp = (payload.get("docx_path") if isinstance(payload, dict) else None) or docx_var.get().strip()
                    archive_current_outputs(Path(dp) if dp else None, status_callback=log_message)
                except Exception as e:
                    log_message(f"ARŞİV: Çıktılar yedeklenemedi: {e}", "WARNING")
                
                try:
                    webbrowser.open(VIEWER_HTML.as_uri())
                    log_message("✓ Viewer tarayıcıda açıldı")
                except Exception as e:
                    log_message(f"UYARI: Viewer açılamadı: {e}", "WARNING")
                
                return True
            except Exception as e:
                log_message(f"HATA (VIEWER): Viewer oluşturma sırasında hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - VIEWER", f"Viewer oluşturma sırasında hata oluştu:\n{e}"))
                update_stage_status("viewer", "Hata!")
                return False
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def run_viewer2():
        """AŞAMA: Viewer (Nüsha 2) - N2 tabanlı viewer oluşturma"""
        def _run():
            payload = stage_results["alignment_payload"]
            if payload is None:
                align_exist, align_path = check_alignment_exist()
                if align_exist:
                    try:
                        payload = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = payload
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}", "ERROR")
                        root.after(0, lambda: messagebox.showerror("Hata", f"Alignment dosyası okunamadı: {e}"))
                        return False
                else:
                    root.after(0, lambda: messagebox.showerror("Hata", "Hizalama verisi yok. Önce ALIGNMENT aşamasını çalıştırın."))
                    return False

            update_stage_status("viewer2", "Çalışıyor...")
            log_message("VIEWER (N2): HTML viewer oluşturuluyor (Nüsha 2 tabanlı)...", "INFO")
            try:
                # --- NEW: Reload from disk directly to ensure latest edits ---
                try:
                    loaded_list, loaded_full = AlignmentService()._load_data()
                    if loaded_full:
                        stage_results["alignment_payload"] = loaded_full
                        payload = loaded_full
                        log_message("VIEWER (N2): Diskten güncel hizalama verisi yüklendi.", "INFO")
                except Exception as e:
                    log_message(f"VIEWER (N2) UYARI: Güncel veri diskten okunamadı: {e}", "WARNING")
                # -------------------------------------------------------------

                from src.viewer import write_viewer_html
                from src.doc_archive import archive_current_outputs
                from src.config import NUSHA2_VIEWER_HTML
                write_viewer_html(payload, prefer_alt=True)
                log_message("✓ VIEWER (N2) tamamlandı: Nüsha 2 Viewer HTML oluşturuldu", "INFO")
                update_stage_status("viewer2", "✓ Tamamlandı")

                # Snapshot outputs
                try:
                    dp = (payload.get("docx_path") if isinstance(payload, dict) else None) or docx_var.get().strip()
                    archive_current_outputs(Path(dp) if dp else None, status_callback=log_message)
                except Exception as e:
                    log_message(f"ARŞİV: Çıktılar yedeklenemedi: {e}", "WARNING")

                try:
                    webbrowser.open(NUSHA2_VIEWER_HTML.as_uri())
                except Exception as e:
                    log_message(f"UYARI: Viewer (N2) açılamadı: {e}", "WARNING")
                return True
            except Exception as e:
                log_message(f"HATA (VIEWER N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - VIEWER (Nüsha 2)", f"Viewer oluşturma sırasında hata:\n{e}"))
                update_stage_status("viewer2", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    # =========================
    # Nüsha 3 helpers + stages
    # =========================
    def validate_inputs3() -> bool:
        """Nüsha 3 için PDF + DPI kontrolü"""
        if not pdf3_var.get().strip():
            messagebox.showerror("Hata", "3. Nüsha PDF seçilmedi.")
            return False
        try:
            dpi = int(dpi_var.get().strip())
            if dpi < 100 or dpi > 600:
                raise ValueError
        except Exception:
            messagebox.showerror("Hata", "DPI 100-600 arası bir sayı olmalı (örn: 300).")
            return False
        return True

    def run_pages3():
        """AŞAMA: Pages (Nüsha 3)"""
        def _run():
            if not validate_inputs3():
                return False
            update_stage_status("pages3", "Çalışıyor...")
            log_message("PAGES (N3): PDF işleniyor (PNG'e dönüştürülüyor)...", "INFO")
            try:
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf3_var.get()), dpi=dpi, pages_dir=NUSHA3_PAGES_DIR)
                log_message(f"✓ PAGES (N3) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages3", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (PAGES N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - PAGES (Nüsha 3)", f"PDF işleme sırasında hata:\n{e}"))
                update_stage_status("pages3", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_lines3():
        """AŞAMA: Lines (Nüsha 3)"""
        def _run():
            pages_exist, pages_count = _check_pages_exist_dir(NUSHA3_PAGES_DIR)
            if not pages_exist:
                log_message("HATA: Nüsha 3 sayfa PNG'leri bulunamadı. Önce PAGES (N3) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 3 sayfa PNG'leri bulunamadı. Önce PAGES (N3) çalıştırın."))
                update_stage_status("lines3", "Hata!")
                return False

            update_stage_status("lines3", "Çalışıyor...")
            log_message(f"LINES (N3): {pages_count} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
            try:
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA3_LINES_MANIFEST.exists():
                    NUSHA3_LINES_MANIFEST.unlink()
                with NUSHA3_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA3_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N3) Sayfa {idx + 1}/{pages_count} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA3_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA3_LINES_MANIFEST)
                log_message(f"✓ LINES (N3) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines3", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (LINES N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - LINES (Nüsha 3)", f"Satır segmentasyonu sırasında hata:\n{e}"))
                update_stage_status("lines3", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_ocr3():
        """AŞAMA: OCR (Nüsha 3)"""
        def _run():
            if not ocr_var.get():
                ocr_exist, ocr_count = _check_ocr_exist_dir(NUSHA3_OCR_DIR)
                if ocr_exist:
                    log_message(f"OCR (N3) atlandı (kapalı) ama {ocr_count} mevcut OCR dosyası bulundu.", "INFO")
                    update_stage_status("ocr3", f"Mevcut ({ocr_count})")
                else:
                    log_message("OCR (N3) atlandı (kapalı)", "INFO")
                    update_stage_status("ocr3", "Atlandı")
                return True

            lines_exist, lines_count = _check_lines_exist_dir(NUSHA3_LINES_DIR, NUSHA3_LINES_MANIFEST)
            if not lines_exist:
                log_message("HATA: Nüsha 3 satır kayıtları bulunamadı. Önce LINES (N3) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 3 satır kayıtları bulunamadı. Önce LINES (N3) çalıştırın."))
                update_stage_status("ocr3", "Hata!")
                return False

            update_stage_status("ocr3", "Çalışıyor...")
            log_message(f"OCR (N3): Google Vision OCR yapılıyor... ({lines_count} satır)", "INFO")
            try:
                from src.kraken_processor import load_line_records_ordered
                from src.ocr import ocr_lines_with_google_vision_api
                recs = load_line_records_ordered(manifest_path=NUSHA3_LINES_MANIFEST)
                ordered_line_paths = [Path(r["line_image"]) for r in recs]
                vkey = get_google_vision_api_key()
                from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                ok, total = ocr_lines_with_google_vision_api(
                    ordered_line_paths,
                    api_key=vkey,
                    timeout=VISION_TIMEOUT,
                    retries=VISION_RETRIES,
                    backoff_base=VISION_BACKOFF_BASE,
                    max_dim=VISION_MAX_DIM,
                    jpeg_quality=VISION_JPEG_QUALITY,
                    sleep_s=0.10,
                    status_callback=log_message,
                    ocr_dir=NUSHA3_OCR_DIR,
                )
                log_message(f"✓ OCR (N3) tamamlandı: {ok}/{total} başarılı", "INFO")
                update_stage_status("ocr3", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (OCR N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - OCR (Nüsha 3)", f"OCR sırasında hata:\n{e}"))
                update_stage_status("ocr3", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_alignment3():
        """AŞAMA: Alignment (Nüsha 3) - N3 çıktılarını da içeren hizalamayı üret"""
        def _run():
            if not docx_var.get().strip():
                root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) seçilmedi."))
                return False

            l3_exist, _ = _check_lines_exist_dir(NUSHA3_LINES_DIR, NUSHA3_LINES_MANIFEST)
            if not l3_exist:
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 3 satırları yok. Önce Pages/Lines/OCR (N3) çalıştırın."))
                update_stage_status("alignment3", "Hata!")
                return False

            update_stage_status("alignment3", "Çalışıyor...")
            log_message("ALIGNMENT (N3): Nüsha 3 hizalaması (ve birleşik payload) hazırlanıyor...", "INFO")
            try:
                from src.alignment import align_ocr_to_tahkik_segment_dp_multi
                payload = align_ocr_to_tahkik_segment_dp_multi(
                    Path(docx_var.get()),
                    spellcheck_payload=stage_results["sc_payload"],
                    status_callback=log_message,
                )
                stage_results["alignment_payload"] = payload
                update_stage_status("alignment3", "✓ Tamamlandı")
                log_message("✓ ALIGNMENT (N3) tamamlandı", "INFO")
                return True
            except Exception as e:
                log_message(f"HATA (ALIGNMENT N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - ALIGNMENT (Nüsha 3)", f"Hizalama sırasında hata:\n{e}"))
                update_stage_status("alignment3", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_viewer3():
        """AŞAMA: Viewer (Nüsha 3) - N3 tabanlı viewer oluşturma"""
        def _run():
            payload = stage_results["alignment_payload"]
            if payload is None:
                align_exist, align_path = check_alignment_exist()
                if align_exist:
                    try:
                        payload = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = payload
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}", "ERROR")
                        root.after(0, lambda: messagebox.showerror("Hata", f"Alignment dosyası okunamadı: {e}"))
                        return False
                else:
                    root.after(0, lambda: messagebox.showerror("Hata", "Hizalama verisi yok. Önce ALIGNMENT aşamasını çalıştırın."))
                    return False

            update_stage_status("viewer3", "Çalışıyor...")
            log_message("VIEWER (N3): HTML viewer oluşturuluyor (Nüsha 3 tabanlı)...", "INFO")
            try:
                # --- NEW: Reload from disk directly to ensure latest edits ---
                try:
                    loaded_list, loaded_full = AlignmentService()._load_data()
                    if loaded_full:
                        stage_results["alignment_payload"] = loaded_full
                        payload = loaded_full
                        log_message("VIEWER (N3): Diskten güncel hizalama verisi yüklendi.", "INFO")
                except Exception as e:
                    log_message(f"VIEWER (N3) UYARI: Güncel veri diskten okunamadı: {e}", "WARNING")
                # -------------------------------------------------------------

                from src.viewer import write_viewer_html
                from src.doc_archive import archive_current_outputs
                write_viewer_html(payload, prefer_alt3=True)
                log_message("✓ VIEWER (N3) tamamlandı: Nüsha 3 Viewer HTML oluşturuldu", "INFO")
                update_stage_status("viewer3", "✓ Tamamlandı")

                # Snapshot outputs
                try:
                    dp = (payload.get("docx_path") if isinstance(payload, dict) else None) or docx_var.get().strip()
                    archive_current_outputs(Path(dp) if dp else None, status_callback=log_message)
                except Exception as e:
                    log_message(f"ARŞİV: Çıktılar yedeklenemedi: {e}", "WARNING")

                try:
                    webbrowser.open(NUSHA3_VIEWER_HTML.as_uri())
                except Exception as e:
                    log_message(f"UYARI: Viewer (N3) açılamadı: {e}", "WARNING")
                return True
            except Exception as e:
                log_message(f"HATA (VIEWER N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - VIEWER (Nüsha 3)", f"Viewer oluşturma sırasında hata:\n{e}"))
                update_stage_status("viewer3", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True


    # =========================
    # Nüsha 4 helpers + stages
    # =========================
    def validate_inputs4() -> bool:
        """Nüsha 4 için PDF + DPI kontrolü"""
        if not pdf4_var.get().strip():
            messagebox.showerror("Hata", "4. Nüsha PDF seçilmedi.")
            return False
        try:
            dpi = int(dpi_var.get().strip())
            if dpi < 100 or dpi > 600:
                raise ValueError
        except Exception:
            messagebox.showerror("Hata", "DPI 100-600 arası bir sayı olmalı (örn: 300).")
            return False
        return True

    def run_pages4():
        """AŞAMA: Pages (Nüsha 4)"""
        def _run():
            if not validate_inputs4():
                return False
            update_stage_status("pages4", "Çalışıyor...")
            log_message("PAGES (N4): PDF işleniyor (PNG'e dönüştürülüyor)...", "INFO")
            try:
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf4_var.get()), dpi=dpi, pages_dir=NUSHA4_PAGES_DIR)
                log_message(f"✓ PAGES (N4) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages4", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (PAGES N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - PAGES (Nüsha 4)", f"PDF işleme sırasında hata:\n{e}"))
                update_stage_status("pages4", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_lines4():
        """AŞAMA: Lines (Nüsha 4)"""
        def _run():
            pages_exist, pages_count = _check_pages_exist_dir(NUSHA4_PAGES_DIR)
            if not pages_exist:
                log_message("HATA: Nüsha 4 sayfa PNG'leri bulunamadı. Önce PAGES (N4) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 4 sayfa PNG'leri bulunamadı. Önce PAGES (N4) çalıştırın."))
                update_stage_status("lines4", "Hata!")
                return False

            update_stage_status("lines4", "Çalışıyor...")
            log_message(f"LINES (N4): {pages_count} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
            try:
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA4_LINES_MANIFEST.exists():
                    NUSHA4_LINES_MANIFEST.unlink()
                with NUSHA4_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA4_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N4) Sayfa {idx + 1}/{pages_count} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA4_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA4_LINES_MANIFEST)
                log_message(f"✓ LINES (N4) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines4", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (LINES N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - LINES (Nüsha 4)", f"Satır segmentasyonu sırasında hata:\n{e}"))
                update_stage_status("lines4", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_ocr4():
        """AŞAMA: OCR (Nüsha 4)"""
        def _run():
            if not ocr_var.get():
                ocr_exist, ocr_count = _check_ocr_exist_dir(NUSHA4_OCR_DIR)
                if ocr_exist:
                    log_message(f"OCR (N4) atlandı (kapalı) ama {ocr_count} mevcut OCR dosyası bulundu.", "INFO")
                    update_stage_status("ocr4", f"Mevcut ({ocr_count})")
                else:
                    log_message("OCR (N4) atlandı (kapalı)", "INFO")
                    update_stage_status("ocr4", "Atlandı")
                return True

            lines_exist, lines_count = _check_lines_exist_dir(NUSHA4_LINES_DIR, NUSHA4_LINES_MANIFEST)
            if not lines_exist:
                log_message("HATA: Nüsha 4 satır kayıtları bulunamadı. Önce LINES (N4) çalıştırın.", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 4 satır kayıtları bulunamadı. Önce LINES (N4) çalıştırın."))
                update_stage_status("ocr4", "Hata!")
                return False

            update_stage_status("ocr4", "Çalışıyor...")
            log_message(f"OCR (N4): Google Vision OCR yapılıyor... ({lines_count} satır)", "INFO")
            try:
                from src.kraken_processor import load_line_records_ordered
                from src.ocr import ocr_lines_with_google_vision_api
                recs = load_line_records_ordered(manifest_path=NUSHA4_LINES_MANIFEST)
                ordered_line_paths = [Path(r["line_image"]) for r in recs]
                vkey = get_google_vision_api_key()
                from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                ok, total = ocr_lines_with_google_vision_api(
                    ordered_line_paths,
                    api_key=vkey,
                    timeout=VISION_TIMEOUT,
                    retries=VISION_RETRIES,
                    backoff_base=VISION_BACKOFF_BASE,
                    max_dim=VISION_MAX_DIM,
                    jpeg_quality=VISION_JPEG_QUALITY,
                    sleep_s=0.10,
                    status_callback=log_message,
                    ocr_dir=NUSHA4_OCR_DIR,
                )
                log_message(f"✓ OCR (N4) tamamlandı: {ok}/{total} başarılı", "INFO")
                update_stage_status("ocr4", "✓ Tamamlandı")
                return True
            except Exception as e:
                log_message(f"HATA (OCR N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - OCR (Nüsha 4)", f"OCR sırasında hata:\n{e}"))
                update_stage_status("ocr4", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_alignment4():
        """AŞAMA: Alignment (Nüsha 4) - N4 çıktılarını da içeren hizalamayı üret"""
        def _run():
            if not docx_var.get().strip():
                root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) seçilmedi."))
                return False

            l4_exist, _ = _check_lines_exist_dir(NUSHA4_LINES_DIR, NUSHA4_LINES_MANIFEST)
            if not l4_exist:
                root.after(0, lambda: messagebox.showerror("Hata", "Nüsha 4 satırları yok. Önce Pages/Lines/OCR (N4) çalıştırın."))
                update_stage_status("alignment4", "Hata!")
                return False

            update_stage_status("alignment4", "Çalışıyor...")
            log_message("ALIGNMENT (N4): Nüsha 4 hizalaması (ve birleşik payload) hazırlanıyor...", "INFO")
            try:
                from src.alignment import align_ocr_to_tahkik_segment_dp_multi
                payload = align_ocr_to_tahkik_segment_dp_multi(
                    Path(docx_var.get()),
                    spellcheck_payload=stage_results["sc_payload"],
                    status_callback=log_message,
                )
                stage_results["alignment_payload"] = payload
                update_stage_status("alignment4", "✓ Tamamlandı")
                log_message("✓ ALIGNMENT (N4) tamamlandı", "INFO")
                return True
            except Exception as e:
                log_message(f"HATA (ALIGNMENT N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - ALIGNMENT (Nüsha 4)", f"Hizalama sırasında hata:\n{e}"))
                update_stage_status("alignment4", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_viewer4():
        """AŞAMA: Viewer (Nüsha 4) - N4 tabanlı viewer oluşturma"""
        def _run():
            payload = stage_results["alignment_payload"]
            if payload is None:
                align_exist, align_path = check_alignment_exist()
                if align_exist:
                    try:
                        payload = json.loads(align_path.read_text(encoding="utf-8"))
                        stage_results["alignment_payload"] = payload
                    except Exception as e:
                        log_message(f"Mevcut alignment dosyası okunamadı: {e}", "ERROR")
                        root.after(0, lambda: messagebox.showerror("Hata", f"Alignment dosyası okunamadı: {e}"))
                        return False
                else:
                    root.after(0, lambda: messagebox.showerror("Hata", "Hizalama verisi yok. Önce ALIGNMENT aşamasını çalıştırın."))
                    return False

            update_stage_status("viewer4", "Çalışıyor...")
            log_message("VIEWER (N4): HTML viewer oluşturuluyor (Nüsha 4 tabanlı)...", "INFO")
            try:
                # --- NEW: Reload from disk directly to ensure latest edits ---
                try:
                    loaded_list, loaded_full = AlignmentService()._load_data()
                    if loaded_full:
                        stage_results["alignment_payload"] = loaded_full
                        payload = loaded_full
                        log_message("VIEWER (N4): Diskten güncel hizalama verisi yüklendi.", "INFO")
                except Exception as e:
                    log_message(f"VIEWER (N4) UYARI: Güncel veri diskten okunamadı: {e}", "WARNING")
                # -------------------------------------------------------------

                from src.viewer import write_viewer_html
                from src.doc_archive import archive_current_outputs
                write_viewer_html(payload, prefer_alt4=True)
                log_message("✓ VIEWER (N4) tamamlandı: Nüsha 4 Viewer HTML oluşturuldu", "INFO")
                update_stage_status("viewer4", "✓ Tamamlandı")

                # Snapshot outputs
                try:
                    dp = (payload.get("docx_path") if isinstance(payload, dict) else None) or docx_var.get().strip()
                    archive_current_outputs(Path(dp) if dp else None, status_callback=log_message)
                except Exception as e:
                    log_message(f"ARŞİV: Çıktılar yedeklenemedi: {e}", "WARNING")

                try:
                    webbrowser.open(NUSHA4_VIEWER_HTML.as_uri())
                except Exception as e:
                    log_message(f"UYARI: Viewer (N4) açılamadı: {e}", "WARNING")
                return True
            except Exception as e:
                log_message(f"HATA (VIEWER N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                root.after(0, lambda: messagebox.showerror("Hata - VIEWER (Nüsha 4)", f"Viewer oluşturma sırasında hata:\n{e}"))
                update_stage_status("viewer4", "Hata!")
                return False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def run_all_threaded():
        """Tüm aşamaları thread'de çalıştır"""
        def _run_all():
            # Tüm durumları sıfırla
            for key in stage_status:
                stage_status[key].set("Bekliyor")
            
            # Sonuçları sıfırla
            stage_results["pages_count"] = 0
            stage_results["lines_count"] = 0
            stage_results["sc_payload"] = None
            stage_results["alignment_payload"] = None
            
            if log_text:
                log_text.delete(1.0, tk.END)
            
            log_message("=" * 60)
            log_message("TÜM AŞAMALAR BAŞLATILIYOR...")
            log_message("=" * 60)

            try:
                # Eski çıktıları temizle
                hard_cleanup_output()
                
                # PAGES
                if not validate_inputs():
                    return
                
                update_stage_status("pages", "Çalışıyor...")
                log_message("PAGES: PDF işleniyor (PNG'e dönüştürülüyor)...")
                dpi = int(dpi_var.get().strip())
                from src.pdf_processor import pdf_to_page_pngs
                pages = pdf_to_page_pngs(Path(pdf_var.get()), dpi=dpi)
                log_message(f"✓ PAGES tamamlandı: {len(pages)} sayfa PNG'e dönüştürüldü")
                update_stage_status("pages", "✓ Tamamlandı")
                stage_results["pages_count"] = len(pages)

                # LINES
                update_stage_status("lines", "Çalışıyor...")
                log_message("LINES: Sayfalar satırlara bölünüyor (Kraken)...")
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                from src.config import PAGES_DIR
                page_files = sorted(PAGES_DIR.glob("*.png"))
                if LINES_MANIFEST.exists():
                    LINES_MANIFEST.unlink()
                with LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(page_files):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  Sayfa {idx + 1}/{len(page_files)} işleniyor...", "INFO")
                        records = split_page_to_lines(page)
                        for rec in records:
                            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered()
                log_message(f"✓ LINES tamamlandı: {len(ordered_recs)} satır oluşturuldu")
                update_stage_status("lines", "✓ Tamamlandı")
                stage_results["lines_count"] = len(ordered_recs)

                # OCR
                if ocr_var.get():
                    update_stage_status("ocr", "Çalışıyor...")
                    log_message("OCR: Google Vision OCR yapılıyor...")
                    ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
                    vkey = get_google_vision_api_key()
                    from src.ocr import ocr_lines_with_google_vision_api
                    from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                    ocr_ok, total = ocr_lines_with_google_vision_api(
                        ordered_line_paths,
                        api_key=vkey,
                        timeout=VISION_TIMEOUT,
                        retries=VISION_RETRIES,
                        backoff_base=VISION_BACKOFF_BASE,
                        max_dim=VISION_MAX_DIM,
                        jpeg_quality=VISION_JPEG_QUALITY,
                        sleep_s=0.10,
                        status_callback=log_message
                    )
                    log_message(f"✓ OCR tamamlandı: {ocr_ok}/{total} başarılı")
                    update_stage_status("ocr", "✓ Tamamlandı")
                else:
                    log_message("OCR atlandı (kapalı)", "INFO")
                    update_stage_status("ocr", "Atlandı")

                if not align_var.get():
                    log_message("=" * 60)
                    log_message("✓ PDF İŞLEME TAMAMLANDI!")
                    log_message("=" * 60)
                    root.after(0, lambda: messagebox.showinfo("Bitti", "PDF işleme tamamlandı."))
                    return

                # SPELLCHECK
                if not docx_var.get().strip():
                    log_message("UYARI: Word dosyası seçilmedi, imla kontrolü atlanıyor...", "WARNING")
                else:
                    ai_model = ai_model_var.get()
                    if ai_model == "none":
                        log_message("AI model seçilmedi, imla kontrolü atlanıyor...")
                        update_stage_status("spellcheck", "Atlandı")
                        stage_results["sc_payload"] = None
                    else:
                        update_stage_status("spellcheck", "Çalışıyor...")
                        log_message("SPELLCHECK: İmla kontrolü yapılıyor...")
                        trace_state = None
                        debug_cb = None
                        if sc_verbose_ai_var.get():
                            ev = threading.Event()
                            holder = {}

                            def _create():
                                try:
                                    holder["state"] = _open_ai_trace_window()
                                finally:
                                    ev.set()

                            root.after(0, _create)
                            ev.wait(timeout=5.0)
                            trace_state = holder.get("state")
                            if trace_state:
                                debug_cb = _make_ai_trace_callback(trace_state)

                        use_gemini = ai_model in ("gemini", "both", "all")
                        use_openai = ai_model in ("openai", "both", "all")
                        use_claude = ai_model in ("claude", "all")
                        try:
                            from src.spellcheck import spellcheck_tahkik_paragraphs
                            sc_payload = spellcheck_tahkik_paragraphs(
                                Path(docx_var.get()),
                                use_gemini=use_gemini,
                                use_openai=use_openai,
                                use_claude=use_claude,
                                start_paragraph=int(sc_start_para_var.get() or 1),
                                selected_paragraphs=sc_selected_paras.get("indices"),
                                append_to_existing=True,  # Her zaman append (eski sonuçlar korunur)
                                status_callback=log_message,
                                debug_callback=debug_cb,
                            )
                        finally:
                            if trace_state:
                                try:
                                    trace_state["lines"].append("=== AI API TRACE BİTTİ (RUN_ALL) ===\n")
                                    trace_state["trace_path"].write_text("".join(trace_state["lines"]), encoding="utf-8")
                                    log_message(f"AI trace kaydedildi: {trace_state['trace_path']}", "INFO")
                                except Exception as e:
                                    log_message(f"AI trace kaydedilemedi: {e}", "WARNING")

                                def _close():
                                    try:
                                        trace_state["win"].destroy()
                                    except Exception:
                                        pass

                                root.after(0, _close)
                        error_count = len(sc_payload.get("errors_merged", []))
                        log_message(f"✓ SPELLCHECK tamamlandı: {error_count} hata bulundu")
                        update_stage_status("spellcheck", "✓ Tamamlandı")
                        stage_results["sc_payload"] = sc_payload

                # ALIGNMENT
                if not docx_var.get().strip():
                    root.after(0, lambda: messagebox.showerror("Hata", "Word (.docx) secilmedi."))
                    return
                
                update_stage_status("alignment", "Çalışıyor...")
                log_message("ALIGNMENT: OCR ve tahkik metni hizalanıyor...")
                from src.alignment import align_ocr_to_tahkik_segment_dp_multi
                payload = align_ocr_to_tahkik_segment_dp_multi(
                    Path(docx_var.get()), 
                    spellcheck_payload=stage_results["sc_payload"],
                    status_callback=log_message
                )
                log_message(f"✓ ALIGNMENT tamamlandı: {payload.get('lines_count', 0)} satır hizalandı")
                update_stage_status("alignment", "✓ Tamamlandı")
                stage_results["alignment_payload"] = payload

                # VIEWER
                update_stage_status("viewer", "Çalışıyor...")
                log_message("VIEWER: HTML viewer oluşturuluyor...")
                
                # --- NEW: Reload from disk directly to ensure latest edits ---
                try:
                    loaded_list, loaded_full = AlignmentService()._load_data()
                    # If load successful, update payload. If not, use whatever we had (fallback)
                    if loaded_full:
                        stage_results["alignment_payload"] = loaded_full
                        payload = loaded_full
                        log_message("VIEWER: Diskten güncel hizalama verisi yüklendi.", "INFO")
                except Exception as e:
                    log_message(f"VIEWER UYARI: Güncel veri diskten okunamadı, eski veri kullanılıyor: {e}", "WARNING")
                # -------------------------------------------------------------

                from src.viewer import write_viewer_html
                from src.doc_archive import archive_current_outputs
                write_viewer_html(payload)
                log_message("✓ VIEWER tamamlandı: Viewer HTML oluşturuldu")
                update_stage_status("viewer", "✓ Tamamlandı")

                # Snapshot outputs so switching to another Word won't overwrite old lines/tahkik/alignment
                try:
                    dp = (payload.get("docx_path") if isinstance(payload, dict) else None) or docx_var.get().strip()
                    archive_current_outputs(Path(dp) if dp else None, status_callback=log_message)
                except Exception as e:
                    log_message(f"ARŞİV: Çıktılar yedeklenemedi: {e}", "WARNING")
                
                try:
                    webbrowser.open(VIEWER_HTML.as_uri())
                    log_message("✓ Viewer tarayıcıda açıldı")
                except Exception as e:
                    log_message(f"UYARI: Viewer açılamadı: {e}", "WARNING")

                log_message("=" * 60)
                log_message("✓ TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!")
                log_message("=" * 60)

                root.after(0, lambda: messagebox.showinfo(
                    "Bitti",
                    f"Tüm işlemler tamamlandı!\n\nCikti klasoru:\n{OUT}"
                ))
            except Exception as e:
                log_message(f"KRİTİK HATA: Beklenmeyen hata: {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
                # NOTE: in Python 3, exception variables are cleared at the end of the except block.
                # If we capture `e` inside a lambda scheduled later, it may raise:
                #   NameError: cannot access free variable 'e' ...
                msg = str(e)
                root.after(0, lambda msg=msg: messagebox.showerror("Kritik Hata", f"Beklenmeyen bir hata oluştu:\n{msg}\n\nDetaylar için log alanına bakın."))
        
        # Thread'de çalıştır
        thread = threading.Thread(target=_run_all, daemon=True)
        thread.start()

    def run_all():
        """Tüm aşamaları sırayla çalıştır (thread wrapper)"""
        run_all_threaded()

    # Ana frame
    main_frame = ttk.Frame(root, style="TFrame")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

    # Sol panel - Kontroller
    left_container = ttk.Frame(main_frame, style="TFrame")
    left_container.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 14))

    # Sol panel scroll (Canvas + Scrollbar + içerik frame)
    left_canvas = tk.Canvas(left_container, highlightthickness=0, borderwidth=0)
    left_scroll = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
    left_canvas.configure(yscrollcommand=left_scroll.set)

    left_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    left_panel = ttk.Frame(left_canvas, style="TFrame")
    left_window_id = left_canvas.create_window((0, 0), window=left_panel, anchor="nw")

    def _sync_left_scroll_region(_event=None):
        try:
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        except Exception:
            pass

    def _sync_left_width(event=None):
        # içerik frame genişliği canvas genişliğine eşitlensin
        try:
            left_canvas.itemconfig(left_window_id, width=left_canvas.winfo_width())
        except Exception:
            pass

    left_panel.bind("<Configure>", _sync_left_scroll_region)
    left_canvas.bind("<Configure>", _sync_left_width)

    def _bind_mousewheel_to_left(_event=None):
        def _on_mousewheel(e):
            # macOS: e.delta küçük değerler olabilir; Windows: 120 katları
            if getattr(e, "delta", 0):
                delta = e.delta
                step = int(-1 * (delta / 120)) if abs(delta) >= 120 else int(-1 * delta)
                if step == 0:
                    step = -1 if delta > 0 else 1
                left_canvas.yview_scroll(step, "units")
            else:
                # Linux (Button-4/5)
                if e.num == 4:
                    left_canvas.yview_scroll(-3, "units")
                elif e.num == 5:
                    left_canvas.yview_scroll(3, "units")

        root.bind_all("<MouseWheel>", _on_mousewheel)
        root.bind_all("<Button-4>", _on_mousewheel)
        root.bind_all("<Button-5>", _on_mousewheel)

    def _unbind_mousewheel_from_left(_event=None):
        root.unbind_all("<MouseWheel>")
        root.unbind_all("<Button-4>")
        root.unbind_all("<Button-5>")

    left_canvas.bind("<Enter>", _bind_mousewheel_to_left)
    left_canvas.bind("<Leave>", _unbind_mousewheel_from_left)
    left_panel.bind("<Enter>", _bind_mousewheel_to_left)
    left_panel.bind("<Leave>", _unbind_mousewheel_from_left)

    def open_old_results():
        """
        Browse output_lines/doc_archives and open an archived viewer.html.
        Each archive is a full snapshot (lines + spellcheck + viewer).
        """
        try:
            DOC_ARCHIVES_DIR.mkdir(exist_ok=True)
        except Exception:
            pass

        win = tk.Toplevel(root)
        win.title("Eski Sonuçlar (doc_archives)")
        win.geometry("980x720")

        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=12, pady=10)
        ttk.Label(top, text=f"Arşiv klasörü: {DOC_ARCHIVES_DIR}", style="Muted.TLabel").pack(anchor="w")

        mid = ttk.Frame(win)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        lb = tk.Listbox(mid, selectmode=tk.BROWSE)
        sb = ttk.Scrollbar(mid, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        info = ttk.Label(win, text="Seçili arşiv: (yok)", style="Muted.TLabel", justify=tk.LEFT)
        info.pack(fill=tk.X, padx=12, pady=(0, 10))

        state = {"dirs": []}  # list[Path]

        def _refresh():
            lb.delete(0, tk.END)
            dirs = []
            try:
                dirs = sorted([p for p in DOC_ARCHIVES_DIR.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
            except Exception:
                dirs = []
            state["dirs"] = dirs
            for d in dirs:
                lb.insert(tk.END, d.name)
            info.config(text=f"Toplam arşiv: {len(dirs)}")

        def _sel_dir() -> Optional[Path]:
            try:
                cur = lb.curselection()
                if not cur:
                    return None
                i = int(cur[0])
                return state["dirs"][i]
            except Exception:
                return None

        def _update_info(_event=None):
            d = _sel_dir()
            if not d:
                return
            meta = {}
            try:
                mp = d / "meta.json"
                if mp.exists():
                    meta = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
            docx_path = (meta.get("docx_path") or "").strip() if isinstance(meta, dict) else ""
            hv = (d / "viewer.html").exists()
            ha = (d / "alignment.json").exists()
            hs = (d / "spellcheck.json").exists()
            hl = (d / "lines").exists()
            info.config(
                text=(
                    f"Seçili arşiv: {d.name}\n"
                    f"docx_path: {docx_path or '(yok)'}\n"
                    f"viewer.html: {'✓' if hv else '✗'} • alignment.json: {'✓' if ha else '✗'} • spellcheck.json: {'✓' if hs else '✗'} • lines/: {'✓' if hl else '✗'}"
                )
            )

        def _open_viewer():
            d = _sel_dir()
            if not d:
                messagebox.showerror("Hata", "Bir arşiv seçin.")
                return
            try:
                # Prefer regenerating viewer from archived alignment.json using the latest template
                ap = d / "alignment.json"
                if ap.exists():
                    try:
                        payload = json.loads(ap.read_text(encoding="utf-8"))
                        if isinstance(payload, dict):
                            from src.viewer import write_viewer_html
                            write_viewer_html(payload, prefer_alt=False, archive_path=str(d), out_dir=d)
                    except Exception:
                        pass

                vp = d / "viewer.html"
                if not vp.exists():
                    messagebox.showerror("Hata", f"viewer.html bulunamadı:\n{vp}")
                    return
                webbrowser.open(vp.as_uri())
            except Exception as e:
                messagebox.showerror("Hata", f"Viewer açılamadı:\n{e}")

        def _rename_archive():
            d = _sel_dir()
            if not d:
                messagebox.showerror("Hata", "Bir arşiv seçin.")
                return
            new_name = tk.simpledialog.askstring(
                "Arşiv İsmini Değiştir",
                f"Mevcut isim: {d.name}\n\nYeni isim:",
                initialvalue=d.name
            )
            if not new_name or not new_name.strip():
                return
            new_name = new_name.strip()
            new_path = d.parent / new_name
            if new_path.exists():
                messagebox.showerror("Hata", f"Bu isim zaten kullanılıyor: {new_name}")
                return
            try:
                d.rename(new_path)
                # Update meta.json if exists
                meta_path = new_path / "meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        meta["custom_name"] = new_name
                        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                _refresh()
                messagebox.showinfo("Başarılı", f"Arşiv ismi değiştirildi:\n{new_name}")
            except Exception as e:
                messagebox.showerror("Hata", f"İsim değiştirilemedi:\n{e}")

        def _delete_archive():
            d = _sel_dir()
            if not d:
                messagebox.showerror("Hata", "Bir arşiv seçin.")
                return
            if not messagebox.askyesno("Arşivi Sil", f"Bu arşivi silmek istediğinize emin misiniz?\n\n{d.name}\n\nBu işlem geri alınamaz!"):
                return
            try:
                import shutil
                shutil.rmtree(d)
                _refresh()
                messagebox.showinfo("Başarılı", f"Arşiv silindi:\n{d.name}")
            except Exception as e:
                messagebox.showerror("Hata", f"Arşiv silinemedi:\n{e}")

        def _restore_archive():
            d = _sel_dir()
            if not d:
                messagebox.showerror("Hata", "Bir arşiv seçin.")
                return
            if not messagebox.askyesno(
                "Arşivi Geri Yükle",
                f"Bu arşivi output_lines/ klasörüne geri yüklemek istediğinize emin misiniz?\n\n"
                f"{d.name}\n\n"
                f"Mevcut output_lines/ dosyaları üzerine yazılacak!"
            ):
                return
            try:
                from src.doc_archive import restore_archive_to_outputs
                def log_cb(msg, level):
                    log_message(f"GERİ YÜKLEME: {msg}", level)
                success = restore_archive_to_outputs(d, status_callback=log_cb)
                if success:
                    messagebox.showinfo(
                        "Başarılı",
                        f"Arşiv geri yüklendi:\n{d.name}\n\n"
                        f"Artık bu arşivin üzerine ekstra spellcheck veya ikinci nüsha ekleyebilirsiniz."
                    )
                else:
                    messagebox.showerror("Hata", "Arşiv geri yüklenemedi. Log mesajlarına bakın.")
            except Exception as e:
                messagebox.showerror("Hata", f"Arşiv geri yüklenemedi:\n{e}")

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(btns, text="Yenile", command=_refresh).pack(side=tk.LEFT)
        ttk.Button(btns, text="İsim Değiştir", command=_rename_archive).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Sil", command=_delete_archive).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Geri Yükle (output_lines/)", command=_restore_archive, style="Accent.TButton").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Seçili Arşivi Aç (Viewer)", command=_open_viewer, style="Accent.TButton").pack(side=tk.RIGHT)

        lb.bind("<<ListboxSelect>>", _update_info)
        _refresh()

    # -------------------------
    # Primary action buttons (top)
    # -------------------------
    top_actions = ttk.Frame(left_panel)
    top_actions.pack(fill=tk.X, pady=(0, 12))

    ttk.Button(top_actions, text="TÜMÜNÜ ÇALIŞTIR (Nüsha 1)", command=run_all, style="Accent.TButton").pack(fill=tk.X)

    def run_all_nusha2():
        """Nüsha 2 için: Pages2 -> Lines2 -> OCR2 -> (opsiyonel) Alignment + Viewer"""
        def _run():
            # IMPORTANT: stage handlers (run_pages2/run_lines2/run_ocr2) spawn their own threads.
            # For "TÜMÜNÜ ÇALIŞTIR", we must run sequentially in THIS thread, otherwise
            # Lines/OCR starts before Pages finishes and we get "satır kayıtları bulunamadı".
            try:
                if not validate_inputs2():
                    return

                # --- Pages (N2) ---
                update_stage_status("pages2", "Çalışıyor...")
                log_message("PAGES (N2): PDF işleniyor (PNG'e dönüştürülüyor)...", "INFO")
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf2_var.get()), dpi=dpi, pages_dir=NUSHA2_PAGES_DIR)
                log_message(f"✓ PAGES (N2) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages2", "✓ Tamamlandı")

                # --- Lines (N2) ---
                update_stage_status("lines2", "Çalışıyor...")
                log_message(f"LINES (N2): {len(pages)} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA2_LINES_MANIFEST.exists():
                    NUSHA2_LINES_MANIFEST.unlink()
                with NUSHA2_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA2_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N2) Sayfa {idx + 1}/{len(pages)} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA2_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA2_LINES_MANIFEST)
                log_message(f"✓ LINES (N2) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines2", "✓ Tamamlandı")

                # --- OCR (N2) ---
                if ocr_var.get():
                    update_stage_status("ocr2", "Çalışıyor...")
                    log_message(f"OCR (N2): Google Vision OCR yapılıyor... ({len(ordered_recs)} satır)", "INFO")
                    from src.ocr import ocr_lines_with_google_vision_api
                    ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
                    vkey = get_google_vision_api_key()
                    from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                    ok, total = ocr_lines_with_google_vision_api(
                        ordered_line_paths,
                        api_key=vkey,
                        timeout=VISION_TIMEOUT,
                        retries=VISION_RETRIES,
                        backoff_base=VISION_BACKOFF_BASE,
                        max_dim=VISION_MAX_DIM,
                        jpeg_quality=VISION_JPEG_QUALITY,
                        sleep_s=0.10,
                        status_callback=log_message,
                        ocr_dir=NUSHA2_OCR_DIR,
                    )
                    log_message(f"✓ OCR (N2) tamamlandı: {ok}/{total} başarılı", "INFO")
                    update_stage_status("ocr2", "✓ Tamamlandı")
                else:
                    update_stage_status("ocr2", "Atlandı")

                # Alignment/viewer shared: if docx is set, refresh combined alignment + viewer
                if docx_var.get().strip():
                    try:
                        run_alignment2()
                        run_viewer()
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"HATA (TÜMÜNÜ N2): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
        threading.Thread(target=_run, daemon=True).start()

    ttk.Button(top_actions, text="TÜMÜNÜ ÇALIŞTIR (Nüsha 2)", command=run_all_nusha2, style="Accent.TButton").pack(fill=tk.X, pady=(8, 0))

    def run_all_nusha3():
        """Nüsha 3 için: Pages3 -> Lines3 -> OCR3 -> (opsiyonel) Alignment + Viewer"""
        def _run():
            # Sequential run (same reason as N2)
            try:
                if not validate_inputs3():
                    return

                # --- Pages (N3) ---
                update_stage_status("pages3", "Çalışıyor...")
                log_message("PAGES (N3): PDF işleniyor (PNG'e dönüştürülüyor)...", "INFO")
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf3_var.get()), dpi=dpi, pages_dir=NUSHA3_PAGES_DIR)
                log_message(f"✓ PAGES (N3) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages3", "✓ Tamamlandı")

                # --- Lines (N3) ---
                update_stage_status("lines3", "Çalışıyor...")
                log_message(f"LINES (N3): {len(pages)} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA3_LINES_MANIFEST.exists():
                    NUSHA3_LINES_MANIFEST.unlink()
                with NUSHA3_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA3_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N3) Sayfa {idx + 1}/{len(pages)} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA3_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA3_LINES_MANIFEST)
                log_message(f"✓ LINES (N3) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines3", "✓ Tamamlandı")

                # --- OCR (N3) ---
                if ocr_var.get():
                    update_stage_status("ocr3", "Çalışıyor...")
                    log_message(f"OCR (N3): Google Vision OCR yapılıyor... ({len(ordered_recs)} satır)", "INFO")
                    from src.ocr import ocr_lines_with_google_vision_api
                    ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
                    vkey = get_google_vision_api_key()
                    from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                    ok, total = ocr_lines_with_google_vision_api(
                        ordered_line_paths,
                        api_key=vkey,
                        timeout=VISION_TIMEOUT,
                        retries=VISION_RETRIES,
                        backoff_base=VISION_BACKOFF_BASE,
                        max_dim=VISION_MAX_DIM,
                        jpeg_quality=VISION_JPEG_QUALITY,
                        sleep_s=0.10,
                        status_callback=log_message,
                        ocr_dir=NUSHA3_OCR_DIR,
                    )
                    log_message(f"✓ OCR (N3) tamamlandı: {ok}/{total} başarılı", "INFO")
                    update_stage_status("ocr3", "✓ Tamamlandı")
                else:
                    update_stage_status("ocr3", "Atlandı")

                if docx_var.get().strip():
                    try:
                        run_alignment3()
                        run_viewer()
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"HATA (TÜMÜNÜ N3): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
        threading.Thread(target=_run, daemon=True).start()

    ttk.Button(top_actions, text="TÜMÜNÜ ÇALIŞTIR (Nüsha 3)", command=run_all_nusha3, style="Accent.TButton").pack(fill=tk.X, pady=(8, 0))

    def run_all_nusha4():
        """Nüsha 4 için: Pages4 -> Lines4 -> OCR4 -> (opsiyonel) Alignment + Viewer"""
        def _run():
            try:
                if not validate_inputs4():
                    return

                # --- Pages (N4) ---
                update_stage_status("pages4", "Çalışıyor...")
                log_message("PAGES (N4): PDF işleniyor (PNG'e dönüştürülüyor)...", "INFO")
                from src.pdf_processor import pdf_to_page_pngs
                dpi = int(dpi_var.get().strip())
                pages = pdf_to_page_pngs(Path(pdf4_var.get()), dpi=dpi, pages_dir=NUSHA4_PAGES_DIR)
                log_message(f"✓ PAGES (N4) tamamlandı: {len(pages)} sayfa üretildi", "INFO")
                update_stage_status("pages4", "✓ Tamamlandı")

                # --- Lines (N4) ---
                update_stage_status("lines4", "Çalışıyor...")
                log_message(f"LINES (N4): {len(pages)} sayfa PNG bulundu, satırlara bölünüyor (Kraken)...", "INFO")
                from src.kraken_processor import split_page_to_lines, load_line_records_ordered
                import json as _json
                if NUSHA4_LINES_MANIFEST.exists():
                    NUSHA4_LINES_MANIFEST.unlink()
                with NUSHA4_LINES_MANIFEST.open("a", encoding="utf-8") as mf:
                    for idx, page in enumerate(sorted(NUSHA4_PAGES_DIR.glob("*.png"))):
                        if (idx + 1) % 5 == 0:
                            log_message(f"  (N4) Sayfa {idx + 1}/{len(pages)} işleniyor...", "INFO")
                        records = split_page_to_lines(page, lines_dir=NUSHA4_LINES_DIR)
                        for rec in records:
                            mf.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                ordered_recs = load_line_records_ordered(manifest_path=NUSHA4_LINES_MANIFEST)
                log_message(f"✓ LINES (N4) tamamlandı: {len(ordered_recs)} satır oluşturuldu", "INFO")
                update_stage_status("lines4", "✓ Tamamlandı")

                # --- OCR (N4) ---
                if ocr_var.get():
                    update_stage_status("ocr4", "Çalışıyor...")
                    log_message(f"OCR (N4): Google Vision OCR yapılıyor... ({len(ordered_recs)} satır)", "INFO")
                    from src.ocr import ocr_lines_with_google_vision_api
                    ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
                    vkey = get_google_vision_api_key()
                    from src.config import VISION_TIMEOUT, VISION_RETRIES, VISION_BACKOFF_BASE, VISION_MAX_DIM, VISION_JPEG_QUALITY
                    ok, total = ocr_lines_with_google_vision_api(
                        ordered_line_paths,
                        api_key=vkey,
                        timeout=VISION_TIMEOUT,
                        retries=VISION_RETRIES,
                        backoff_base=VISION_BACKOFF_BASE,
                        max_dim=VISION_MAX_DIM,
                        jpeg_quality=VISION_JPEG_QUALITY,
                        sleep_s=0.10,
                        status_callback=log_message,
                        ocr_dir=NUSHA4_OCR_DIR,
                    )
                    log_message(f"✓ OCR (N4) tamamlandı: {ok}/{total} başarılı", "INFO")
                    update_stage_status("ocr4", "✓ Tamamlandı")
                else:
                    update_stage_status("ocr4", "Atlandı")

                if docx_var.get().strip():
                    try:
                        run_alignment4()
                        run_viewer4()
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"HATA (TÜMÜNÜ N4): {e}", "ERROR")
                log_message(f"Hata detayı:\n{traceback.format_exc()}", "ERROR")
        threading.Thread(target=_run, daemon=True).start()

    ttk.Button(top_actions, text="TÜMÜNÜ ÇALIŞTIR (Nüsha 4)", command=run_all_nusha4, style="Accent.TButton").pack(fill=tk.X, pady=(8, 0))

    # -------------------------
    # Nüsha stage buttons (horizontally scrollable)
    # -------------------------
    cols_wrap = ttk.Frame(left_panel)
    cols_wrap.pack(fill=tk.X, pady=(0, 12))

    cols_canvas = tk.Canvas(cols_wrap, highlightthickness=0, borderwidth=0, height=360)
    cols_scroll_x = ttk.Scrollbar(cols_wrap, orient="horizontal", command=cols_canvas.xview)
    cols_canvas.configure(xscrollcommand=cols_scroll_x.set)

    cols_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
    cols_canvas.pack(side=tk.TOP, fill=tk.X, expand=False)

    cols = ttk.Frame(cols_canvas, style="TFrame")
    cols_window_id = cols_canvas.create_window((0, 0), window=cols, anchor="nw")

    def _sync_cols_scroll_region(_event=None):
        try:
            cols_canvas.configure(scrollregion=cols_canvas.bbox("all"))
        except Exception:
            pass

    def _sync_cols_width(event=None):
        # keep inner frame height; allow x-scroll; don't force width to canvas width
        try:
            cols_canvas.itemconfig(cols_window_id, height=cols.winfo_reqheight())
        except Exception:
            pass

    cols.bind("<Configure>", _sync_cols_scroll_region)
    cols_canvas.bind("<Configure>", _sync_cols_width)

    # Shift+MouseWheel to horizontal scroll on this block (nice UX on macOS/Windows)
    def _cols_wheel(ev):
        try:
            if getattr(ev, "delta", 0):
                delta = ev.delta
                step = int(-1 * (delta / 120)) if abs(delta) >= 120 else int(-1 * delta)
                if step == 0:
                    step = -1 if delta > 0 else 1
                cols_canvas.xview_scroll(step * 3, "units")
            else:
                if ev.num == 4:
                    cols_canvas.xview_scroll(-3, "units")
                elif ev.num == 5:
                    cols_canvas.xview_scroll(3, "units")
        except Exception:
            pass

    cols_canvas.bind("<Shift-MouseWheel>", _cols_wheel)
    cols_canvas.bind("<Shift-Button-4>", _cols_wheel)
    cols_canvas.bind("<Shift-Button-5>", _cols_wheel)

    col1 = ttk.LabelFrame(cols, text="Nüsha 1", padding=(12, 10))
    col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    col2 = ttk.LabelFrame(cols, text="Nüsha 2", padding=(12, 10))
    col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

    col3 = ttk.LabelFrame(cols, text="Nüsha 3", padding=(12, 10))
    col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

    col4 = ttk.LabelFrame(cols, text="Nüsha 4", padding=(12, 10))
    col4.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

    ttk.Button(col1, text="1. Pages", command=run_pages).pack(fill=tk.X, pady=4)
    ttk.Button(col1, text="2. Lines", command=run_lines).pack(fill=tk.X, pady=4)
    ttk.Button(col1, text="3. OCR", command=run_ocr).pack(fill=tk.X, pady=4)
    ttk.Button(col1, text="4. Spellcheck", command=run_spellcheck).pack(fill=tk.X, pady=4)
    ttk.Button(col1, text="5. Alignment", command=run_alignment).pack(fill=tk.X, pady=4)
    ttk.Button(col1, text="6. Viewer", command=run_viewer).pack(fill=tk.X, pady=4)

    ttk.Button(col2, text="1. Pages (N2)", command=run_pages2).pack(fill=tk.X, pady=4)
    ttk.Button(col2, text="2. Lines (N2)", command=run_lines2).pack(fill=tk.X, pady=4)
    ttk.Button(col2, text="3. OCR (N2)", command=run_ocr2).pack(fill=tk.X, pady=4)
    ttk.Separator(col2, orient="horizontal").pack(fill="x", pady=8)
    ttk.Button(col2, text="5. Alignment (N2)", command=run_alignment2).pack(fill=tk.X, pady=4)
    ttk.Button(col2, text="6. Viewer (N2)", command=run_viewer2).pack(fill=tk.X, pady=4)

    ttk.Button(col3, text="1. Pages (N3)", command=run_pages3).pack(fill=tk.X, pady=4)
    ttk.Button(col3, text="2. Lines (N3)", command=run_lines3).pack(fill=tk.X, pady=4)
    ttk.Button(col3, text="3. OCR (N3)", command=run_ocr3).pack(fill=tk.X, pady=4)
    ttk.Separator(col3, orient="horizontal").pack(fill="x", pady=8)
    ttk.Button(col3, text="5. Alignment (N3)", command=run_alignment3).pack(fill=tk.X, pady=4)
    ttk.Button(col3, text="6. Viewer (N3)", command=run_viewer3).pack(fill=tk.X, pady=4)

    ttk.Button(col4, text="1. Pages (N4)", command=run_pages4).pack(fill=tk.X, pady=4)
    ttk.Button(col4, text="2. Lines (N4)", command=run_lines4).pack(fill=tk.X, pady=4)
    ttk.Button(col4, text="3. OCR (N4)", command=run_ocr4).pack(fill=tk.X, pady=4)
    ttk.Separator(col4, orient="horizontal").pack(fill="x", pady=8)
    ttk.Button(col4, text="5. Alignment (N4)", command=run_alignment4).pack(fill=tk.X, pady=4)
    ttk.Button(col4, text="6. Viewer (N4)", command=run_viewer4).pack(fill=tk.X, pady=4)

    ttk.Button(left_panel, text="Eski Sonuçlar (doc_archives)…", command=open_old_results).pack(fill=tk.X, pady=(0, 12))

    # Sağ panel - Durum ve Log (Scrollable)
    right_container = ttk.Frame(main_frame, style="TFrame")
    right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    right_canvas = tk.Canvas(right_container, highlightthickness=0, borderwidth=0)
    right_scroll = ttk.Scrollbar(right_container, orient="vertical", command=right_canvas.yview)
    right_canvas.configure(yscrollcommand=right_scroll.set)

    right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    right_panel = ttk.Frame(right_canvas, style="TFrame")
    right_window_id = right_canvas.create_window((0, 0), window=right_panel, anchor="nw")

    def _sync_right_scroll_region(_event=None):
        try:
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        except Exception:
            pass

    def _sync_right_width(event=None):
        try:
            right_canvas.itemconfig(right_window_id, width=right_canvas.winfo_width())
        except Exception:
            pass

    right_panel.bind("<Configure>", _sync_right_scroll_region)
    right_canvas.bind("<Configure>", _sync_right_width)

    # Mousewheel - Right
    def _bind_mousewheel_to_right(_event=None):
        def _on_mousewheel(e):
            try:
                if getattr(e, "delta", 0):
                    delta = e.delta
                    step = int(-1 * (delta / 120)) if abs(delta) >= 120 else int(-1 * delta)
                    if step == 0: step = -1 if delta > 0 else 1
                    right_canvas.yview_scroll(step, "units")
                else:
                    if e.num == 4: right_canvas.yview_scroll(-3, "units")
                    elif e.num == 5: right_canvas.yview_scroll(3, "units")
            except Exception: pass
        root.bind_all("<MouseWheel>", _on_mousewheel)
        root.bind_all("<Button-4>", _on_mousewheel)
        root.bind_all("<Button-5>", _on_mousewheel)

    def _unbind_mousewheel_from_right(_event=None):
        root.unbind_all("<MouseWheel>")
        root.unbind_all("<Button-4>")
        root.unbind_all("<Button-5>")

    right_canvas.bind("<Enter>", _bind_mousewheel_to_right)
    right_canvas.bind("<Leave>", _unbind_mousewheel_from_right)
    right_panel.bind("<Enter>", _bind_mousewheel_to_right)
    right_panel.bind("<Leave>", _unbind_mousewheel_from_right)

    # Başlık kartı
    header = ttk.Frame(right_panel, style="Card.TFrame")
    header.pack(fill=tk.X, pady=(0, 12))

    header_top = ttk.Frame(header, style="Card.TFrame")
    header_top.pack(fill=tk.X, padx=14, pady=(12, 2))

    ttk.Label(header_top, text="Kraken + Vision OCR + Satır Satır Hizalama", style="Card.TLabel").pack(side=tk.LEFT, anchor="w")

    def open_dual_viewer():
        """
        Generate a dual-copy viewer (both nushas visible in parallel) and open it.
        Requires an alignment payload with has_alt/aligned_alt present.
        """
        payload = stage_results.get("alignment_payload")
        if payload is None:
            align_exist, align_path = check_alignment_exist()
            if align_exist:
                try:
                    payload = json.loads(align_path.read_text(encoding="utf-8"))
                    stage_results["alignment_payload"] = payload
                except Exception as e:
                    messagebox.showerror("Hata", f"Alignment dosyası okunamadı:\n{e}")
                    return
            else:
                messagebox.showerror("Hata", "Alignment yok. Önce Alignment çalıştırın (ve Nüsha 2 de hazır olsun).")
                return

        if not (isinstance(payload, dict) and payload.get("has_alt") and isinstance(payload.get("aligned_alt"), list) and payload.get("aligned_alt")):
            messagebox.showerror("Hata", "Çift nüsha viewer için Nüsha 2 alignment gerekli. Önce Nüsha 2 Pages/Lines/OCR + Alignment (N2) çalıştırın.")
            return

        try:
            from src.viewer import write_viewer_html
            from src.config import VIEWER_DUAL_HTML
            write_viewer_html(payload, dual=True)
            webbrowser.open(VIEWER_DUAL_HTML.as_uri())
        except Exception as e:
            messagebox.showerror("Hata", f"Çift nüsha viewer oluşturulamadı:\n{e}")

    def ocr_to_ocr_match():
        """
        Compute OCR↔OCR mapping (Nüsha1 OCR -> Nüsha2 OCR) and update alignment payload.
        This is independent of tahkik; it allows jumping from N1 to matching N2 lines.
        """
        payload = stage_results.get("alignment_payload")
        if payload is None:
            align_exist, align_path = check_alignment_exist()
            if align_exist:
                try:
                    payload = json.loads(align_path.read_text(encoding="utf-8"))
                    stage_results["alignment_payload"] = payload
                except Exception as e:
                    messagebox.showerror("Hata", f"Alignment dosyası okunamadı:\n{e}")
                    return
            else:
                messagebox.showerror("Hata", "Alignment yok. Önce Alignment çalıştırın (Nüsha 1).")
                return

        try:
            from src.alignment import attach_ocr_to_ocr_links
            # Update payload in-memory and on-disk
            payload2 = attach_ocr_to_ocr_links(payload, status_callback=log_message, max_keep=6)
            stage_results["alignment_payload"] = payload2
            # persist back to alignment.json so viewers can use it
            try:
                from src.config import ALIGNMENT_JSON
                ALIGNMENT_JSON.write_text(json.dumps(payload2, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            messagebox.showinfo("OCR↔OCR", "OCR↔OCR eşleştirme tamamlandı. Viewer/Çift Nüsha Viewer açabilirsiniz.")
        except Exception as e:
            messagebox.showerror("Hata", f"OCR↔OCR eşleştirme başarısız:\n{e}")

    ttk.Button(header_top, text="Çift Nüsha Viewer", command=open_dual_viewer, style="Accent.TButton").pack(side=tk.RIGHT)
    ttk.Button(header_top, text="OCR↔OCR Eşleştir", command=ocr_to_ocr_match, style="Accent.TButton").pack(side=tk.RIGHT, padx=(0, 10))

    ttk.Label(
        header,
        text="Aşamaları tek tek veya toplu çalıştırın. Loglar canlı akar; hata olursa hangi aşamada olduğu görünür.",
        style="Muted.TLabel",
    ).pack(anchor="w", padx=14, pady=(0, 12))

    # Font ayarı
    font_frame = ttk.LabelFrame(left_panel, text="Görünüm", padding=(12, 10))
    font_frame.pack(fill=tk.X, pady=(0, 12))
    row = ttk.Frame(font_frame)
    row.pack(fill=tk.X)
    ttk.Label(row, text="Punto (Font Boyutu):").pack(side=tk.LEFT)
    font_spin = ttk.Spinbox(row, from_=8, to=28, textvariable=font_size_var, width=6, command=lambda: update_fonts(font_size_var.get()))
    font_spin.pack(side=tk.LEFT, padx=(10, 0))

    def _on_font_change(*_):
        try:
            update_fonts(font_size_var.get())
        except Exception:
            pass

    font_size_var.trace_add("write", _on_font_change)

    # PDF seçimi
    io_frame = ttk.LabelFrame(left_panel, text="Girdiler", padding=(12, 10))
    io_frame.pack(fill=tk.X, pady=(0, 12))

    ttk.Label(io_frame, text="PDF Dosyası").pack(anchor="w")
    pdf_entry = ttk.Entry(io_frame, textvariable=pdf_var)
    pdf_entry.pack(fill=tk.X, pady=(6, 8))
    ttk.Button(io_frame, text="PDF Seç", command=choose_pdf).pack(anchor="w")

    ttk.Label(io_frame, text="2. Nüsha PDF (İkinci PDF)").pack(anchor="w", pady=(10, 0))
    pdf2_entry = ttk.Entry(io_frame, textvariable=pdf2_var)
    pdf2_entry.pack(fill=tk.X, pady=(6, 8))
    ttk.Button(io_frame, text="2. Nüsha PDF Seç", command=choose_pdf2).pack(anchor="w")

    ttk.Label(io_frame, text="3. Nüsha PDF (Üçüncü PDF)").pack(anchor="w", pady=(10, 0))
    pdf3_entry = ttk.Entry(io_frame, textvariable=pdf3_var)
    pdf3_entry.pack(fill=tk.X, pady=(6, 8))
    ttk.Button(io_frame, text="3. Nüsha PDF Seç", command=choose_pdf3).pack(anchor="w")

    ttk.Label(io_frame, text="4. Nüsha PDF (Dördüncü PDF)").pack(anchor="w", pady=(10, 0))
    pdf4_entry = ttk.Entry(io_frame, textvariable=pdf4_var)
    pdf4_entry.pack(fill=tk.X, pady=(6, 8))
    ttk.Button(io_frame, text="4. Nüsha PDF Seç", command=choose_pdf4).pack(anchor="w")

    # DPI ve OCR
    dpi_frame = ttk.Frame(io_frame)
    dpi_frame.pack(fill=tk.X, pady=(10, 0))
    ttk.Label(dpi_frame, text="DPI").pack(side=tk.LEFT)
    ttk.Entry(dpi_frame, textvariable=dpi_var, width=8).pack(side=tk.LEFT, padx=(8, 14))
    ttk.Checkbutton(dpi_frame, text="Google Vision OCR", variable=ocr_var).pack(side=tk.LEFT)

    # Word seçimi
    ttk.Label(io_frame, text="Tahkik Dizgisi (Word .docx)").pack(anchor="w", pady=(12, 0))
    docx_entry = ttk.Entry(io_frame, textvariable=docx_var)
    docx_entry.pack(fill=tk.X, pady=(6, 8))
    ttk.Button(io_frame, text="Word (.docx) Seç", command=choose_docx).pack(anchor="w")

    # AI Model seçimi
    ai_frame = ttk.LabelFrame(left_panel, text="AI Model Seçimi", padding=(12, 10))
    ai_frame.pack(fill=tk.X, pady=(0, 12))
    ttk.Radiobutton(ai_frame, text="AI Kullanma", variable=ai_model_var, value="none").pack(anchor="w")
    ttk.Radiobutton(ai_frame, text="Sadece Gemini", variable=ai_model_var, value="gemini").pack(anchor="w")
    ttk.Radiobutton(ai_frame, text="Sadece OpenAI", variable=ai_model_var, value="openai").pack(anchor="w")
    ttk.Radiobutton(ai_frame, text="Sadece Claude (Opus 4.5)", variable=ai_model_var, value="claude").pack(anchor="w")
    ttk.Radiobutton(ai_frame, text="İkisi de (Gemini + OpenAI)", variable=ai_model_var, value="both").pack(anchor="w")
    ttk.Radiobutton(ai_frame, text="Hepsi (Gemini + OpenAI + Claude)", variable=ai_model_var, value="all").pack(anchor="w")
    ttk.Separator(ai_frame, orient="horizontal").pack(fill="x", pady=6)
    ttk.Label(ai_frame, text="Not: Spellcheck her zaman mevcut sonuçlara eklenir (eski sonuçlar korunur).", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
    ttk.Checkbutton(ai_frame, text="AI API trace penceresini aç (PROMPT + RESPONSE) ve kaydet", variable=sc_verbose_ai_var).pack(anchor="w")

    # Spellcheck başlangıç paragrafı (satır gibi düşün: Word paragraf numarası)
    sp_row = ttk.Frame(ai_frame)
    sp_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Label(sp_row, text="Spellcheck başlangıç paragrafı (P):").pack(side=tk.LEFT)
    ttk.Spinbox(sp_row, from_=1, to=999999, textvariable=sc_start_para_var, width=8).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Label(ai_frame, text="Not: Spellcheck her zaman mevcut sonuçlara eklenir.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    # Paragraf seçimi (multi-select)
    sel_row = ttk.Frame(ai_frame)
    sel_row.pack(fill=tk.X, pady=(8, 0))
    sel_label = ttk.Label(sel_row, text="Seçim: Hepsi", style="Muted.TLabel")
    sel_label.pack(side=tk.LEFT)

    def _resolve_docx_for_selection() -> Optional[Path]:
        p = (docx_var.get() or "").strip()
        if p:
            return Path(p)
        sc_exist, sc_path = check_spellcheck_exist()
        if sc_exist:
            try:
                sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
                dp = (sc_data.get("docx_path") or "").strip()
                if dp:
                    return Path(dp)
            except Exception:
                return None
        return None

    def _update_sel_label():
        idxs = sc_selected_paras.get("indices")
        if not idxs:
            sel_label.config(text="Seçim: Hepsi")
        else:
            idxs = sorted([int(x) for x in idxs])
            if len(idxs) == 1:
                sel_label.config(text=f"Seçim: P{idxs[0]}")
            else:
                sel_label.config(text=f"Seçim: {len(idxs)} paragraf (P{idxs[0]}–P{idxs[-1]})")

    def open_paragraph_picker(start_spellcheck: bool = False):
        docx_path = _resolve_docx_for_selection()
        if not docx_path or (not docx_path.exists()):
            messagebox.showerror("Hata", "Paragrafları listelemek için Word (.docx) seçilmeli (veya mevcut spellcheck.json içinde docx_path olmalı).")
            return
        try:
            from src.document import read_docx_paragraphs
            paras = read_docx_paragraphs(docx_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Word paragrafları okunamadı: {e}")
            return

        win = tk.Toplevel(root)
        win.title("Spellcheck için Paragrafları Seç")
        win.geometry("980x720")

        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=12, pady=10)
        ttk.Label(top, text=f"Toplam paragraf: {len(paras)} • Çoklu seçim: Ctrl/Shift").pack(anchor="w")
        ttk.Label(top, text=str(docx_path), style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        mid = ttk.Frame(win)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        lb = tk.Listbox(mid, selectmode=tk.EXTENDED)
        sb = ttk.Scrollbar(mid, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for i, t in enumerate(paras, start=1):
            snip = " ".join(t.split()[:14])
            lb.insert(tk.END, f"P{i:03d}  {snip}")

        # Preselect current
        cur = sc_selected_paras.get("indices")
        if isinstance(cur, list) and cur:
            for pidx in cur:
                if isinstance(pidx, int) and 1 <= pidx <= len(paras):
                    lb.selection_set(pidx - 1)

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))

        def _select_all():
            lb.selection_set(0, tk.END)

        def _clear():
            lb.selection_clear(0, tk.END)

        def _apply_and_close(do_start: bool):
            sel = [i + 1 for i in lb.curselection()]
            sc_selected_paras["indices"] = sel if sel else None
            _update_sel_label()
            try:
                win.destroy()
            except Exception:
                pass
            if do_start:
                run_spellcheck()

        ttk.Button(btns, text="Hepsini seç", command=_select_all).pack(side=tk.LEFT)
        ttk.Button(btns, text="Seçimi temizle (Hepsi)", command=_clear).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Uygula", command=lambda: _apply_and_close(False)).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Uygula ve Başlat Spellcheck", command=lambda: _apply_and_close(True), style="Accent.TButton").pack(side=tk.RIGHT, padx=(0, 8))

    ttk.Button(sel_row, text="Paragrafları Seç…", command=lambda: open_paragraph_picker(False)).pack(side=tk.RIGHT)
    ttk.Button(ai_frame, text="Paragrafları Seç ve Başlat Spellcheck", command=lambda: open_paragraph_picker(True)).pack(fill=tk.X, pady=(8, 0))

    ttk.Checkbutton(left_panel, text="Tahkik ile satır satır hizala ve viewer üret", variable=align_var).pack(anchor="w", pady=(0, 12))

    # Dosya durumu gösterimi
    status_check_frame = ttk.LabelFrame(left_panel, text="Mevcut Dosya Durumu", padding=(12, 10))
    status_check_frame.pack(fill=tk.X, pady=(0, 12))
    
    def refresh_file_status():
        """Dosya durumunu güncelle"""
        status_lines = []
        
        pages_exist, pages_count = check_pages_exist()
        status_lines.append(f"Pages: {'✓' if pages_exist else '✗'} ({pages_count})")
        
        lines_exist, lines_count = check_lines_exist()
        status_lines.append(f"Lines: {'✓' if lines_exist else '✗'} ({lines_count})")
        
        ocr_exist, ocr_count = check_ocr_exist()
        status_lines.append(f"OCR: {'✓' if ocr_exist else '✗'} ({ocr_count})")

        # Nüsha 2
        p2_exist, p2_cnt = _check_pages_exist_dir(NUSHA2_PAGES_DIR)
        status_lines.append(f"N2 Pages: {'✓' if p2_exist else '✗'} ({p2_cnt})")
        l2_exist, l2_cnt = _check_lines_exist_dir(NUSHA2_LINES_DIR, NUSHA2_LINES_MANIFEST)
        status_lines.append(f"N2 Lines: {'✓' if l2_exist else '✗'} ({l2_cnt})")
        o2_exist, o2_cnt = _check_ocr_exist_dir(NUSHA2_OCR_DIR)
        status_lines.append(f"N2 OCR: {'✓' if o2_exist else '✗'} ({o2_cnt})")

        # Nüsha 3
        p3_exist, p3_cnt = _check_pages_exist_dir(NUSHA3_PAGES_DIR)
        status_lines.append(f"N3 Pages: {'✓' if p3_exist else '✗'} ({p3_cnt})")
        l3_exist, l3_cnt = _check_lines_exist_dir(NUSHA3_LINES_DIR, NUSHA3_LINES_MANIFEST)
        status_lines.append(f"N3 Lines: {'✓' if l3_exist else '✗'} ({l3_cnt})")
        o3_exist, o3_cnt = _check_ocr_exist_dir(NUSHA3_OCR_DIR)
        status_lines.append(f"N3 OCR: {'✓' if o3_exist else '✗'} ({o3_cnt})")

        # Nüsha 4
        p4_exist, p4_cnt = _check_pages_exist_dir(NUSHA4_PAGES_DIR)
        status_lines.append(f"N4 Pages: {'✓' if p4_exist else '✗'} ({p4_cnt})")
        l4_exist, l4_cnt = _check_lines_exist_dir(NUSHA4_LINES_DIR, NUSHA4_LINES_MANIFEST)
        status_lines.append(f"N4 Lines: {'✓' if l4_exist else '✗'} ({l4_cnt})")
        o4_exist, o4_cnt = _check_ocr_exist_dir(NUSHA4_OCR_DIR)
        status_lines.append(f"N4 OCR: {'✓' if o4_exist else '✗'} ({o4_cnt})")
        
        sc_exist, _ = check_spellcheck_exist()
        status_lines.append(f"Spellcheck: {'✓' if sc_exist else '✗'}")
        
        align_exist, _ = check_alignment_exist()
        status_lines.append(f"Alignment: {'✓' if align_exist else '✗'}")
        
        file_status_label.config(text="\n".join(status_lines))
    
    file_status_label = ttk.Label(status_check_frame, text="Dosya durumu kontrol ediliyor...", style="Monospace.TLabel", justify=tk.LEFT)
    file_status_label.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Button(status_check_frame, text="Durumu Yenile", command=refresh_file_status).pack(anchor="w")
    
    # İlk durum kontrolü
    refresh_file_status()

    # Log alanı (Yukarı taşındı)
    log_frame = ttk.LabelFrame(right_panel, text="İşlem Logları", padding=(12, 10))
    log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 12))
    
    # Log toolbar
    log_tools = ttk.Frame(log_frame)
    log_tools.pack(fill=tk.X, pady=(0, 4))
    
    ttk.Checkbutton(log_tools, text="Otomatik Kaydır", variable=log_auto_scroll_var).pack(side=tk.LEFT, padx=(0, 8))
    
    def _manual_scroll_down():
        if log_text:
            log_text.see(tk.END)
            
    def _clear_log():
        if log_text:
            log_text.delete("1.0", tk.END)
            
    ttk.Button(log_tools, text="▼", width=4, command=_manual_scroll_down, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(log_tools, text="Temizle", command=_clear_log).pack(side=tk.RIGHT)
    
    log_text = scrolledtext.ScrolledText(
        log_frame, 
        height=15, 
        width=60,
        wrap=tk.WORD,
        bg="#0B1220",
        fg="#E5E7EB",
        insertbackground="#E5E7EB",
        relief="flat",
        borderwidth=0
    )
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # İlk mesaj
    log_text.insert(tk.END, "Hazır. İşlemi başlatmak için butonları kullanın.\n")
    log_text.see(tk.END)

    # Aşama durumları (Nüsha 1 + Nüsha 2)
    status_frame1 = ttk.LabelFrame(right_panel, text="Aşama Durumları (Nüsha 1)", padding=(12, 10))
    status_frame1.pack(fill=tk.X, pady=(0, 12))

    stages_info_1 = [
        ("pages", "1. Pages"),
        ("lines", "2. Lines"),
        ("ocr", "3. OCR"),
        ("spellcheck", "4. Spellcheck"),
        ("alignment", "5. Alignment"),
        ("viewer", "6. Viewer"),
    ]

    for stage_key, stage_name in stages_info_1:
        stage_row = ttk.Frame(status_frame1)
        stage_row.pack(fill=tk.X, pady=4)
        ttk.Label(stage_row, text=stage_name, width=18).pack(side=tk.LEFT)
        ttk.Label(stage_row, textvariable=stage_status[stage_key], width=16, style="Muted.TLabel").pack(side=tk.LEFT)

    status_frame2 = ttk.LabelFrame(right_panel, text="Aşama Durumları (Nüsha 2)", padding=(12, 10))
    status_frame2.pack(fill=tk.X, pady=(0, 12))

    stages_info_2 = [
        ("pages2", "1. Pages (N2)"),
        ("lines2", "2. Lines (N2)"),
        ("ocr2", "3. OCR (N2)"),
        ("alignment2", "5. Alignment (N2)"),
        ("viewer2", "6. Viewer (N2)"),
    ]

    for stage_key, stage_name in stages_info_2:
        stage_row = ttk.Frame(status_frame2)
        stage_row.pack(fill=tk.X, pady=4)
        ttk.Label(stage_row, text=stage_name, width=18).pack(side=tk.LEFT)
        ttk.Label(stage_row, textvariable=stage_status[stage_key], width=16, style="Muted.TLabel").pack(side=tk.LEFT)

    status_frame3 = ttk.LabelFrame(right_panel, text="Aşama Durumları (Nüsha 3)", padding=(12, 10))
    status_frame3.pack(fill=tk.X, pady=(0, 12))

    stages_info_3 = [
        ("pages3", "1. Pages (N3)"),
        ("lines3", "2. Lines (N3)"),
        ("ocr3", "3. OCR (N3)"),
        ("alignment3", "5. Alignment (N3)"),
        ("viewer3", "6. Viewer (N3)"),
    ]

    for stage_key, stage_name in stages_info_3:
        stage_row = ttk.Frame(status_frame3)
        stage_row.pack(fill=tk.X, pady=4)
        ttk.Label(stage_row, text=stage_name, width=18).pack(side=tk.LEFT)
        ttk.Label(stage_row, textvariable=stage_status[stage_key], width=16, style="Muted.TLabel").pack(side=tk.LEFT)

    status_frame4 = ttk.LabelFrame(right_panel, text="Aşama Durumları (Nüsha 4)", padding=(12, 10))
    status_frame4.pack(fill=tk.X, pady=(0, 12))

    stages_info_4 = [
        ("pages4", "1. Pages (N4)"),
        ("lines4", "2. Lines (N4)"),
        ("ocr4", "3. OCR (N4)"),
        ("alignment4", "5. Alignment (N4)"),
        ("viewer4", "6. Viewer (N4)"),
    ]

    for stage_key, stage_name in stages_info_4:
        stage_row = ttk.Frame(status_frame4)
        stage_row.pack(fill=tk.X, pady=4)
        ttk.Label(stage_row, text=stage_name, width=18).pack(side=tk.LEFT)
        ttk.Label(stage_row, textvariable=stage_status[stage_key], width=16, style="Muted.TLabel").pack(side=tk.LEFT)

    # Log alanı yukarı taşındı

    # İlk font güncellemesi
    update_fonts(default_font_size)

    root.mainloop()
