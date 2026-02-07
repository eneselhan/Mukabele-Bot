@echo off
if not exist "venv_311" (
    echo Python 3.11 Sanal Ortami bulunamadi. Olusturuluyor...
    py -3.11 -m venv venv_311
)

echo Bagimliliklar kontrol ediliyor (Timeout artirildi)...
venv_311\Scripts\pip install --default-timeout=1000 -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Bagimlilik kurulumunda hata olustu.
    pause
    exit /b %ERRORLEVEL%
)

echo Bot baslatiliyor...
venv_311\Scripts\python main.py
pause
