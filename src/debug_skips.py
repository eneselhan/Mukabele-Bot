# -*- coding: utf-8 -*-
"""
Enhanced Comparison Report (Matrix View)
Generates an HTML matrix comparing 'Dizgi' (Main Text) vs All Nusha OCRs.
"""
import sys
import json
import webbrowser
from pathlib import Path
from rapidfuzz.distance import Levenshtein

# Allow importing from src
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import ALIGNMENT_JSON, OUT
from src.utils import normalize_ar

def get_missing_words(ref_text, cand_text):
    """
    Returns list of words in REF that are NOT in CAND.
    """
    if not ref_text: return []
    if not cand_text: return ref_text.split()
    
    ref_toks = [t for t in ref_text.split()]
    cand_toks = [t for t in cand_text.split()]
    
    ref_norm = [normalize_ar(t) for t in ref_toks]
    cand_norm = [normalize_ar(t) for t in cand_toks]
    
    matcher = Levenshtein.opcodes(ref_norm, cand_norm)
    
    missing = []
    for tag, i1, i2, j1, j2 in matcher:
        if tag in ("replace", "delete"):
            for k in range(i1, i2):
                missing.append(ref_toks[k])
    return missing

def visualize_anchors(ref_text, cand_text):
    """
    Visualizes alignment anchors.
    Blue (Anchor) = Exact match used for alignment.
    Red = Missing in candidate.
    """
    if not ref_text: return ""
    if not cand_text: return f'<span class="miss">{ref_text}</span>'
    
    ref_toks = [t for t in ref_text.split()]
    cand_toks = [t for t in cand_text.split()]
    
    ref_norm = [normalize_ar(t) for t in ref_toks]
    cand_norm = [normalize_ar(t) for t in cand_toks]
    
    matcher = Levenshtein.opcodes(ref_norm, cand_norm)
    
    parts = []
    
    for tag, i1, i2, j1, j2 in matcher:
        if tag == "equal":
            # ANCHOR: These words matched exactly and "hooked" the alignment
            for k in range(i1, i2):
                parts.append(f'<span class="anchor">{ref_toks[k]}</span>')
        elif tag in ("replace", "delete"):
            # These are the gaps between anchors
            for k in range(i1, i2):
                parts.append(f'<span class="miss">{ref_toks[k]}</span>')
            
    return " ".join(parts)

def generate_full_matrix(data, target_out):
    # --- LOAD MANIFEST IF AVAILABLE ---
    manifest_map = {}
    manifest_path = target_out / "lines_manifest.jsonl"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        obj = json.loads(line)
                        p_name = obj.get("page_name")
                        l_idx = obj.get("line_index")
                        l_img = obj.get("line_image", "")
                        if p_name and l_idx is not None and l_img:
                            fname = Path(l_img).name
                            manifest_map[(p_name, l_idx)] = fname
                    except:
                        pass
            print(f"Manifest loaded: {len(manifest_map)} entries.")
        except Exception as e:
            print(f"Error loading manifest: {e}")

    aligned = data.get("aligned") or []
    if not aligned:
        return "<h3>Hata: 'aligned' verisi bulunamadı.</h3>"
        
    headers = ["No", "Dizgi (Hizalama ve Kancalar)", "Nüsha 1 (OCR)", "Eksik Kelimeler"]
    
    rows_html = []
    
    missing_images_count = 0
    
    for i, item in enumerate(aligned):
        line_no = item.get("line_no", i + 1)
        
        best_cand = item.get("best") or {}
        dizgi_text = best_cand.get("raw", "").strip()
        # N1 Text & Image
        n1_text = item.get("ocr_text", "").strip()
        
        # --- IMAGE PATH RESOLUTION LOGIC ---
        final_path = None
        
        # Strategy 1: Check Manifest Map (Most Reliable for Archives)
        page_name = item.get("page_name")
        line_idx = item.get("line_index")
        
        if page_name and line_idx is not None:
            # Try tuple lookup
            manifest_fname = manifest_map.get((page_name, line_idx))
            if manifest_fname:
                # Check target_out/lines/filename
                check_man = target_out / "lines" / manifest_fname
                if check_man.exists():
                    final_path = check_man
        
        # Strategy 2: Fallback to alignment.json path
        if not final_path:
            raw_path = item.get("line_image", "")
            if raw_path:
                p_obj = Path(raw_path)
                
                # 2a. Check if absolute path works (for local logic)
                if p_obj.exists():
                    final_path = p_obj
                
                # 2b. Check local lines folder by filename
                if not final_path:
                    fname = p_obj.name
                    check_local = target_out / "lines" / fname
                    if check_local.exists():
                        final_path = check_local
                    
                # 2c. Check global lines folder (fallback)
                if not final_path:
                    fname = p_obj.name
                    check_global = OUT / "lines" / fname
                    if check_global.exists():
                        final_path = check_global

        # Generate HTML
        if final_path:
            img_html = f'<div class="line-img"><img src="{final_path.as_uri()}" alt="Line Image" /></div>'
        else:
            missing_images_count += 1
            # Show a small placeholder if missing
            fname_display = Path(item.get("line_image", "")).name
            img_html = f'<div class="line-img" style="color:red; font-size:0.7em;">[Missing: {fname_display}]</div>'
        
        # Visualize Anchors on Dizgi Column
        # This shows both the text AND the alignment logic (Blue=Hook, Red=Gap)
        dizgi_html = visualize_anchors(dizgi_text, n1_text)
        
        missing = get_missing_words(dizgi_text, n1_text)
        missing_html = " ".join(f'<span class="miss-tag">{w}</span>' for w in missing) if missing else '<span class="ok">Tam Eşleşme</span>'
        
        cols = []
        # 1. No
        cols.append(f'<td class="min">{line_no}</td>')
        
        # 2. Dizgi
        cols.append(f'<td class="ar ref">{dizgi_html}</td>')
        
        # 3. N1
        cols.append(f'<td class="ar">{img_html}{n1_text}</td>')
        
        # 4. Missing
        cols.append(f'<td class="ar">{missing_html}</td>')
            
        rows_html.append(f'<tr>{"".join(cols)}</tr>')
        
    thead = "".join(f'<th>{h}</th>' for h in headers)
    
    return f"""
    <table class="matrix">
        <thead>
            <tr>{thead}</tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    """

