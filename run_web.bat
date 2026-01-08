@echo off
cd /d "%~dp0"
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
) else (
    if not exist venv\Lib\site-packages\streamlit (
         echo Installing dependencies...
         venv\Scripts\pip install -r requirements.txt
    )
)
echo Starting Video Whisper Web...
venv\Scripts\streamlit run app_web.py
pause
