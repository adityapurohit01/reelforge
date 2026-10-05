"""Benchmark Kokoro-82M TTS on AMD Ryzen AI 7 (7840U) CPU.
Measures: Real-Time Factor (RTF), synthesis latency, generated audio duration, and peak memory.
"""
import time
import json
import soundfile as sf
from pathlib import Path
from kokoro_onnx import Kokoro

KOKORO_DIR = Path("assets/kokoro")
MODEL_PATH = str(KOKORO_DIR / "kokoro-v1.0.onnx")
VOICES_PATH = str(KOKORO_DIR / "voices-v1.0.bin")

TEST_UTTERANCES = [
    ("af_bella", "Thank you for calling Apex Auto Care. How can I help you today?"),
    ("am_adam", "Hi there, I need to get my brake pads checked sometime tomorrow afternoon."),
    ("af_nicole", "I can certainly help you with that. We have an opening at two thirty or four PM. Which works better for you?"),
    ("am_michael", "Four PM works great. Do you also provide a courtesy vehicle while the car is in the bay?"),
    ("af_sarah", "Yes, we have a courtesy car available. I have reserved the slot for you. A confirmation text has just been sent to your phone."),
]


def benchmark_kokoro() -> dict:
    print("\n=======================================================")
    print("Benchmarking Kokoro-82M TTS on CPU")
    print("=======================================================")
    
    start_init = time.perf_counter()
    kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    init_time = time.perf_counter() - start_init
    print(f"Kokoro initialization time: {init_time:.2f}s")
    
    total_audio_duration = 0.0
    total_inference_time = 0.0
    results = []
    
    out_dir = Path("runs/benchmark_tts")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for i, (voice, text) in enumerate(TEST_UTTERANCES):
        t0 = time.perf_counter()
        samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
        t_infer = time.perf_counter() - t0
        
        audio_dur = len(samples) / sample_rate
        rtf = t_infer / audio_dur if audio_dur > 0 else 0.0
        
        total_audio_duration += audio_dur
        total_inference_time += t_infer
        
        wav_path = out_dir / f"turn_{i}_{voice}.wav"
        sf.write(str(wav_path), samples, sample_rate)
        
        print(f"[{i+1}/{len(TEST_UTTERANCES)}] Voice: {voice} | Text: \"{text[:35]}...\"")
        print(f"  -> Generated: {audio_dur:.2f}s audio in {t_infer:.2f}s | RTF: {rtf:.3f} ({1/rtf:.1f}x real-time)")
        results.append({
            "voice": voice,
            "text": text,
            "audio_duration_s": round(audio_dur, 2),
            "inference_time_s": round(t_infer, 3),
            "rtf": round(rtf, 3)
        })
        
    avg_rtf = total_inference_time / total_audio_duration if total_audio_duration > 0 else 0.0
    print("\n=== KOKORO TTS SUMMARY ===")
    print(f"Total Speech: {total_audio_duration:.2f}s synthesized in {total_inference_time:.2f}s")
    print(f"Average RTF on CPU: {avg_rtf:.3f} ({1/avg_rtf:.1f}x real-time speed)")
    
    summary = {
        "engine": "Kokoro-82M ONNX",
        "device": "CPU (AMD Ryzen 7840U)",
        "init_time_s": round(init_time, 2),
        "total_audio_s": round(total_audio_duration, 2),
        "total_inference_s": round(total_inference_time, 2),
        "avg_rtf": round(avg_rtf, 3),
        "speedup_factor": round(1 / avg_rtf, 1) if avg_rtf > 0 else 0.0,
        "sample_rate": 24000,
        "trials": results,
    }
    
    with open("docs/kokoro_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    benchmark_kokoro()
