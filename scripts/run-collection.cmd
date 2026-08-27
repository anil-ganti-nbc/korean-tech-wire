@echo off
setlocal enabledelayedexpansion
rem Manual, INTERACTIVE collection run for Korean Tech Wire.
rem
rem The desktop dashboard launcher (native\windows\launcher.py) is
rem deliberately read-only - it never fetches new articles on its own, and
rem there is no Windows Scheduled Task wired up for this repo either. This
rem script is the actual, discoverable way to populate/update the local
rem SQLite database on Windows. It uses the same config.local.yaml, same
rem database, and same run lock as the dashboard reads from - this is just
rem a visible way to trigger a collection and see whether it succeeded or
rem failed before going looking for a log file. Output is kept on-screen
rem AND written to a timestamped file under logs\, so a fatal error is
rem never hidden.
cd /d "%~dp0.."

set "EXE=.venv\Scripts\korean-tech-wire.exe"
set "CONFIG=config\config.local.yaml"

if not exist "%EXE%" (
    echo ERROR: Korean Tech Wire virtual environment not found at:
    echo   %CD%\%EXE%
    echo Run setup first from this repo directory, e.g.:
    echo   uv sync --locked --all-extras --python 3.12
    pause
    exit /b 1
)

if not exist "%CONFIG%" (
    echo ERROR: Local config not found at:
    echo   %CD%\%CONFIG%
    echo Create it from the tracked example first, e.g.:
    echo   copy config\config.example.yaml config\config.local.yaml
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
set "LOGFILE=logs\collection-%STAMP%.log"

echo Korean Tech Wire - manual collection run
echo Repo:     %CD%
echo Config:   %CD%\%CONFIG%
echo Log:      %CD%\%LOGFILE%
echo.

powershell -NoProfile -Command "& '%EXE%' --config '%CONFIG%' run 2>&1 | Tee-Object -FilePath '%LOGFILE%'"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo RESULT: collection command completed ^(exit 0^). See the "Run:" line
    echo         above - "success" means every attempted source succeeded;
    echo         "partial failure" means at least one source failed even
    echo         though the CLI itself exited cleanly. ERROR lines above list
    echo         per-source failures. Full detail also in %LOGFILE%.
) else (
    echo RESULT: collection FAILED to complete ^(exit %EXITCODE%^). See
    echo         %LOGFILE% and the output above for the error.
)
echo.
echo Full log saved to: %CD%\%LOGFILE%
pause
exit /b %EXITCODE%
