# core/runtime_config.py — part of PyBase core
from core.hw_adapter import get_hardware_profile

DEFAULTS = {
    "min_threads": 2,
    "max_threads": 16,
    "min_cache_mb": 128,
    "max_cache_mb": 4096
}

def get_runtime_config():
    hw = get_hardware_profile()

    physical_cores = hw.get("cpu_physical", 4)
    ram_total_gb = hw.get("ram_total_gb", 8)

    max_threads = min(DEFAULTS["max_threads"], max(DEFAULTS["min_threads"], physical_cores * 2))
    cache_size_mb = min(DEFAULTS["max_cache_mb"], max(DEFAULTS["min_cache_mb"], int(ram_total_gb * 0.1 * 1024)))

    index_mode = "parallel" if max_threads >= 4 else "sequential"

    return {
        "max_threads": max_threads,
        "cache_size_mb": cache_size_mb,
        "index_mode": index_mode,
        "gpu_enabled": hw.get("has_gpu", False)
    }
