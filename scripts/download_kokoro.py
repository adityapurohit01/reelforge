"""Helper to download Kokoro-82M ONNX model and voice embeddings."""
import os
import sys
import time
import urllib.request
from pathlib import Path

KOKORO_DIR = Path("assets/kokoro")
KOKORO_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = KOKORO_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = KOKORO_DIR / "voices-v1.0.bin"

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"[OK] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"Downloading {dest.name} from {url}...")
    start_t = time.perf_counter()
    urllib.request.urlretrieve(url, dest)
    elapsed = time.perf_counter() - start_t
    print(f"[OK] Downloaded {dest.name} ({dest.stat().st_size / 1e6:.1f} MB) in {elapsed:.1f}s")


if __name__ == "__main__":
    download_file(MODEL_URL, MODEL_PATH)
    download_file(VOICES_URL, VOICES_PATH)
    print("Kokoro assets ready.")
