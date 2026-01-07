@echo off
cd /d "%~dp0"
echo Uninstalling any existing torch...
venv\Scripts\pip uninstall -y torch torchvision torchaudio

echo Installing CUDA-enabled torch (Nightly cu118 for Python 3.13)...
venv\Scripts\pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu118

echo Verifying CUDA...
venv\Scripts\python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"
pause
