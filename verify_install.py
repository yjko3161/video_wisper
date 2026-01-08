import os
import time
print("Importing faster_whisper...")
from faster_whisper import WhisperModel
print("Import success.")

try:
    print("Loading tiny model on CUDA...")
    start = time.time()
    model = WhisperModel("tiny", device="cuda", compute_type="float16")
    print(f"Model loaded in {time.time() - start:.2f}s")
    
    print("Transcribing test...")
    # Generate a dummy file if needed, or just warn
    if not os.path.exists("test.wav"):
        print("No test file, skipping transcription but model load worked.")
    else:
        segments, info = model.transcribe("test.wav")
        print(list(segments))
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Verification done.")
