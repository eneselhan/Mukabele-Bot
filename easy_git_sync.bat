@echo off
setlocal EnableDelayedExpansion

echo ========================================================
echo   Antigravity Github Sync Tool (v2.0)
echo ========================================================

:: 1. Git Yuklu mu?
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Git bulunamadi. Lutfen Git'i yukleyin ve bilgisayari yeniden baslatin.
    echo İndirme Linki: https://git-scm.com/downloads
    pause
    exit /b
)

:: 2. Repo Baslatma / Kontrol
if not exist ".git" (
    echo [BILGI] Git reposu baslatiliyor...
    git init
    git branch -M main
) else (
    echo [BILGI] Mevcut Git reposu algilandi.
)

:: 3. Remote URL Kontrolu
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [UYARI] Henuz bir GitHub deposuna baglanmamis.
    echo Lutfen GitHub'da bos bir repo acin ve linkini yapistirin.
    echo (Ornek: https://github.com/kullaniciadi/proje.git)
    echo.
    set /p REMOTE_URL="Repo URL'si: "

    if "!REMOTE_URL!"=="" (
        echo [HATA] URL bos birakildi. İptal ediliyor.
        pause
        exit /b
    )
    
    git remote add origin !REMOTE_URL!
    echo [BASARILI] Uzak sunucu eklendi.
) else (
    echo [BILGI] Remote URL zaten bagli.
)

:: 4. .gitignore Kontrolu (Yoksa Olustur)
if not exist ".gitignore" (
    echo [BILGI] .gitignore dosyasi olusturuluyor...
    (
        echo # Python
        echo venv/
        echo venv_311/
        echo __pycache__/
        echo *.pyc
        echo .env
        echo .DS_Store
        echo # Node
        echo node_modules/
        echo .next/
        echo out/
        echo build/
        echo .vscode/
        echo *.log
        echo tahkik_data/
    ) > .gitignore
)

:: 5. Commit ve Push
echo.
echo [ISLEM] Degisiklikler algilaniyor...
git add .
git commit -m "Otomatik Yedekleme: %date% %time%"

echo.
echo [ISLEM] GitHub'a gonderiliyor (Push)...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [HATA] Gonderme basarisiz oldu!
    echo Olası Sebepler:
    echo 1. İnternet baglantisi yok.
    echo 2. Repo bos degil (Once 'git pull' gerekebilir).
    echo 3. Yetki hatasi (GitHub'a giris yapmamis olabilirsiniz).
) else (
    echo.
    echo [BASARILI] Kodlar guvenle GitHub'a yuklendi.
)

echo.
pause