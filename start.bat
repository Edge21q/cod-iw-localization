@echo off
:: Yonetici olarak calisiyor mu kontrol et
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici olarak baslatiliyor
    powershell -Command "Start-Process '%~f0' -Verb runAs"
    exit /b
)

:: Script bulunduğu klasöre geç
cd /d "%~dp0"

:: Python betiğini çalıştır
python "cod-iw-localization.py"

pause
