@echo off
setlocal
cd /d "%~dp0"

set VERSION=%~1
if "%VERSION%"=="" set VERSION=1.0.0

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\publish-from-master.ps1" -Version "%VERSION%"
set ERR=%ERRORLEVEL%

echo.
if "%ERR%"=="0" (
  echo ============================================================
  echo FL-ENTERTAINMENT %VERSION% PUBBLICATO
  echo ============================================================
) else (
  echo ============================================================
  echo PUBBLICAZIONE FALLITA - ERRORE %ERR%
  echo ============================================================
)
echo.
pause
exit /b %ERR%
