@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [MediaForge] Ambiente virtual nao encontrado. Execute primeiro:
    echo     py -3.12 -m venv .venv
    echo     .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m mediaforge %*
if errorlevel 1 pause
endlocal
