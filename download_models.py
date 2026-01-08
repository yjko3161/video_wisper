from faster_whisper import download_model
import os

def download_all_models():
    models = ["tiny", "base", "small", "medium", "large-v3"]
    print("=============================================")
    print(" Downloading Faster-Whisper Models")
    print("=============================================")
    print("This will download models to the local cache so they don't need to be downloaded at runtime.")
    
    for model in models:
        print(f"\n[Downloading {model} model...]")
        try:
            path = download_model(model)
            print(f"✔ Success! Saved to: {path}")
        except Exception as e:
            print(f"❌ Failed to download {model}: {e}")

    print("\nAll downloads finished!")

if __name__ == "__main__":
    download_all_models()
