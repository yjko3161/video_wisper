import streamlit as st
import os
import tempfile
import datetime
import torch
from faster_whisper import WhisperModel
import imageio_ffmpeg
import subprocess
import re
import time

# Page Config
st.set_page_config(
    page_title="Video Whisper - Web",
    page_icon="🎬",
    layout="wide"
)

# Styling
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        height: 3em;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def format_timestamp(seconds):
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def get_video_duration(video_path):
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        creationflags = 0x08000000 if os.name == 'nt' else 0
        result = subprocess.run(
            [ffmpeg_exe, "-i", video_path], 
            creationflags=creationflags,
            stdin=subprocess.DEVNULL, 
            stderr=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", result.stderr)
        if match:
            h, m, s, cs = map(int, match.groups())
            return h * 3600 + m * 60 + s + cs / 100.0
    except Exception as e:
        print(f"Error getting duration: {e}")
    return 0

@st.cache_resource(show_spinner=False)
def load_model(model_size, device, compute_type):
    return WhisperModel(model_size, device=device, compute_type=compute_type)

def main():
    st.title("🎬 Video Whisper - Auto Subtitle Generator")
    st.markdown("Upload a video file to generate subtitles (.srt) automatically using **Faster-Whisper**.")

    # Sidebar Settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        model_size = st.selectbox(
            "Model Size",
            ["tiny", "base", "small", "medium", "large-v3"],
            index=3,
            help="Larger models are more accurate but slower. 'Medium' is recommended for RTX 2060+."
        )

        if model_size == "large":
            st.warning("⚠️ 'Large' model is ~3GB. First time load will take a while to download. Please check the Terminal window for download progress.")
        
        language = st.selectbox(
            "Language",
            ["Auto", "Korean", "English", "Japanese", "Chinese"],
            index=1
        )
        
        initial_prompt = st.text_input(
            "Hint (Optional)",
            help="Keywords or context to improve accuracy (e.g., 'AI, Lecture, Depp Learning')."
        )
        
        vad_filter = st.checkbox("Enable VAD Filter", value=True, help="Reduces hallucinations in silent parts.")
        suppress_singing = st.checkbox("Suppress Singing (Experimental)", value=False, help="Tries to ignore singing/lyrics via prompt engineering.")
        high_accuracy = st.checkbox("High Accuracy Mode (Slower)", value=False, help="Increases Beam Size to 10. Good for mumbling or fast speech.")
        strict_mode = st.checkbox("Strict Filtering (Anti-Loop)", value=True, help="Prevents loops but might skip mumbled speech. Uncheck if too much is skipped.")

        st.info(f"Running on: **{'CUDA (GPU)' if torch.cuda.is_available() else 'CPU'}**")

    # Main Area
    uploaded_file = st.file_uploader("Step 1: Choose a video file", type=["mp4", "mkv", "avi", "mov", "flv"])

    if uploaded_file is not None:
        # Check file extension for browser compatibility
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        if file_ext in [".mp4", ".mov", ".webm"]:
             st.video(uploaded_file)
        else:
             st.warning(f"⚠️ Video preview is not supported for '{file_ext}' files in this browser. Don't worry, transcription will still work!")

        if st.button("Generate Subtitles", type="primary"):
            # Temporary file handling
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                video_path = tmp_file.name

            try:
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                # 1. Get Duration
                status_text.text("Analyzing video duration...")
                duration = get_video_duration(video_path)
                
                # 2. Load Model
                device = "cuda" if torch.cuda.is_available() else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
                
                status_text.text(f"Loading model '{model_size}' on {device.upper()}... (Check Terminal for download progress if stuck)")
                model = load_model(model_size, device, compute_type)
                
                # 3. Prepare Args
                beam_size = 10 if high_accuracy else 5
                transcribe_args = {"beam_size": beam_size}
                if language != "Auto":
                    lang_map = {"Korean": "ko", "English": "en", "Japanese": "ja", "Chinese": "zh"}
                    if language in lang_map:
                        transcribe_args["language"] = lang_map[language]
                
                # Construct Prompt
                final_prompt = initial_prompt if initial_prompt else ""
                if suppress_singing:
                    # Simplified prompt to reduce negative interference
                    suppress_msg = "Ignore singing and lyrics."
                    final_prompt = f"{suppress_msg} {final_prompt}".strip()

                if final_prompt:
                    transcribe_args["initial_prompt"] = final_prompt

                transcribe_args["vad_filter"] = vad_filter
                
                if strict_mode:
                    transcribe_args["condition_on_previous_text"] = False
                    transcribe_args["no_speech_threshold"] = 0.6 
                    transcribe_args["compression_ratio_threshold"] = 2.4
                else:
                    # Hyper-Permissive Settings (Capture EVERYTHING)
                    transcribe_args["condition_on_previous_text"] = True 
                    transcribe_args["no_speech_threshold"] = 0.95 # Higher = Harder to skip as silence
                    transcribe_args["log_prob_threshold"] = None # Never skip based on low confidence

                # 4. Transcribe
                status_text.text("Transcribing... This may take a while.")
                segments_generator, info = model.transcribe(video_path, **transcribe_args)
                
                st.success(f"Detected language: {info.language.upper()} (Probability: {info.language_probability:.2f})")
                
                # Real-time preview container
                preview_placeholder = st.empty()
                full_transcript = ""

                segments = []
                # Process segments
                for i, segment in enumerate(segments_generator):
                    segments.append(segment)
                    
                    # Update real-time preview
                    full_transcript += f"[{format_timestamp(segment.start)} -> {format_timestamp(segment.end)}] {segment.text}\n"
                    preview_placeholder.text_area("Live Preview", value=full_transcript, height=300)

                    if duration > 0:
                        percent = min(int((segment.end / duration) * 100), 100)
                        progress_bar.progress(percent)
                
                progress_bar.progress(100)
                status_text.text("Subtitle generation complete!")
                
                # 5. Create SRT & TXT Content
                srt_content = ""
                txt_content = ""
                for i, segment in enumerate(segments):
                    start = format_timestamp(segment.start)
                    end = format_timestamp(segment.end)
                    text = segment.text.strip()
                    srt_content += f"{i+1}\n{start} --> {end}\n{text}\n\n"
                    txt_content += f"{text} "
                
                # 6. Download Buttons
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="Download .SRT File",
                        data=srt_content,
                        file_name=os.path.splitext(uploaded_file.name)[0] + ".srt",
                        mime="text/plain"
                    )
                with col2:
                    st.download_button(
                        label="Download Full Text (.txt)",
                        data=txt_content.strip(),
                        file_name=os.path.splitext(uploaded_file.name)[0] + ".txt",
                        mime="text/plain"
                    )
                
                # Display text preview
                with st.expander("Preview Subtitles"):
                    st.text(srt_content)

            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                # Cleanup temp file
                if os.path.exists(video_path):
                    os.remove(video_path)

if __name__ == "__main__":
    main()
