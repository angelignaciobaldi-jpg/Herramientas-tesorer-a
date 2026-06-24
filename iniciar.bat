@echo off
chcp 65001 >nul
title Herramienta Integral de Tesoreria
cd /d "%~dp0"

echo ============================================================
echo   Herramienta Integral de Tesoreria
echo ============================================================
echo.

echo [1/3] Buscando actualizaciones (git pull)...
git pull
if errorlevel 1 (
    echo   * No se pudo actualizar (sin internet o cambios locales).
    echo   * Se abrira la version local actual.
)
echo.

echo [2/3] Verificando dependencias...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo.

echo [3/3] Iniciando la aplicacion...
python "aplicación.py"

REM Si la app cierra con error, deja ver el mensaje.
if errorlevel 1 (
    echo.
    echo La aplicacion termino con un error. Revisa el mensaje de arriba.
    pause
)
