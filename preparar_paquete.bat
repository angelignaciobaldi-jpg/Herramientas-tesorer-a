@echo off
title Preparar paquete para compartir
cd /d "%~dp0"
pushd "%~dp0.."
set "DESTINO=%CD%\Tesoreria-paquete"
popd
echo ============================================================
echo   Preparando paquete para compartir a usuarios nuevos
echo   Destino: %DESTINO%
echo ============================================================
echo.
robocopy "%~dp0." "%DESTINO%" /E /R:1 /W:1 /NFL /NDL /NJH /NP /XD "dist" "build" "__pycache__" "CARATULAS" "Archivos TXT" ".vscode" /XF "tesoreria.db" "Tesoreria.spec" "ALTABANREGIO 1.xls" "Codigo macro excel"
echo.
echo ============================================================
echo   Listo. Comparte la carpeta:
echo     %DESTINO%
echo ============================================================
pause
