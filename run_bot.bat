@echo off
echo Sistemdeki Python versiyonu kullaniliyor...
python --version

:: Eger 'venv' klasoru yoksa olustur
if not exist "venv" (
    echo Sanal Ortam (venv) bulunamadi. Mevcut Python ile olusturuluyor...
    python -m venv venv
)

echo Bagimliliklar yukleniyor/guncelleniyor...
:: Once pip'i guncelle
venv\Scripts\python -m pip install --upgrade pip
:: Sonra requirements.txt'yi yukle
venv\Scripts\pip install --default-timeout=1000 -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo !HATA! Bagimliliklar yuklenirken sorun olustu.
    echo Lutfen requirements.txt dosyasini kontrol edin (Kraken silindi mi?).
    pause
    exit /b %ERRORLEVEL%
)

echo ---------------------------------------
echo Bot Baslatiliyor...
echo ---------------------------------------
venv\Scripts\python main.py
pause