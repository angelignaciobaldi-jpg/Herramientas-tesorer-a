@echo off
title Instalacion - Herramienta Integral de Tesoreria
cd /d "%~dp0"
echo ============================================================
echo   Instalacion de requisitos (solo la primera vez)
echo   Instala Python, Git y Tesseract si no estan.
echo   Puede pedir permisos de administrador.
echo ============================================================
echo.
echo [1/3] Python...
where python >nul 2>nul
if errorlevel 1 (winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements) else (echo   * Python ya esta instalado.)
echo.
echo [2/3] Git...
where git >nul 2>nul
if errorlevel 1 (winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements) else (echo   * Git ya esta instalado.)
echo.
echo [3/3] Tesseract (OCR)...
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (echo   * Tesseract ya esta instalado.) else (winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements)
echo.
echo ============================================================
echo   Listo. CIERRA esta ventana y abre la app con iniciar.bat
echo ============================================================
pause
