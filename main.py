import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import whisper
import os
import threading
import datetime
import sys
import shutil
import imageio_ffmpeg
import subprocess
import re
import time
import io
import torch

import warnings
# Suppress specific PyTorch warning usually seen in Nightly builds with older Whisper versions
warnings.filterwarnings("ignore", message="Using a non-tuple sequence for multidimensional indexing is deprecated")

# --- 1. FFmpeg Setup Fix ---
# Whisper relies on the command 'ffmpeg'. We ensure it exists in the Python Scripts folder.
def setup_ffmpeg():
    try:
        # Get the path to the bundled ffmpeg binary
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Target path: venv/Scripts/ffmpeg.exe (directory where python.exe resides)
        # This directory is guaranteed to be in PATH when running from venv.
        scripts_dir = os.path.dirname(sys.executable)
        target_ffmpeg = os.path.join(scripts_dir, "ffmpeg.exe")
        
        # Check if it works
        if shutil.which("ffmpeg") is None and not os.path.exists(target_ffmpeg):
            print(f"Installing FFmpeg to {target_ffmpeg}...")
            shutil.copy(ffmpeg_exe, target_ffmpeg)
            # Also invoke os.environ update just in case it's not picked up immediately
            os.environ["PATH"] += os.pathsep + scripts_dir
            
    except Exception as e:
        print(f"Warning during FFmpeg setup: {e}")

setup_ffmpeg()

# --- 2. Stdout Redirector for Progress Parsing ---
class StdoutRedirector:
    def __init__(self, callback):
        self.callback = callback
        self.buffer = ""

    def write(self, message):
        # Buffer text to handle fragmented writes
        self.buffer += message
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.callback(line + "\n")

    def flush(self):
        pass

class SubtitleGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Whisper - Auto Subtitle Generator")
        self.root.geometry("700x650")

        # Variables
        self.video_path_var = tk.StringVar()
        self.model_size_var = tk.StringVar(value="base")
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.is_running = False
        self.video_duration = 0

        # UI Components
        self.create_widgets()

    def create_widgets(self):
        # File Selection Block
        file_frame = tk.LabelFrame(self.root, text="Step 1: Select Video File", padx=10, pady=10)
        file_frame.pack(fill="x", padx=10, pady=5)

        tk.Entry(file_frame, textvariable=self.video_path_var, width=50).pack(side="left", padx=5, fill="x", expand=True)
        tk.Button(file_frame, text="Browse", command=self.browse_file).pack(side="left", padx=5)

        # Model Selection Block
        model_frame = tk.LabelFrame(self.root, text="Step 2: Settings", padx=10, pady=10)
        model_frame.pack(fill="x", padx=10, pady=5)
        
        # Model Size
        tk.Label(model_frame, text="Model Size:").pack(side="left", padx=5)
        models = ["tiny", "base", "small", "medium", "large"]
        for model in models:
            tk.Radiobutton(model_frame, text=model.capitalize(), variable=self.model_size_var, value=model).pack(side="left", padx=(0, 10))

        # Language Selection
        tk.Label(model_frame, text="Language:").pack(side="left", padx=5)
        self.language_var = tk.StringVar(value="Korean")
        languages = ["Auto", "Korean", "English", "Japanese", "Chinese"]
        self.lang_combo = ttk.Combobox(model_frame, textvariable=self.language_var, values=languages, state="readonly", width=10)
        self.lang_combo.pack(side="left", padx=5)
        
        # Action Block
        action_frame = tk.Frame(self.root, padx=10, pady=10)
        action_frame.pack(fill="x", padx=10, pady=5)

        self.run_btn = tk.Button(action_frame, text="Generate Subtitles", command=self.start_transcription, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2)
        self.run_btn.pack(pady=5, fill="x")

        # Progress Block
        progress_frame = tk.LabelFrame(self.root, text="Progress", padx=10, pady=10)
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=5)
        
        self.progress_label = tk.Label(progress_frame, text="0%")
        self.progress_label.pack()

        # Log Block
        log_frame = tk.LabelFrame(self.root, text="Logs", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

        # Status Bar
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, message):
        self.root.after(0, lambda: self._log_impl(message))

    def _log_impl(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message) 
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
    
    def set_status(self, message):
        self.root.after(0, lambda: self.status_var.set(message))

    def update_progress_from_log(self, message):
        # Update logs (log method is now thread-safe)
        self.log(message)
        
        # Parse timestamp from Whisper verbose output.
        # Format can be [00:00.000 --> 00:05.000] (MM:SS.mmm) or [00:00:00.000 --> ...] (HH:MM:SS.mmm)
        # We look for the END timestamp after '-->'.
        
        # Regex for HH:MM:SS.mmm
        match_hms = re.search(r"--> (\d{1,2}):(\d{2}):(\d{2})\.(\d{3})", message)
        
        # Regex for MM:SS.mmm
        match_ms = re.search(r"--> (\d{1,2}):(\d{2})\.(\d{3})", message)
        
        current_seconds = 0
        found = False

        if match_hms:
            h, m, s, ms = map(int, match_hms.groups())
            current_seconds = h * 3600 + m * 60 + s + ms / 1000.0
            found = True
        elif match_ms:
            m, s, ms = map(int, match_ms.groups())
            current_seconds = m * 60 + s + ms / 1000.0
            found = True
            
        if found and self.video_duration > 0:
            percent = min((current_seconds / self.video_duration) * 100, 99)
            self.root.after(0, lambda: self.progress_var.set(percent))
            self.root.after(0, lambda: self.progress_label.config(text=f"{int(percent)}%"))

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.flv")])
        if filename:
            self.video_path_var.set(filename)

    def get_video_duration(self, video_path):
        try:
            # Run ffmpeg to get duration
            result = subprocess.run(
                ["ffmpeg", "-i", video_path], 
                stderr=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                text=True,
                encoding="utf-8",
                errors="replace" # Handle potential encoding errors
            )
            # Search for "Duration: 00:00:00.00"
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", result.stderr)
            if match:
                h, m, s, cs = map(int, match.groups())
                return h * 3600 + m * 60 + s + cs / 100.0
        except Exception as e:
            print(f"Error getting duration: {e}")
        return 0

    def start_transcription(self):
        if self.is_running:
            return
        
        video_path = self.video_path_var.get()
        if not video_path or not os.path.exists(video_path):
            messagebox.showerror("Error", "Please select a valid video file.")
            return

        self.is_running = True
        self.run_btn.config(state="disabled", text="Processing...")
        self.set_status("Initializing...")
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        
        # Clear logs
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')

        # Run in separate thread
        thread = threading.Thread(target=self.run_process, args=(video_path, self.model_size_var.get(), self.language_var.get()))
        thread.start()

    def run_process(self, video_path, model_size, language_selection):
        try:
            # 1. Get Duration
            self.set_status("Analyzing video...")
            self.video_duration = self.get_video_duration(video_path)
            self.log(f"Video Duration: {self.video_duration} seconds\n")

            # 2. Load Model
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.set_status(f"Loading model '{model_size}' on {device.upper()}...")
            self.log(f"Loading model '{model_size}' on device: {device.upper()}... (First time load may take a while)\n")
            model = whisper.load_model(model_size, device=device)
            
            # 3. Transcribe
            self.set_status("Transcribing...")
            self.log(f"Transcribing '{os.path.basename(video_path)}'...\n")
            
            # Hook stdout and stderr
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = StdoutRedirector(self.update_progress_from_log)
            sys.stderr = StdoutRedirector(self.update_progress_from_log)
            
            # Prepare args
            transcribe_args = {"fp16": False, "verbose": True}
            if language_selection != "Auto":
                # Extended map if needed, but Whisper handles 'Korean', 'English' mainly via codes internally or full names.
                # It's safer to map to codes: ko, en, ja, zh
                lang_map = {
                    "Korean": "ko",
                    "English": "en",
                    "Japanese": "ja",
                    "Chinese": "zh"
                }
                code = lang_map.get(language_selection)
                if code:
                    transcribe_args["language"] = code
                    self.log(f"Forcing language: {language_selection} ({code})\n")

            try:
                result = model.transcribe(video_path, **transcribe_args)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_label.config(text="100%"))
            
            # 4. Save
            self.set_status("Saving...")
            srt_path = os.path.splitext(video_path)[0] + ".srt"
            self.save_as_srt(result["segments"], srt_path)
            
            self.log(f"\nSaved subtitles to: {srt_path}\n")
            
            def show_success():
                if messagebox.askyesno("Success", f"Subtitle generated successfully!\n\nFile saved to:\n{srt_path}\n\nOpen output folder now?"):
                    try:
                        os.startfile(os.path.dirname(srt_path))
                    except Exception:
                        pass

            self.root.after(0, show_success)
            
        except Exception as e:
            self.log(f"\nError: {str(e)}\n")
            self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred:\n{str(e)}"))
        
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.run_btn.config(state="normal", text="Generate Subtitles"))
            self.set_status("Ready")

    def save_as_srt(self, segments, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments):
                start = self.format_timestamp(segment["start"])
                end = self.format_timestamp(segment["end"])
                text = segment["text"].strip()
                
                f.write(f"{i+1}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")

    def format_timestamp(self, seconds):
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int(td.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

if __name__ == "__main__":
    root = tk.Tk()
    app = SubtitleGeneratorApp(root)
    root.mainloop()
