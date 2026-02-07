@echo off
setlocal EnableDelayedExpansion

echo ========================================================
echo   Antigravity Github Sync Tool
echo ========================================================

:: 1. Giris Kontrolu
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Git yuklu degil veya PATH'e ekli degil. Lutfen Git'i yukleyin.
    pause
    exit /b
)

:: 2. Repo Kontrolu ve Baslatma
if not exist ".git" (
    echo [BILGI] Bu klasorde Git reposu bulunamadi. Yeni repo olusturuluyor...
    git init
    git branch -M main
) else (
    echo [BILGI] Git reposu mevcut.
)

:: 3. Remote Kontrolu
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo [UYARI] Uzak sunucu (Remote URL) tanimli degil.
    echo Lutfen GitHub'da yeni bir bos repo olusturun ve linki asagiya yapistirin.
    echo Ornek: https://github.com/kullaniciadi/proje-adi.git
    set /p REMOTE_URL="Repo URL'si: "
    
    if "!REMOTE_URL!"=="" (
        echo [HATA] URL girilmedi. İptal ediliyor.
        pause
        exit /b
    )
    
    git remote add origin !REMOTE_URL!
    echo [BASARILI] Remote eklendi.
) else (
    echo [BILGI] Remote URL zaten tanimli.
)

:: 4. .gitignore Kontrolu
if not exist ".gitignore" (
    echo [BILGI] .gitignore dosyasi olusturuluyor (Standart Node/Python/General)...
    (
        echo node_modules/
        echo .next/
        echo dist/
        echo build/
        echo .env
        echo .env.local
        echo .DS_Store
        echo venv/
        echo __pycache__/
        echo *.log
        echo .vscode/
        echo .idea/
    ) > .gitignore
)

:: 5. Ekleme ve Commit
echo.
echo [ISLEM] Dosyalar ekleniyor ve commitleniyor...
git add .
set TIMESTAMP=%date% %time%
git commit -m "Otomatik yedekleme: %TIMESTAMP%"

:: 6. Push Islemi
echo.
echo [ISLEM] GitHub'a yukleniyor...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [HATA] Yukleme sirasinda bir sorun olustu. 
    echo - Remote URL'nin dogru oldugundan emin olun.
    echo - Force push gerekebilir (dikkatli olun).
    echo - İnternet baglantinizi kontrol edin.
) else (
    echo.
    echo [BASARILI] Kodlariniz GitHub'a yuklendi!
)

echo.
pause
