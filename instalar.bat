@echo off
title Instalacion - Herramienta Integral de Tesoreria
cd /d "%~dp0"
echo ============================================================
echo   Instalacion de requisitos (solo la primera vez)
echo   Instala Python, Git y Tesseract si no estan.
echo   Puede pedir permisos de administrador.
echo ============================================================
echo.
where winget >nul 2>nul
if errorlevel 1 (
  echo *** No se encontro 'winget' ^(Instalador de aplicaciones de Windows^). ***
  echo Actualiza Windows o instala "App Installer" desde Microsoft Store
  echo y vuelve a ejecutar instalar.bat.
  echo.
  pause
  exit /b 1
)
echo [1/3] Python...
set "PYOK="
where py.exe >nul 2>nul && py -c "" >nul 2>nul && set "PYOK=1"
if not defined PYOK where python.exe >nul 2>nul && python -c "" >nul 2>nul && set "PYOK=1"
if defined PYOK (echo   * Python ya esta instalado.) else (echo   Instalando Python 3.12... & winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements)
echo.
echo [2/3] Git...
where git >nul 2>nul
if errorlevel 1 (winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements) else (echo   * Git ya esta instalado.)
echo.
echo [3/3] Tesseract (OCR)...
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (echo   * Tesseract ya esta instalado.) else (winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements)
echo.
echo ============================================================
echo   Verificacion final:
set "PYOK="
where py.exe >nul 2>nul && py -c "" >nul 2>nul && set "PYOK=1"
if not defined PYOK where python.exe >nul 2>nul && python -c "" >nul 2>nul && set "PYOK=1"
if defined PYOK (echo   [OK]    Python) else (echo   [FALTA] Python - cierra y reabre esta ventana; si sigue, desactiva el alias de Microsoft Store)
where git >nul 2>nul && (echo   [OK]    Git) || (echo   [FALTA] Git)
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (echo   [OK]    Tesseract) else (echo   [FALTA] Tesseract)
echo ============================================================
echo   Si todo dice [OK], CIERRA esta ventana y abre la app con iniciar.bat
echo   Si acabas de instalar Python y dice [FALTA], solo cierra y vuelve a abrir.
echo ============================================================
pause
