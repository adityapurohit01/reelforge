"""Benchmark candidate local LLMs for ReelForge.
Measures: tokens/sec, response latency, peak RAM (Ollama process), JSON validity rate over N generations.
Uses standard library so it can run immediately.
"""
import json
import time
import urllib.request
import urllib.error
import subprocess
import sys
from typing import Dict, Any, List

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

BUSINESS_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "tagline": {"type": "string"},
        "vertical": {"type": "string"},
        "city": {"type": "string"},
        "owner_first_name": {"type": "string"},
        "hours": {
            "type": "object",
            "properties": {
                "weekdays": {"type": "string"},
                "saturday": {"type": "string"},
                "sunday": {"type": "string"}
            },
            "required": ["weekdays", "saturday", "sunday"]
        },
        "services": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "string"},
                    "duration_mins": {"type": "integer"}
                },
                "required": ["name", "price", "duration_mins"]
            }
        },
        "faqs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"}
                },
                "required": ["question", "answer"]
            }
        },
        "booking_rules": {
            "type": "object",
            "properties": {
                "slot_length_mins": {"type": "integer"},
                "buffer_mins": {"type": "integer"}
            },
            "required": ["slot_length_mins", "buffer_mins"]
        }
    },
    "required": ["name", "tagline", "vertical", "city", "owner_first_name", "hours", "services", "faqs", "booking_rules"]
}

PROMPT_TEMPLATE = """You are an expert small business generator. Create a realistic, highly authentic fictional small business profile in the vertical: "{vertical}" located in "{city}".
Return ONLY valid JSON adhering strictly to the schema provided.
Include 6-8 realistic services with local currency prices and 5 FAQ items.
Do not use real trademarked names or real phone numbers."""

VERTICALS = [
    ("Dental Clinic Front Desk", "Pune"),
    ("Auto Repair Garage", "Bengaluru"),
    ("Specialty Bakery", "Lucknow"),
    ("Pet Grooming Spa", "Jaipur"),
    ("Physiotherapy Clinic", "Kochi"),
]


def query_ollama(model: str, prompt: str) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        },
        "keep_alive": 0,  # Unload LLM immediately after generation per memory discipline
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    start_t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - start_t
    res["wall_clock_s"] = elapsed
    return res


def validate_profile_json(raw_text: str) -> bool:
    try:
        data = json.loads(raw_text)
        required = ["name", "tagline", "vertical", "city", "owner_first_name", "hours", "services", "faqs", "booking_rules"]
        for k in required:
            if k not in data:
                return False
        if not isinstance(data["services"], list) or len(data["services"]) < 4:
            return False
        if not isinstance(data["faqs"], list) or len(data["faqs"]) < 3:
            return False
        return True
    except Exception:
        return False


def get_ollama_memory_mb() -> float:
    try:
        cmd = 'powershell -Command "(Get-Process -Name *ollama* -ErrorAction SilentlyContinue | Measure-Object -Property WorkingSet -Sum).Sum / 1MB"'
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        return float(out) if out else 0.0
    except Exception:
        return 0.0


def benchmark_model(model_name: str, n_trials: int = 5) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"Benchmarking model: {model_name} ({n_trials} trials)")
    print(f"=======================================================")
    
    total_tokens = 0
    total_time = 0.0
    valid_json_count = 0
    latencies = []
    tok_per_sec_list = []
    
    for i in range(n_trials):
        v, c = VERTICALS[i % len(VERTICALS)]
        prompt = PROMPT_TEMPLATE.format(vertical=v, city=c)
        print(f"[{i+1}/{n_trials}] Generating profile for '{v}' in '{c}'...")
        try:
            res = query_ollama(model_name, prompt)
            eval_count = res.get("eval_count", 0)
            eval_dur_ns = res.get("eval_duration", 1)
            tps = (eval_count / (eval_dur_ns / 1e9)) if eval_dur_ns else 0.0
            wall_s = res.get("wall_clock_s", 0.0)
            
            raw_response = res.get("response", "")
            is_valid = validate_profile_json(raw_response)
            if is_valid:
                valid_json_count += 1
                
            total_tokens += eval_count
            total_time += wall_s
            latencies.append(wall_s)
            tok_per_sec_list.append(tps)
            
            ram_mb = get_ollama_memory_mb()
            print(f"  -> Tokens: {eval_count} | Speed: {tps:.1f} tok/s | Latency: {wall_s:.2f}s | Valid JSON: {is_valid} | Ollama RAM: {ram_mb:.0f} MB")
        except Exception as e:
            print(f"  -> Error: {e}")
            latencies.append(0.0)
            
    avg_tps = sum(tok_per_sec_list) / len(tok_per_sec_list) if tok_per_sec_list else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    validity_rate = (valid_json_count / n_trials) * 100
    
    return {
        "model": model_name,
        "n_trials": n_trials,
        "avg_tokens_per_sec": round(avg_tps, 2),
        "avg_latency_s": round(avg_latency, 2),
        "valid_json_percent": round(validity_rate, 1),
        "peak_ram_mb": round(get_ollama_memory_mb(), 1),
    }


if __name__ == "__main__":
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    models = ["llama3.2:3b", "llama3.1:latest"]
    results = []
    for m in models:
        r = benchmark_model(m, n_trials=trials)
        results.append(r)
        
    print("\n\n=== BENCHMARK SUMMARY TABLE ===")
    print(f"{'Model':<18} | {'tok/s':<8} | {'Avg Latency':<12} | {'JSON Valid %':<12} | {'RAM (MB)':<10}")
    print("-" * 72)
    for r in results:
        print(f"{r['model']:<18} | {r['avg_tokens_per_sec']:<8} | {r['avg_latency_s']:<10}s | {r['valid_json_percent']:<10}% | {r['peak_ram_mb']:<10}")
        
    with open("docs/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved results to docs/benchmark_results.json")
