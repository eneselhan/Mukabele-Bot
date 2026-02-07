import shutil
import sys
import os
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
    print(f"{BOLD}\n=== ProjectManager Test Başlatılıyor ===\n{RESET}")
    pm = None
    project_id = None
    
    try:
        # 1. ProjectManager Init
        print_status("ProjectManager başlatılıyor...", "INFO")
        try:
            pm = ProjectManager()
            print_status("ProjectManager sınıfı başarıyla başlatıldı.", "SUCCESS")
        except Exception as e:
            print_status(f"ProjectManager başlatılamadı: {e}", "ERROR")
            return

        # 2. Create Project
        print_status("Yeni proje oluşturuluyor ('Test Projesi')...", "INFO")
        try:
            project_id = pm.create_project("Test Projesi")
            project_path = pm.get_project_path(project_id)
            
            if project_path.exists() and project_path.is_dir():
                print_status(f"Proje klasörü oluşturuldu: {project_path}", "SUCCESS")
            else:
                print_status("Proje klasörü bulunamadı!", "ERROR")
                return

            metadata_path = project_path / "metadata.json"
            if metadata_path.exists():
                print_status("metadata.json dosyası mevcut.", "SUCCESS")
            else:
                print_status("metadata.json dosyası OLUŞMADI!", "ERROR")
                return

        except Exception as e:
            print_status(f"Proje oluşturma hatası: {e}", "ERROR")
            return

        # 3. Create Nusha Dir
        print_status(f"Nüsha klasörü oluşturuluyor (ID: {project_id}, Index: 1)...", "INFO")
        try:
            nusha_path = pm.get_nusha_dir(project_id, 1)
            if nusha_path.exists() and nusha_path.name == "nusha_1":
                 print_status(f"Nüsha klasörü başarıyla oluşturuldu: {nusha_path}", "SUCCESS")
            else:
                 print_status("Nüsha klasörü oluşturulamadı veya ismi yanlış.", "ERROR")
        except Exception as e:
            print_status(f"Nüsha klasörü oluşturma hatası: {e}", "ERROR")

        # 4. List Projects
        print_status("Projeler listeleniyor...", "INFO")
        try:
            projects = pm.list_projects()
            found = False
            for p in projects:
                if p.get('id') == project_id and p.get('name') == "Test Projesi":
                    found = True
                    break
            
            if found:
                print_status(f"Listede oluşturulan proje bulundu. (Toplam {len(projects)} proje)", "SUCCESS")
            else:
                print_status("Oluşturulan proje listede bulunamadı!", "ERROR")
        except Exception as e:
             print_status(f"Proje listeleme hatası: {e}", "ERROR")

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
    # Windows terminal color support fix if needed (often works in VSCode without this, but safe to add)
    os.system('') 
    run_tests()
