# core/hw_adapter.py — part of PyBase core

import psutil
import platform

VERSION=0.1

# Detect the presence of GPU
def detect_gpu():
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        return len(gpus) > 0
    except:
        return False


def get_hardware_profile():
    """
    Retrieves and prints CPU core information, frequency, and usage.
    """
    # Number of logical cores (includes hyperthreading)
    logical_cores = psutil.cpu_count(logical=True)
    # Number of physical cores (true cores, excludes hyperthreading)
    physical_cores = psutil.cpu_count(logical=False)
    # CPU frequency (current, min, max)
    cpu_freq = psutil.cpu_freq()

    return {
        "cpu_logical":logical_cores,
        "cpu_physical":physical_cores,
        "cpu_freq":cpu_freq,
        "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "has_gpu": detect_gpu(),
        "platform": f"{platform.system()}-{platform.release()}"}
    

# Call the function to display CPU info
print(get_hardware_profile())
