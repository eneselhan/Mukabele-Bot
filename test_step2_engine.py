import shutil
import sys
import os
from src.services.manuscript_engine import ManuscriptEngine
from src.services.project_manager import ProjectManager

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[94m"

def print_status(message, status="INFO"):
    if status == "SUCCESS":
        print(f"{GREEN}✅ BAŞARILI: {message}{RESET}")
    elif status == "ERROR":
        print(f"{RED}❌ HATA: {message}{RESET}")
    elif status == "INFO":
        print(f"{BLUE}ℹ️  {message}{RESET}")
    else:
        print(message)

def run_tests():
    print(f"{BOLD}\n=== ManuscriptEngine Yapısal Test Başlatılıyor ===\n{RESET}")
    pm = None
    engine = None
    project_id = None
    
    try:
        # 1. Create Project
        print_status("Geçici proje oluşturuluyor ('Engine_Test_Project')...", "INFO")
        try:
            pm = ProjectManager()
            project_id = pm.create_project("Engine_Test_Project")
            
            if project_id:
                print_status(f"Proje ID alındı: {project_id}", "SUCCESS")
            else:
                print_status("Proje ID alınamadı!", "ERROR")
                return
        except Exception as e:
            print_status(f"Proje oluşturma hatası: {e}", "ERROR")
            return

        # 2. Init Engine
        print_status("ManuscriptEngine başlatılıyor...", "INFO")
        try:
            engine = ManuscriptEngine(project_id)
            print_status("ManuscriptEngine sınıfı başlatıldı.", "SUCCESS")
        except Exception as e:
            print_status(f"Engine başlatılamadı: {e}", "ERROR")
            return

        # 3. Path Verification
        print_status("Klasör yolları doğrulanıyor...", "INFO")
        try:
            manager_path = pm.get_project_path(project_id)
            engine_path = engine.project_dir
            
            if manager_path == engine_path and engine_path.exists():
                print_status(f"Yol eşleşmesi DOĞRU: {engine_path}", "SUCCESS")
            else:
                print_status(f"Yol eşleşmesi HATALI!\nManager: {manager_path}\nEngine:  {engine_path}", "ERROR")
        except Exception as e:
            print_status(f"Yol doğrulama hatası: {e}", "ERROR")

        # 4. Method Verification (hasattr)
        print_status("Kritik metodlar kontrol ediliyor...", "INFO")
        required_methods = [
            "convert_pdf_to_images",
            "run_line_segmentation",
            "run_ocr",
            "align_manuscript"
        ]
        
        all_methods_ok = True
        for method in required_methods:
            if hasattr(engine, method) and callable(getattr(engine, method)):
                print_status(f"Metod mevcut: {method}", "SUCCESS")
            else:
                print_status(f"Metod EKSİK: {method}", "ERROR")
                all_methods_ok = False
        
        if all_methods_ok:
            print_status("Tüm kritik metodlar tanımlı.", "SUCCESS")
        else:
            print_status("Bazı metodlar eksik!", "ERROR")

    except Exception as e:
        print_status(f"Beklenmeyen genel hata: {e}", "ERROR")
    
    finally:
        # 5. Cleanup
        if project_id and pm:
            print_status("Temizlik yapılıyor (Test projesi siliniyor)...", "INFO")
            try:
                project_path = pm.get_project_path(project_id)
                if project_path.exists():
                    shutil.rmtree(project_path)
                    if not project_path.exists():
                        print_status("Test projesi başarıyla silindi.", "SUCCESS")
                    else:
                        print_status("Test projesi silinemedi!", "ERROR")
                else:
                    print_status("Silinecek proje yolu zaten yok.", "INFO")
            except Exception as e:
                print_status(f"Temizlik sırasında hata: {e}", "ERROR")

    print(f"{BOLD}\n=== Test Tamamlandı ===\n{RESET}")

if __name__ == "__main__":
    os.system('') # Color fix
    run_tests()
