import json
import shutil
import logging
import traceback
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.services.project_manager import ProjectManager
from src.pdf_processor import pdf_to_page_pngs
from src.kraken_processor import split_page_to_lines, load_line_records_ordered
from src.ocr import ocr_lines_with_google_vision_api, load_ocr_lines_ordered
from src.alignment import align_ocr_to_tahkik_segment_dp
from src.keys import get_google_vision_api_key

# Configure logging
logger = logging.getLogger(__name__)

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
        
        # Locate PDF: Checks nusha folder first, then project root.
        pdf_path = paths["root"] / "source.pdf"
        if not pdf_path.exists():
            # Fallback to project root if nusha specific pdf not found
            pdf_path = self.project_dir / "source.pdf"
            
        if not pdf_path.exists():
            msg = f"PDF source not found. Expected at {paths['root'] / 'source.pdf'} or {self.project_dir / 'source.pdf'}"
            print(f"[ENGINE] ERROR: {msg}")
            return {"success": False, "error": msg}

        try:
            # Clean up old pages
            if paths["pages"].exists():
                print(f"[ENGINE] Cleaning old pages at {paths['pages']}")
                shutil.rmtree(paths["pages"])
            paths["pages"].mkdir(parents=True, exist_ok=True)

            logger.info(f"Converting PDF to images: {pdf_path}")
            print(f"[ENGINE] Processing PDF: {pdf_path}")
            
            page_paths = pdf_to_page_pngs(pdf_path, dpi=final_dpi, pages_dir=paths["pages"])
            
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
            return {"success": False, "error": str(e)}

    def run_line_segmentation(self, nusha_index: int) -> Dict[str, Any]:
        """
        Segments page images into line images using Kraken/BLLA.
        """
        print(f"[ENGINE] Line Segmentation (Kraken) started for Nusha {nusha_index}...")
        start_time = time.time()
        
        paths = self._get_nusha_paths(nusha_index)
        
        if not paths["pages"].exists() or not list(paths["pages"].glob("*.png")):
             msg = "No page images found. Run PDF conversion first."
             print(f"[ENGINE] ERROR: {msg}")
             return {"success": False, "error": msg}

        try:
            # Clean up old lines
            if paths["lines"].exists():
                print(f"[ENGINE] Cleaning old lines at {paths['lines']}")
                shutil.rmtree(paths["lines"])
            paths["lines"].mkdir(parents=True, exist_ok=True)
            
            # Reset Manifest
            if paths["manifest"].exists():
                paths["manifest"].unlink()
            
            page_images = sorted(list(paths["pages"].glob("*.png")))
            total_lines = 0
            
            print(f"[ENGINE] Configuring manifest at {paths['manifest']}")
            
            with paths["manifest"].open("a", encoding="utf-8") as mf:
                for idx, page_img in enumerate(page_images):
                    print(f"[ENGINE] Segmenting Page {idx+1}/{len(page_images)}: {page_img.name}")
                    try:
                        records = split_page_to_lines(page_img, lines_dir=paths["lines"])
                        print(f"    -> Found {len(records)} lines.")
                        for rec in records:
                            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        total_lines += len(records)
                    except Exception as inner_e:
                        print(f"[ENGINE] WARN: Failed to segment page {page_img.name}: {inner_e}")
                        traceback.print_exc()
                        # Continue to next page? Yes, robustness.
            
            elapsed = time.time() - start_time
            print(f"[ENGINE] Segmentation finished. {total_lines} total lines in {elapsed:.2f}s.")
            
            return {
                "success": True,
                "line_count": total_lines,
                "lines_dir": str(paths["lines"]),
                "manifest_path": str(paths["manifest"])
            }
        except Exception as e:
             print(f"[ENGINE] CRITICAL ERROR in run_line_segmentation: {e}")
             traceback.print_exc()
             logger.error(f"Line segmentation failed: {e}")
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

            paths["ocr"].mkdir(parents=True, exist_ok=True)
            
            count = len(ordered_line_paths)
            logger.info(f"Starting OCR for {count} lines.")
            print(f"[ENGINE] Sending {count} lines to Google Vision API...")
            
            # Note: ocr_lines_with_google_vision_api should handle individual retries
            ok_count, total_count = ocr_lines_with_google_vision_api(
                ordered_line_paths=ordered_line_paths,
                api_key=api_key,
                ocr_dir=paths["ocr"],
            )
            
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
            return {"success": False, "error": str(e)}

    def run_full_pipeline(self, nusha_index: int) -> Dict[str, Any]:
        """
        Executes the full pipeline in order:
        1. PDF -> Images
        2. Line Segmentation (Kraken)
        3. OCR (Google Vision)
        """
        print(f"[ENGINE] Starting FULL PIPELINE for Nusha {nusha_index}...")
        
        # 1. PDF -> Images
        res_pdf = self.convert_pdf_to_images(nusha_index)
        if not res_pdf["success"]:
            return res_pdf
            
        # 2. Segmentation
        res_seg = self.run_line_segmentation(nusha_index)
        if not res_seg["success"]:
            return res_seg
            
        # 3. OCR
        res_ocr = self.run_ocr(nusha_index)
        
        if res_ocr["success"]:
            print(f"[ENGINE] FULL PIPELINE COMPLETED SUCCESSFULLY for Nusha {nusha_index}")
        else:
            print(f"[ENGINE] FULL PIPELINE FAILED at OCR step")
            
        return res_ocr
