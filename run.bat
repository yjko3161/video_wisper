@echo off
cd /d "%~dp0"
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
) else (
    if not exist venv\Lib\site-packages\faster_whisper (
         echo Installing dependencies...
         venv\Scripts\pip install -r requirements.txt
    )
)
echo Starting Video Whisper...
venv\Scripts\python main.py
pause
