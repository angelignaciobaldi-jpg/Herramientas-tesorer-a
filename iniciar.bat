@echo off
title Herramienta Integral de Tesoreria
cd /d "%~dp0"
echo ============================================================
echo   Herramienta Integral de Tesoreria
echo ============================================================
echo.
echo [1/3] Buscando actualizaciones (git pull)...
git pull
if errorlevel 1 echo   * No se pudo actualizar; se abrira la version local.
echo.
echo [2/3] Verificando dependencias...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo.
echo [3/3] Iniciando la aplicacion...
echo   (esta ventana se cierra sola si la app abre correctamente)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$log = Join-Path $env:TEMP ('tesoreria_error_' + $PID + '.log'); $p = Start-Process pythonw -ArgumentList 'app.py' -WorkingDirectory (Get-Location).Path -PassThru -RedirectStandardError $log; Start-Sleep -Seconds 7; Get-ChildItem (Join-Path $env:TEMP 'tesoreria_error_*.log') -ErrorAction SilentlyContinue | Where-Object { $_.FullName -ne $log } | Remove-Item -Force -ErrorAction SilentlyContinue; if ($p.HasExited -and $p.ExitCode -ne 0) { Write-Host ''; Write-Host '*** La aplicacion no pudo iniciar. Detalle del error: ***' -ForegroundColor Red; if (Test-Path $log) { Get-Content $log }; exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo.
  echo Copia el error de arriba si necesitas reportarlo.
  pause
)
