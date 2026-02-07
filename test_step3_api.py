from fastapi.testclient import TestClient
from src.api_server import app
import shutil
import os

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

client = TestClient(app)

def run_api_tests():
    print(f"{BOLD}\n=== API Server Test Başlatılıyor ===\n{RESET}")
    project_id = None
    
    try:
        # 1. List Projects (Empty)
        print_status("Proje listesi çekiliyor...", "INFO")
        response = client.get("/api/projects")
        if response.status_code == 200:
             print_status("GET /api/projects başarılı.", "SUCCESS")
        else:
             print_status(f"GET /api/projects başarısız: {response.text}", "ERROR")
             return

        # 2. Create Project
        print_status("Yeni proje oluşturuluyor...", "INFO")
        response = client.post("/api/projects", json={"name": "API Test Projesi"})
        if response.status_code == 200:
             data = response.json()
             project_id = data.get("id")
             print_status(f"POST /api/projects başarılı. ID: {project_id}", "SUCCESS")
        else:
             print_status(f"POST /api/projects başarısız: {response.text}", "ERROR")
             return

        # 3. Get Project Detail
        print_status("Proje detayları alınıyor...", "INFO")
        response = client.get(f"/api/projects/{project_id}")
        if response.status_code == 200 and response.json().get("name") == "API Test Projesi":
             print_status("GET /api/projects/{id} başarılı.", "SUCCESS")
        else:
             print_status(f"GET /api/projects/{id} başarısız: {response.text}", "ERROR")

        # 4. Upload File
        print_status("Dosya yükleniyor (Dummy PDF)...", "INFO")
        # Create dummy pdf
        dummy_pdf = "dummy_source.pdf"
        with open(dummy_pdf, "wb") as f: f.write(b"%PDF-1.4 dummy content")
        
        with open(dummy_pdf, "rb") as f:
            response = client.post(
                f"/api/projects/{project_id}/upload", 
                files={"file": ("source.pdf", f, "application/pdf")},
                data={"nusha_index": 1, "file_type": "pdf"}
            )
        
        os.remove(dummy_pdf)
        
        if response.status_code == 200:
             print_status("POST /api/projects/{id}/upload başarılı.", "SUCCESS")
        else:
             print_status(f"POST /api/projects/{id}/upload başarısız: {response.text}", "ERROR")

        # 5. Process (Trigger Background Task)
        # We can't easily wait for background tasks in TestClient without mocking, 
        # but we can check if the endpoint returns success.
        print_status("İşlem başlatılıyor...", "INFO")
        response = client.post(
            f"/api/projects/{project_id}/process",
            json={"step": "images", "nusha_index": 1}
        )
        if response.status_code == 200:
             print_status("POST /api/projects/{id}/process başarılı.", "SUCCESS")
        else:
             print_status(f"POST /api/projects/{id}/process başarısız: {response.text}", "ERROR")

        # 6. Status Check
        print_status("Durum kontrol ediliyor...", "INFO")
        response = client.get(f"/api/projects/{project_id}/status")
        if response.status_code == 200:
             status = response.json()
             print_status(f"GET /api/projects/{id}/status başarılı. Durum: {status}", "SUCCESS")
        else:
             print_status(f"GET /api/projects/{id}/status başarısız: {response.text}", "ERROR")

    except Exception as e:
        print_status(f"Beklenmeyen hata: {e}", "ERROR")

    finally:
        # Cleanup
        if project_id:
            print_status("Test projesi temizleniyor...", "INFO")
            from src.services.project_manager import ProjectManager
            pm = ProjectManager()
            path = pm.get_project_path(project_id)
            if path.exists():
                shutil.rmtree(path)
                print_status("Temizlik tamamlandı.", "SUCCESS")

    print(f"{BOLD}\n=== Test Tamamlandı ===\n{RESET}")

if __name__ == "__main__":
    os.system('')
    run_api_tests()
