import ctypes
import os
import sys
import shutil
import time
import struct

# ==========================================
# 1. SETUP
# ==========================================
def find_project_root():
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(current, "storage_manager")):
            return current
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    return os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = find_project_root()
DLL_PATH = os.path.join(PROJECT_ROOT, "storage_manager", "lib", "rawCPP", "page.dll")
DB_FOLDER = os.path.join(PROJECT_ROOT, "databases")

print(f"--- PRECISION STRESS TEST (FILE-PER-PAGE) ---")
print(f"DLL: {DLL_PATH}")

if not os.path.exists(DLL_PATH):
    print("CRITICAL: DLL not found.")
    sys.exit(1)

try:
    lib = ctypes.CDLL(DLL_PATH, winmode=0) if os.name == 'nt' else ctypes.CDLL(DLL_PATH)
except OSError as e:
    print(f"Load Failed: {e}")
    sys.exit(1)

# ==========================================
# 2. DEFINING SIGNATURES (FIXED)
# ==========================================
# 1. Create/Destroy
lib.PM_Create.restype = ctypes.c_void_p
lib.PM_Create.argtypes = [ctypes.c_char_p]

lib.PM_Destroy.argtypes = [ctypes.c_void_p]
lib.PM_Destroy.restype = None

# 2. Page Management
lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int] # <--- FIXED
lib.PM_CreatePage.restype = None

lib.PM_Load.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_Load.restype = None

lib.PM_Unload.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_Unload.restype = None

# 3. Data IO
lib.PM_Write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int]
lib.PM_Write.restype = None

lib.PM_GetData.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_GetData.restype = ctypes.POINTER(ctypes.c_uint8)

lib.PM_GetSize.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_GetSize.restype = ctypes.c_int


# ==========================================
# 3. HELPER: FORMATTING
# ==========================================
def print_stats(phase_name, duration, num_items, total_bytes):
    if duration <= 0: duration = 0.000001 # Prevent div/0
    iops = num_items / duration
    mb_sec = (total_bytes / (1024*1024)) / duration
    
    print(f"[{phase_name}]")
    print(f"   Duration : {duration:.4f} seconds")
    print(f"   Speed    : {iops:,.0f} files/sec")
    print(f"   Throughput: {mb_sec:,.2f} MB/s")
    print("-" * 40)

# ==========================================
# 4. THE TEST
# ==========================================
def run_test():
    NUM_PAGES = 10000
    PAGE_SIZE = 100 * 1024 # 100 KB
    TOTAL_BYTES = NUM_PAGES * PAGE_SIZE
    
    print(f"Target: {NUM_PAGES} Pages | {PAGE_SIZE/1024:.0f} KB each | {TOTAL_BYTES/(1024**3):.2f} GB Total\n")

    # Clean
    if os.path.exists(DB_FOLDER): shutil.rmtree(DB_FOLDER)
    os.makedirs(DB_FOLDER)

    # Pre-alloc buffers
    raw_buffer = b'X' * PAGE_SIZE
    c_buffer = (ctypes.c_uint8 * PAGE_SIZE).from_buffer_copy(raw_buffer)
    
    # --- PHASE 1: WRITE TO RAM ---
    pm = lib.PM_Create(DB_FOLDER.encode('utf-8'))
    
    print("1. Writing to RAM (Allocating Pages)...")
    t_start = time.perf_counter()
    
    for i in range(NUM_PAGES):
        lib.PM_CreatePage(pm, i, PAGE_SIZE)
        lib.PM_Write(pm, i, c_buffer, PAGE_SIZE, 0)
        
    t_end = time.perf_counter()
    print_stats("RAM WRITE", t_end - t_start, NUM_PAGES, TOTAL_BYTES)

    # --- PHASE 2: FLUSH TO DISK ---
    print("2. Flushing to Disk (Creating Files)...")
    # Note: We destroy the manager, which forces it to iterate and write every file
    t_start = time.perf_counter()
    
    lib.PM_Destroy(pm)
    
    t_end = time.perf_counter()
    print_stats("DISK FLUSH", t_end - t_start, NUM_PAGES, TOTAL_BYTES)
    
    # Validation
    count = len(os.listdir(DB_FOLDER))
    if count != NUM_PAGES:
        print(f" ! ERROR: Expected {NUM_PAGES} files, found {count}")
        return

    # Cool down (Let OS settle)
    time.sleep(1) 

    # --- PHASE 3: COLD LOAD ---
    print("3. Cold Load (Opening Files from Disk)...")
    pm = lib.PM_Create(DB_FOLDER.encode('utf-8'))
    
    t_start = time.perf_counter()
    
    for i in range(NUM_PAGES):
        lib.PM_Load(pm, i) # This opens the file, reads size, allocs RAM, closes file
        
    t_end = time.perf_counter()
    print_stats("COLD READ", t_end - t_start, NUM_PAGES, TOTAL_BYTES)

    # --- PHASE 4: MODIFY ---
    print("4. Modifying Pages (Dirty Bit Set)...")
    mod_byte = b'Z'
    c_mod = (ctypes.c_uint8 * 1).from_buffer_copy(mod_byte)
    
    t_start = time.perf_counter()
    
    for i in range(NUM_PAGES):
        # Touch just 1 byte to mark dirty
        lib.PM_Write(pm, i, c_mod, 1, 0)
        
    t_end = time.perf_counter()
    print_stats("RAM MODIFY", t_end - t_start, NUM_PAGES, TOTAL_BYTES)

    # --- PHASE 5: RE-SAVE ---
    print("5. Re-Saving (Overwriting Files)...")
    t_start = time.perf_counter()
    
    lib.PM_Destroy(pm)
    
    t_end = time.perf_counter()
    print_stats("DISK UPDATE", t_end - t_start, NUM_PAGES, TOTAL_BYTES)

    print("\nTest Complete.")

if __name__ == "__main__":
    run_test()