"""Local system validator — detect hardware, suggest runnable models."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

LOCAL_MODELS: list[dict] = [
    {"id": "qwen3-0.6b", "label": "Qwen3 0.6B", "min_ram_gb": 1,
     "disk_gb": 1, "quality_rank": 1,
     "strengths": "Tiny, instant, basic completions"},
    {"id": "qwen3-1.7b", "label": "Qwen3 1.7B", "min_ram_gb": 2,
     "disk_gb": 2, "quality_rank": 2,
     "strengths": "Quick edits, formatting, simple Q&A"},
    {"id": "qwen3-4b", "label": "Qwen3 4B", "min_ram_gb": 4,
     "disk_gb": 3, "quality_rank": 3,
     "strengths": "Grep, shell, regex, syntax lookups"},
    {"id": "qwen3-8b", "label": "Qwen3 8B", "min_ram_gb": 6,
     "disk_gb": 5, "quality_rank": 4,
     "strengths": "Code completion, simple features, tests"},
    {"id": "qwen3-14b", "label": "Qwen3 14B", "min_ram_gb": 10,
     "disk_gb": 9, "quality_rank": 5,
     "strengths": "Multi-file edits, debugging, refactors"},
    {"id": "qwen3-32b", "label": "Qwen3 32B", "min_ram_gb": 20,
     "disk_gb": 20, "quality_rank": 6,
     "strengths": "Strong coding, reasoning, main local workhorse"},
    {"id": "qwen3-30b-a3b", "label": "Qwen3 30B-A3B (MoE)", "min_ram_gb": 8,
     "disk_gb": 18, "quality_rank": 5,
     "strengths": "MoE: fast inference, only 3B active params"},
    {"id": "deepseek-r1-7b", "label": "DeepSeek R1 7B (distilled)",
     "min_ram_gb": 6, "disk_gb": 5, "quality_rank": 4,
     "strengths": "Reasoning, chain-of-thought, math"},
    {"id": "deepseek-r1-14b", "label": "DeepSeek R1 14B (distilled)",
     "min_ram_gb": 10, "disk_gb": 9, "quality_rank": 5,
     "strengths": "Strong reasoning at mid-size"},
    {"id": "codestral-22b", "label": "Codestral 22B", "min_ram_gb": 14,
     "disk_gb": 14, "quality_rank": 5,
     "strengths": "Code completion, FIM, Mistral quality"},
    {"id": "llama4-scout", "label": "Llama 4 Scout 109B (MoE)",
     "min_ram_gb": 32, "disk_gb": 65, "quality_rank": 6,
     "strengths": "10M context, 16 experts, 17B active"},
    {"id": "llama4-maverick", "label": "Llama 4 Maverick 400B (MoE)",
     "min_ram_gb": 48, "disk_gb": 240, "quality_rank": 7,
     "strengths": "128 experts, strong multimodal, near-frontier"},
]


def detect_hardware() -> dict:
    ram_gb = _get_ram_gb()
    gpu = _detect_gpu()
    disk_free = _get_disk_free_gb()
    return {
        "ram_gb": ram_gb,
        "cpu_cores": os.cpu_count() or 1,
        "disk_free_gb": disk_free,
        "gpu": gpu,
        "platform": platform.system().lower(),
        "arch": platform.machine(),
        "ollama_installed": shutil.which("ollama") is not None,
    }


def suggest_local_models(hw: dict) -> list[dict]:
    ram = hw.get("ram_gb", 0)
    disk = hw.get("disk_free_gb", 0)
    gpu_vram = hw.get("gpu", {}).get("vram_gb", 0)
    usable_ram = max(ram, gpu_vram)
    results = []
    for m in LOCAL_MODELS:
        req_ram = m["min_ram_gb"]
        req_disk = m.get("disk_gb", 0)
        if req_disk > disk:
            continue
        fit = _classify_fit(usable_ram, req_ram)
        if fit == "too_large":
            continue
        results.append({**m, "fit": fit})
    results.sort(key=lambda x: x["quality_rank"], reverse=True)
    return results


def _classify_fit(available_gb: float, required_gb: float) -> str:
    if available_gb >= required_gb * 1.5:
        return "comfortable"
    if available_gb >= required_gb:
        return "tight"
    return "too_large"


def _get_ram_gb() -> float:
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"],
                text=True, timeout=5,
            )
            return round(int(out.strip()) / (1024 ** 3), 1)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 ** 2), 1)
    except Exception:
        pass
    return 0


def _detect_gpu() -> dict:
    sys = platform.system()
    if sys == "Darwin":
        return _detect_metal()
    return _detect_nvidia()


def _detect_metal() -> dict:
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True, timeout=10,
        )
        if "Apple" in out or "M1" in out or "M2" in out or "M3" in out or "M4" in out:
            ram = _get_ram_gb()
            return {"type": "metal", "name": "Apple Silicon", "vram_gb": ram}
    except Exception:
        pass
    return {"type": "none", "name": "", "vram_gb": 0}


def _detect_nvidia() -> dict:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            text=True, timeout=10,
        )
        line = out.strip().split("\n")[0]
        parts = line.split(",")
        name = parts[0].strip()
        vram_mb = int(parts[1].strip())
        return {
            "type": "cuda",
            "name": name,
            "vram_gb": round(vram_mb / 1024, 1),
        }
    except Exception:
        return {"type": "none", "name": "", "vram_gb": 0}


def _get_disk_free_gb() -> float:
    try:
        stat = os.statvfs(os.path.expanduser("~"))
        return round(stat.f_bavail * stat.f_frsize / (1024 ** 3), 1)
    except Exception:
        return 0