def main():
    print("Alignment verileri taranıyor...")
    
    # 1. Mevcut (En güncel)
    candidates = []
    if ALIGNMENT_JSON.exists():
        candidates.append({
            "name": "Most Recent (Mevcut 'output_lines')",
            "path": ALIGNMENT_JSON,
            "out_dir": OUT
        })
        
    # 2. Arşivler
    archives_dir = OUT / "doc_archives"
    if archives_dir.exists():
        # Sort by Name (Date reversed)
        subdirs = sorted([d for d in archives_dir.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
        for d in subdirs:
            aj = d / "alignment.json"
            if aj.exists():
                candidates.append({
                    "name": f"Archive: {d.name}",
                    "path": aj,
                    "out_dir": d
                })
    
    if not candidates:
        print("HATA: Hiçbir 'alignment.json' bulunamadı.")
        return

    print(f"\nBulunan Veri Setleri ({len(candidates)}):")
    for idx, c in enumerate(candidates):
        print(f"[{idx+1}] {c['name']}")
        
    choice = input("\nLütfen bir numara seçin (Enter=1): ").strip()
    if not choice:
        sel_idx = 0
    else:
        try:
            sel_idx = int(choice) - 1
        except:
            sel_idx = 0
            
    if sel_idx < 0 or sel_idx >= len(candidates):
        print("Geçersiz seçim, varsayılan (1) kullanılıyor.")
        sel_idx = 0
        
    selected = candidates[sel_idx]
    target_json = selected["path"]
    target_out = selected["out_dir"] # HTML this dir'in içine kaydedilecek
    
    print(f"\nSeçilen: {selected['name']}")
    print(f"Yükleniyor: {target_json}")
    
    try:
        data = json.loads(target_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"HATA: JSON okunamadı -> {e}")
        return

    table_html = generate_full_matrix(data, target_out)
    
    report_html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Karşılaştırmalı Döküm (Matrix)</title>
        <style>
            body {{ font-family: sans-serif; background: #f8f9fa; padding: 20px; }}
            h1 {{ margin-bottom: 20px; }}
            .matrix {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); table-layout: fixed; }}
            .matrix th, .matrix td {{ border: 1px solid #dee2e6; padding: 12px 8px; vertical-align: top; }}
            .matrix th {{ background: #e9ecef; text-align: left; font-weight: 600; font-size: 0.9em; text-transform: uppercase; color: #495057; }}
            
            .ar {{ direction: rtl; font-family: "Traditional Arabic", "Scheherazade New", serif; font-size: 1.25em; line-height: 1.6; color: #212529; }}
            .ref {{ background-color: #f8f9fa; color: #333; }}
            .min {{ width: 50px; text-align: center; color: #868e96; font-size: 0.85em; font-family: monospace; }}
            
            .miss-tag {{ color: #dc3545; background-color: rgba(220, 53, 69, 0.1); padding: 2px 6px; border-radius: 4px; margin: 0 2px; display: inline-block; }}
            .ok {{ color: #28a745; font-style: italic; font-size: 0.8em; }}
            .anchor {{ color: #0d6efd; font-weight: bold; }}
            .miss {{ color: #dc3545; text-decoration: line-through; opacity: 0.6; }}
            .line-img img {{ max-width: 100%; height: auto; max-height: 80px; display: block; margin-bottom: 5px; border: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <h1>Karşılaştırmalı Döküm (Dizgi vs Nüsha 1)</h1>
        <p>
            <b>Tablo:</b> Sol sütun Dizgi, orta sütun Nüsha 1, sağ sütun Dizgi'de olup Nüsha'da bulunamayan kelimeler.
            <br>
            <small>Kaynak Veri: {selected['name']}</small>
        </p>
        
        {table_html}
    </body>
    </html>
    """
    
    # Save HTML to the SAME directory as the JSON to preserve relative image paths
    out_path = target_out / "debug_comparison.html"
    out_path.write_text(report_html, encoding="utf-8")
    print(f"Rapor oluşturuldu: {out_path}")
    webbrowser.open(out_path.as_uri())

if __name__ == "__main__":
    main()
