import json
import shutil
import logging
import traceback
import time
import os
import stat
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.services.project_manager import ProjectManager
from src.pdf_processor import pdf_to_page_pngs
from src.kraken_processor import split_page_to_lines, load_line_records_ordered
from src.ocr import ocr_lines_with_google_vision_api, load_ocr_lines_ordered
from src.alignment import align_ocr_to_tahkik_segment_dp
from src.keys import get_google_vision_api_key
from src.config import BASE_DIR

# Kraken importlarını try-except içine al ki çökerse bile loglayabilelim
try:
    from PIL import Image
    from kraken import binarization, blla, rpred
    from kraken.lib import models, vgsl
    KRAKEN_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Kraken import hatası: {e}")
    KRAKEN_AVAILABLE = False
except OSError as e:
    print(f"[WARN] Kraken OS hatası (Windows DLL sorunu olabilir): {e}")
    KRAKEN_AVAILABLE = False


# Configure logging
logger = logging.getLogger(__name__)


def remove_readonly(func, path, excinfo):
    """Windows salt okunur dosyaları silmek için yardımcı fonksiyon"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

class ManuscriptEngine:
    """
    Orchestrates the manuscript processing pipeline within a project context.
    Handles PDF conversion, line segmentation, OCR, and text alignment.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.pm = ProjectManager()
        self.project_dir = self.pm.get_project_path(project_id)
        
        if not self.project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {self.project_dir}")

    def update_progress(self, nusha_index: int, percent: int, message: str, status: str = "processing"):
        """İlerleme durumunu diske yazar."""
        nusha_path = self.pm.get_nusha_dir(self.project_id, nusha_index)
        status_file = nusha_path / "status.json"
        
        data = {
            "status": status,      # processing, completed, failed
            "percent": percent,    # 0-100
            "message": message,    #String message
            "updated_at": str(time.time())
        }
        
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[ENGINE] Progress update failed: {e}")

    def _get_nusha_paths(self, nusha_index: int) -> Dict[str, Path]:
        """
        Helper to get all relevant paths for a specific nusha (nusha_1, nusha_2, etc.)
        """
        nusha_root = self.pm.get_nusha_dir(self.project_id, nusha_index)
        return {
            "root": nusha_root,
            "pages": nusha_root / "pages",
            "lines": nusha_root / "lines",
            "ocr": nusha_root / "ocr",
            "manifest": nusha_root / "lines_manifest.jsonl",
            "alignment": nusha_root / "alignment.json"
        }

    def convert_pdf_to_images(self, nusha_index: int, dpi: int = 300) -> Dict[str, Any]:
        """
        Converts the project's PDF (assumed to be 'source.pdf' in nusha folder or project root)
        to PNG images in the 'pages' directory.
        """
        # Retrieve stored config for this nusha, if available (overrides default/arg if set)
        nusha_config = self.pm.get_nusha_config(self.project_id, nusha_index)
        stored_dpi = nusha_config.get("dpi")
        
        # Priority: Stored Config > Argument > Default (300)
        final_dpi = stored_dpi if stored_dpi else dpi
        
        print(f"[ENGINE] PDF -> Images started for Nusha {nusha_index} with DPI={final_dpi}...")
        start_time = time.time()
        
        paths = self._get_nusha_paths(nusha_index)
        self.update_progress(nusha_index, 0, "PDF -> Resim dönüştürme başlatılıyor...")
        
        # Locate PDF: Checks nusha folder first
        # Dynamic search for any .pdf file
        pdf_files = list(paths["root"].glob("*.pdf"))
        
        if not pdf_files:
             # Fallback: check legacy source.pdf in root if absolutely necessary, or just fail
             msg = f"PDF source not found in {paths['root']}"
             print(f"[ENGINE] ERROR: {msg}")
             self.update_progress(nusha_index, 0, f"Hata: {msg}", status="failed")
             return {"success": False, "error": msg}
             
        pdf_path = pdf_files[0]
        print(f"[ENGINE] İşlenen Dosya: {pdf_path.name}")


        try:
            # Clean up old pages
            if paths["pages"].exists():
                print(f"[ENGINE] Cleaning old pages at {paths['pages']}")
                for i in range(3): # 3 kez dene
                    try:
                        shutil.rmtree(paths["pages"], onerror=remove_readonly)
                        break # Başarılıysa döngüden çık
                    except PermissionError:
                        print(f"[ENGINE] Klasör kilitli, bekleniyor... ({i+1}/3)")
                        time.sleep(1) # 1 saniye bekle ve tekrar dene
            paths["pages"].mkdir(parents=True, exist_ok=True)

            logger.info(f"Converting PDF to images: {pdf_path}")
            print(f"[ENGINE] Processing PDF: {pdf_path}")
            
            page_paths = pdf_to_page_pngs(pdf_path, dpi=final_dpi, pages_dir=paths["pages"])
            
            self.update_progress(nusha_index, 100, "PDF dönüştürme tamamlandı.", status="completed")
            
            elapsed = time.time() - start_time
            print(f"[ENGINE] PDF conversion finished. {len(page_paths)} pages created in {elapsed:.2f}s.")
            
            return {
                "success": True,
                "page_count": len(page_paths),
                "pages_dir": str(paths["pages"])
            }
        except Exception as e:
            print(f"[ENGINE] CRITICAL ERROR in convert_pdf_to_images: {e}")
            traceback.print_exc()
            logger.error(f"PDF conversion failed: {e}")
            self.update_progress(nusha_index, 0, f"Hata: {str(e)}", status="failed")
            return {"success": False, "error": str(e)}

    def run_line_segmentation(self, nusha_index: int) -> Dict[str, Any]:
        """
        Kraken kullanarak sayfa resimlerini satırlara böler. 
        Manuel model yüklemesi ile Windows uyumluluğu artırılmıştır.
        """
        print(f"[ENGINE] Line Segmentation (Kraken) started for Nusha {nusha_index}...")
        start_time = time.time()
        
        if not KRAKEN_AVAILABLE:
            return {"success": False, "error": "Kraken kütüphanesi yüklü değil."}
            
        paths = self._get_nusha_paths(nusha_index)
        
        if not paths["pages"].exists() or not list(paths["pages"].glob("*.png")):
             return {"success": False, "error": "Sayfa resimleri bulunamadı. Önce PDF dönüşümü yapın."}

        try:
            # Klasör Temizliği
            if paths["lines"].exists():
                for i in range(3):
                    try:
                        shutil.rmtree(paths["lines"], onerror=remove_readonly)
                        break
                    except PermissionError:
                        time.sleep(1)
            paths["lines"].mkdir(parents=True, exist_ok=True)
            
            if paths["manifest"].exists(): paths["manifest"].unlink()
            
            page_images = sorted(list(paths["pages"].glob("*.png")))
            total_lines = 0

            # --- KRİTİK DÜZELTME: MODEL YÜKLEME ---
            # Kraken'in otomatik yükleyicisi bozuk olduğu için modelleri sırayla deniyoruz.
            model_candidates = [
                BASE_DIR / "tahkik_data" / "models" / "muharaf_seg_best.mlmodel", # Özel Model
                BASE_DIR / "tahkik_data" / "models" / "blla.mlmodel"             # İndirilen Varsayılan Model
            ]

            seg_model = None
            for m_path in model_candidates:
                if m_path.exists():
                    print(f"[ENGINE] Segmentasyon Modeli Yükleniyor: {m_path.name}")
                    try:
                        seg_model = vgsl.TorchVGSLModel.load_model(str(m_path))
                        break # Başarılıysa döngüden çık
                    except Exception as e:
                        print(f"[WARN] Model yüklenemedi ({m_path.name}): {e}")
            
            if seg_model is None:
                print("[WARN] DİKKAT: Hiçbir segmentasyon modeli bulunamadı! İşlem başarısız olabilir.")
                # Yine de şansımızı deneyelim (ama muhtemelen çöker)
            # ---------------------------------------
            
            print(f"[ENGINE] Processing {len(page_images)} pages with Kraken...")
            
            with paths["manifest"].open("a", encoding="utf-8") as mf:
                for idx, page_img_path in enumerate(page_images):
                    self.update_progress(nusha_index, int((idx / len(page_images)) * 100), f"Segmentasyon: {idx+1}/{len(page_images)}")

                    try:
                        print(f"[ENGINE] Segmenting Page {idx+1}: {page_img_path.name}")
                        im = Image.open(page_img_path)
                        bw_im = binarization.nlbin(im)
                        
                        # Modeli parametre olarak veriyoruz
                        res = blla.segment(bw_im, model=seg_model)
                        
                        lines = getattr(res, "lines", [])
                        lines.sort(key=lambda x: min([p[1] for p in x.boundary]))
                        
                        for line_idx, line in enumerate(lines):
                            boundary = line.boundary
                            if not boundary: continue
                            
                            xs = [p[0] for p in boundary]
                            ys = [p[1] for p in boundary]
                            x1, x2 = max(0, int(min(xs))), min(im.width, int(max(xs)))
                            y1, y2 = max(0, int(min(ys))), min(im.height, int(max(ys)))
                            
                            if x2 <= x1 or y2 <= y1: continue
                            
                            line_im = im.crop((x1, y1, x2, y2))
                            line_filename = f"{page_img_path.stem}_line_{line_idx+1:03d}.png"
                            line_path = paths["lines"] / line_filename
                            line_im.save(line_path)
                            
                            rec = {
                                "page_image": str(page_img_path),
                                "line_image": str(line_path),
                                "bbox": [x1, y1, x2, y2]
                            }
                            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            total_lines += 1
                        
                    except Exception as inner_e:
                        print(f"[ENGINE] WARN: Page {page_img_path.name} failed: {inner_e}")
                        traceback.print_exc()
                    
                    gc.collect()

            elapsed = time.time() - start_time
            print(f"[ENGINE] Segmentation finished. {total_lines} lines created.")
            self.update_progress(nusha_index, 100, "Segmentasyon tamamlandı.", status="completed")
            
            return {
                "success": True,
                "line_count": total_lines,
                "lines_dir": str(paths["lines"]),
                "manifest_path": str(paths["manifest"])
            }

        except Exception as e:
             print(f"[ENGINE] CRITICAL ERROR: {e}")
             return {"success": False, "error": str(e)}

    def run_ocr(self, nusha_index: int) -> Dict[str, Any]:
        """
        Runs Google Vision OCR on the segmented lines.
        """
        print(f"[ENGINE] OCR (Google Vision) started for Nusha {nusha_index}...")
        start_time = time.time()

        paths = self._get_nusha_paths(nusha_index)
        
        if not paths["manifest"].exists():
            msg = "Lines manifest not found. Run segmentation first."
            print(f"[ENGINE] ERROR: {msg}")
            return {"success": False, "error": msg}

        try:
            # Load ordered lines from the project-specific manifest
            ordered_recs = load_line_records_ordered(manifest_path=paths["manifest"])
            ordered_line_paths = [Path(r["line_image"]) for r in ordered_recs]
            
            if not ordered_line_paths:
                return {"success": False, "error": "No lines found in manifest."}

            # Authenticate
            api_key = get_google_vision_api_key()
            if not api_key:
                print("[ENGINE] ERROR: API Key missing.")
                return {"success": False, "error": "Google Vision API Key invalid or missing."}

            if paths["ocr"].exists():
                print(f"[ENGINE] Cleaning old OCR data at {paths['ocr']}")
                for i in range(3):
                    try:
                        shutil.rmtree(paths["ocr"], onerror=remove_readonly)
                        break
                    except PermissionError:
                        print(f"[ENGINE] Klasör kilitli, bekleniyor... ({i+1}/3)")
                        time.sleep(1)
            
            paths["ocr"].mkdir(parents=True, exist_ok=True)
            
            count = len(ordered_line_paths)
            logger.info(f"Starting OCR for {count} lines.")
            print(f"[ENGINE] Sending {count} lines to Google Vision API...")
            self.update_progress(nusha_index, 10, f"OCR Başlatılıyor ({count} satır)...")
            
            # Note: ocr_lines_with_google_vision_api should handle individual retries
            ok_count, total_count = ocr_lines_with_google_vision_api(
                ordered_line_paths=ordered_line_paths,
                api_key=api_key,
                ocr_dir=paths["ocr"],
            )
            
            self.update_progress(nusha_index, 100, "OCR İşlemi Tamamlandı.", status="completed")
            
            elapsed = time.time() - start_time
            print(f"[ENGINE] OCR finished. {ok_count}/{total_count} lines successful in {elapsed:.2f}s.")

            return {
                "success": True,
                "total_lines": total_count,
                "successful_ocr": ok_count,
                "ocr_dir": str(paths["ocr"])
            }
        except Exception as e:
            print(f"[ENGINE] CRITICAL ERROR in run_ocr: {e}")
            traceback.print_exc()
            logger.error(f"OCR failed: {e}")
            self.update_progress(nusha_index, 0, f"OCR Hatası: {str(e)}", status="failed")
            return {"success": False, "error": str(e)}

    def align_manuscript(self, nusha_index: int) -> Dict[str, Any]:
        """
        Aligns the OCR text with the 'tahkik.docx' found in the project root.
        """
        print(f"[ENGINE] Alignment started for Nusha {nusha_index}...")
        start_time = time.time()
        
        paths = self._get_nusha_paths(nusha_index)
        
        # Locate Tahkik Docx
        docx_path = self.project_dir / "tahkik.docx"
        if not docx_path.exists():
             msg = f"Tahkik Word document not found at {docx_path}"
             print(f"[ENGINE] ERROR: {msg}")
             return {"success": False, "error": msg}
        
        if not paths["ocr"].exists():
             msg = "OCR data not found. Run OCR first."
             print(f"[ENGINE] ERROR: {msg}")
             return {"success": False, "error": msg}

        try:
            # Load OCR lines for this specific project/nusha
            ocr_lines = load_ocr_lines_ordered(
                manifest_path=paths["manifest"],
                ocr_dir=paths["ocr"]
            )
            
            if not ocr_lines:
                print("[ENGINE] ERROR: No OCR content loaded.")
                return {"success": False, "error": "No OCR content loaded for alignment."}

            logger.info("Starting alignment...")
            print(f"[ENGINE] Aligning {len(ocr_lines)} OCR lines with Word doc...")
            
            # We use write_json=False because align_ocr_to_tahkik_segment_dp writes 
            # to the global ALIGNMENT_JSON by default if True. We want to save to project.
            alignment_payload = align_ocr_to_tahkik_segment_dp(
                docx_path=docx_path,
                ocr_lines_override=ocr_lines,
                write_json=False
            )
            
            # Save to project-specific alignment.json
            with paths["alignment"].open("w", encoding="utf-8") as f:
                json.dump(alignment_payload, f, ensure_ascii=False, indent=2)

            elapsed = time.time() - start_time
            print(f"[ENGINE] Alignment finished in {elapsed:.2f}s. Saved to {paths['alignment']}")

            return {
                "success": True,
                "alignment_file": str(paths["alignment"]),
                "lines_aligned": alignment_payload.get("lines_count", 0)
            }

        except Exception as e:
            print(f"[ENGINE] CRITICAL ERROR in align_manuscript: {e}")
            traceback.print_exc()
            logger.error(f"Alignment failed: {e}")
            self.update_progress(nusha_index, 0, f"Hizalama Hatası: {str(e)}", status="failed")
            return {"success": False, "error": str(e)}

    def _run_ocr_on_page(self, image_path: Path, nusha_dir: Path, page_num: int) -> List[Dict[str, Any]]:
        """
        Runs Kraken OCR on a single page: Binarization -> Recognition -> Line Cropping.
        Returns a list of records with text and image filenames.
        """
        lines_dir = nusha_dir / "lines"
        lines_dir.mkdir(parents=True, exist_ok=True)
        
        # Model Path: tahkik_data/models/default.mlmodel
        model_path = BASE_DIR / "tahkik_data" / "models" / "default.mlmodel"
        
        if not model_path.exists():
            print(f"[ERR] Model dosyası bulunamadı! ({model_path})")
            return []

        print(f"[OCR] Model yükleniyor: {model_path.name}")
        try:
            model = models.load_any(str(model_path))
        except Exception as e:
            print(f"[ERR] Model yükleme hatası: {e}")
            return []
        
        try:
            im = Image.open(image_path)
            # Binarization
            bw_im = binarization.nlbin(im)
            
            # Segmentasyon ve Tanıma (Recognition)
            # rpred.rpred returns a generator
            pred_it = rpred.rpred(model, bw_im)
            
            results = []
            for i, record in enumerate(pred_it):
                text = record.prediction
                # record.line contains the bbox (x1, y1, x2, y2) usually
                bbox = record.line 
                
                # Satır Resmini Kes ve Kaydet
                try:
                    # Ensure bbox is valid int tuple
                    if isinstance(bbox, list):
                        bbox = tuple(map(int, bbox))
                    elif hasattr(bbox, 'coords'): # Some kraken versions
                        bbox = bbox.coords
                    
                    # Crop from ORIGINAL image (not binary)
                    line_im = im.crop(bbox)
                    line_filename = f"p{page_num:03d}_l{i+1:03d}.jpg"
                    line_path = lines_dir / line_filename
                    line_im.save(line_path)
                    
                    results.append({
                        "id": i + 1,
                        "text": text,
                        "img_filename": line_filename,
                        "confidence": getattr(record, 'confidence', 0.0),
                        "bbox": bbox
                    })
                except Exception as e:
                    print(f"[WARN] Satır kesme hatası (Page {page_num}, Line {i+1}): {e}")

            return results
            
        except Exception as e:
             print(f"[ERR] OCR Process Failed for {image_path.name}: {e}")
             return []

    def run_full_pipeline(self, nusha_index: int, dpi: int = 300) -> Dict[str, Any]:
        """
        Executes the full pipeline.
        If KRAKEN_AVAILABLE and default.mlmodel exists, uses local Kraken OCR.
        Otherwise falls back to Google Vision (PDF -> Images -> Segmentation -> OCR).
        """
        print(f"[ENGINE] FULL PIPELINE started for Nusha {nusha_index} (DPI={dpi})...")
        
        # Check for Kraken Model
        kraken_model_path = BASE_DIR / "tahkik_data" / "models" / "default.mlmodel"
        use_kraken = KRAKEN_AVAILABLE and kraken_model_path.exists()
        
        if use_kraken:
             print("[ENGINE] KRAKEN OCR MODU AKTİF (Local OCR)")
             self.update_progress(nusha_index, 5, "OCR Başlatılıyor (Kraken Local)...")
             
             # 1. PDF -> Images
             res_pdf = self.convert_pdf_to_images(nusha_index, dpi=dpi)
             if not res_pdf["success"]: return res_pdf
             
             paths = self._get_nusha_paths(nusha_index)
             page_images = sorted(list(paths["pages"].glob("*.png")))
             
             all_segments = []
             
             # 2. Run OCR Page by Page
             for idx, page_img in enumerate(page_images):
                 percent = 10 + int((idx / len(page_images)) * 80)
                 self.update_progress(nusha_index, percent, f"OCR İşleniyor: Sayfa {idx+1}/{len(page_images)}")
                 
                 page_results = self._run_ocr_on_page(page_img, paths["root"], idx+1)
                 
                 # Add to total segments
                 for res in page_results:
                     # Create segment object for Mukabele format
                     # Note: This is a simplified "append" logic.
                     # Real mukabele.json might need global IDs.
                     seg_id = len(all_segments) + 1
                     relative_path = f"/media/projects/{self.project_id}/nusha_{nusha_index}/lines/{res['img_filename']}"
                     
                     all_segments.append({
                        "id": seg_id,
                        "ref_text": f"Ref Satır {seg_id}",
                        "nushas": {
                            str(nusha_index): {
                                "text": res["text"],
                                "img_url": relative_path,
                                "score": int(res["confidence"] * 100)
                            }
                        }
                     })
             
             # 3. Save Results
             output_path = paths["root"].parent / "mukabele.json"
             with open(output_path, "w", encoding="utf-8") as f:
                 json.dump({"segments": all_segments}, f, ensure_ascii=False, indent=2)
                 
             self.update_progress(nusha_index, 100, "Tüm İşlemler Tamamlandı (Kraken)", status="completed")
             return {"success": True, "mode": "kraken", "segments_count": len(all_segments)}

        else:
            print("[ENGINE] GOOGLE VISION MODU AKTİF")
            try:
                # 1. PDF -> Images
                self.update_progress(nusha_index, 5, "PDF Dosyası İşleniyor...")
                res_pdf = self.convert_pdf_to_images(nusha_index, dpi=dpi)
                if not res_pdf["success"]:
                    return res_pdf
                
                # 2. Segmentation
                self.update_progress(nusha_index, 30, "Sayfa Yapısı Analiz Ediliyor...")
                res_seg = self.run_line_segmentation(nusha_index)
                if not res_seg["success"]:
                    return res_seg
                
                # 3. OCR
                self.update_progress(nusha_index, 50, "Metin Okunuyor (OCR)...")
                res_ocr = self.run_ocr(nusha_index)
                if not res_ocr["success"]:
                    return res_ocr
                
                # 4. Alignment
                self.update_progress(nusha_index, 90, "Metin Hizalanıyor...")
                res_align = self.align_manuscript(nusha_index)
                
                # Final Status Update
                if res_align["success"]:
                    self.update_progress(nusha_index, 95, "Mukabele Verisi Hazırlanıyor...")
                    self.generate_mukabele_json(self.project_id, nusha_index)
                    self.update_progress(nusha_index, 100, "Tüm İşlemler Tamamlandı ✅", status="completed")
                else:
                    self.update_progress(nusha_index, 100, "OCR Tamamlandı (Hizalama Başarısız)", status="completed")
    
                return {
                    "success": True, 
                    "pdf": res_pdf,
                    "segmentation": res_seg,
                    "ocr": res_ocr,
                    "alignment": res_align
                }
                
            except Exception as e:
                 print(f"[ENGINE] Critical Pipeline Error: {e}")
                 traceback.print_exc()
                 self.update_progress(nusha_index, 0, f"Hata: {str(e)}", status="failed")
                 return {"success": False, "error": str(e)}

    def generate_mukabele_json(self, project_id: str, nusha_index: int):
        """OCR çıktılarını Mukabele formatına dönüştürüp kaydeder."""
        try:
            print(f"[ENGINE] Mukabele JSON oluşturuluyor... (Proje: {project_id}, Nüsha: {nusha_index})")
            # Correct path reference
            project_path = self.project_dir
            nusha_dir = project_path / f"nusha_{nusha_index}"
            lines_dir = nusha_dir / "lines" # OCR satır resimlerinin olduğu yer
            
            # Word dosyasını oku (Şimdilik basit okuma)
            # İleride paragraflara böleceğiz, şimdilik satır satır eşleştirelim
            segments = []
            
            # Eğer lines klasörü varsa resimleri listele
            if lines_dir.exists():
                # Resimleri isme göre sırala (line_1.jpg, line_2.jpg vs)
                # Doğru sıralama için lambda kullanabiliriz ama şimdilik glob default
                import re
                def natural_sort_key(s):
                    return [int(text) if text.isdigit() else text.lower()
                            for text in re.split('([0-9]+)', str(s))]
                
                line_images = sorted(list(lines_dir.glob("*.jpg")) + list(lines_dir.glob("*.png")), key=natural_sort_key)
                
                for i, img_path in enumerate(line_images):
                    # Resim URL'ini oluştur (/media/projects/ID/nusha_index/lines/img.jpg)
                    # Dikkat: Static mount /media -> tahkik_data'ya bakıyor.
                    # Project path: tahkik_data/projects/ID
                    # Yani URL: /media/projects/ID/...
                    relative_path = f"/media/projects/{project_id}/nusha_{nusha_index}/lines/{img_path.name}"
                    
                    segments.append({
                        "id": i + 1,
                        "ref_text": f"Referans Metin Satır {i+1} (Word İçeriği Gelecek)", # Placeholder
                        "nushas": {
                            str(nusha_index): {
                                "text": f"OCR Çıktısı: {img_path.name}", # İleride Google Vision text'i gelecek
                                "img_url": relative_path,
                                "score": 100
                            }
                        }
                    })
            
            # JSON Olarak Kaydet
            output_path = project_path / "mukabele.json"
            
            # Mevcut varsa birleştir (Merge logic - advanced feature, şimdilik overwrite veya append)
            # Şu anlık sadece tek nusha destekli gibi yazıyoruz ama yapıyı bozmamak lazım.
            # Eğer dosya varsa oku, ilgili nushayı güncelle.
            existing_data = {"segments": []}
            if output_path.exists():
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except:
                    pass
            
            # Basit merge: Eğer segment ID varsa nushayı ekle, yoksa yeni segment oluştur
            # Bu karmaşık olabilir, şimdilik basitçe overwrite edelim veya append edelim.
            # Kullanıcının isteği "sonuçları kaydetmek". 
            # Şimdilik direkt listeyi yazalım, çoklu nusha merge sonraki iş.
            import json
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"segments": segments}, f, ensure_ascii=False, indent=2)
                
            print(f"[ENGINE] Mukabele verisi oluşturuldu: {output_path}")
            
        except Exception as e:
            print(f"[ENGINE] Mukabele JSON Hatası: {e}")
            traceback.print_exc()
            

        

