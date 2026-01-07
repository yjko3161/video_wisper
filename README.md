# Video Whisper - Auto Subtitle Generator

video_wisper helps you automatically generate `.srt` subtitles for your video files using OpenAI's state-of-the-art **Whisper** model.

It features a simple **Graphical User Interface (GUI)** and handles complex dependencies like FFmpeg automatically, making it easy to use for anyone.

## 🚀 Key Features

*   **Easy to Use GUI**: No command line needed. Just browse for a video and click "Generate".
*   **Automatic FFmpeg**: No need to install FFmpeg on your system manually. The app comes with its own binary.
*   **Multiple Models**: Choose from `tiny`, `base`, `small`, `medium`, and `large` models to balance speed vs. accuracy.
*   **Standard Output**: Generates `.srt` files compatible with all major video players (VLC, YouTube, etc.).
*   **GPU Support**: Automatically uses CUDA (GPU) if available for faster processing.

## 🛠 Prerequisites

*   **Python 3.8+** installed on your system.

## 📥 Installation & Setup

1.  **Clone or Download** this repository.
2.  Navigate to the project folder.
3.  **Run `run.bat`**.
    *   This script will automatically create a virtual environment (`venv`), install all required libraries (`openai-whisper`, `torch`, etc.), and launch the application.
    *   *Note: The first run might take a few minutes to install dependencies.*

## 📖 How to Use

1.  Double-click **`run.bat`** to start the application.
2.  **Step 1**: Click **Browse** and select your video file (`.mp4`, `.mkv`, `.avi`, etc.).
3.  **Step 2**: Select a **Model Size**.
    *   `Tiny`/`Base`: Very fast, good for clear audio.
    *   `Small`/`Medium`: Slower but much more accurate.
    *   `Large`: High accuracy, requires more RAM/VRAM.
4.  Click **Generate Subtitles**.
5.  Wait for the process to finish. The `.srt` file will be saved in the same folder as your video.

## 📂 Project Structure

*   `main.py`: Core application script with GUI and Whisper logic.
*   `run.bat`: Launcher script that handles environment setup.
*   `requirements.txt`: List of Python dependencies.
*   `venv/`: Virtual environment folder (created automatically).

## 💡 Notes

*   **First Run**: When you use a model (e.g., `base`) for the first time, Whisper will download the model weights. This requires an internet connection.
*   **Performance**: Transcription speed depends heavily on your hardware (CPU vs GPU).

---
*Powered by [OpenAI Whisper](https://github.com/openai/whisper)*
