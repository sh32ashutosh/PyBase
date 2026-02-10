import ctypes
import struct
import os
import sys
import shutil
import time
import random

# ==========================================
# 1. ROBUST PATH SETUP
# ==========================================
def find_project_root():
    """Finds the 'storage_manager' folder to anchor paths."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(current, "storage_manager")):
            return current
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    return os.path.dirname(os.path.abspath(__file__)) # Fallback

PROJECT_ROOT = find_project_root()
# Adjust this path if your DLL is elsewhere. This matches your previous error log:
DLL_PATH = os.path.join(PROJECT_ROOT, "storage_manager", "lib", "rawCPP", "page.dll")
DB_FOLDER = os.path.join(PROJECT_ROOT, "databases")

print(f"--- CONFIGURATION ---")
print(f"ROOT: {PROJECT_ROOT}")
print(f"DLL : {DLL_PATH}")
print(f"DB  : {DB_FOLDER}")

if not os.path.exists(DLL_PATH):
    print("CRITICAL ERROR: DLL not found. Check path.")
    sys.exit(1)

# Load DLL
try:
    lib = ctypes.CDLL(DLL_PATH, winmode=0) if os.name == 'nt' else ctypes.CDLL(DLL_PATH)
except OSError as e:
    print(f"DLL Load Failed: {e}")
    sys.exit(1)

# ==========================================
# 2. C++ BINDINGS
# ==========================================
lib.PM_Create.argtypes = [ctypes.c_char_p]
lib.PM_Create.restype = ctypes.c_void_p

lib.PM_Destroy.argtypes = [ctypes.c_void_p]

lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

lib.PM_Write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int]

lib.PM_GetData.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_GetData.restype = ctypes.POINTER(ctypes.c_uint8)

lib.PM_GetSize.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_GetSize.restype = ctypes.c_int

lib.PM_Unload.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.PM_Load.argtypes = [ctypes.c_void_p, ctypes.c_int]

# ==========================================
# 3. TEST SUITE
# ==========================================

def run_stress_test():
    # Setup Clean DB
    if os.path.exists(DB_FOLDER): shutil.rmtree(DB_FOLDER)
    os.makedirs(DB_FOLDER)

    pm = lib.PM_Create(DB_FOLDER.encode('utf-8'))
    
    # --- CONFIG ---
    NUM_PAGES = 10000
    MAX_DATA_SIZE = 1024 # Keep small for speed, or increase for heavy RAM test
    
    print(f"\n[STRESS TEST] Generating {NUM_PAGES} Pages with Random Data...")
    
    # Dictionary to hold the "Truth" (what we expect to find)
    # Map: page_id -> bytes
    verification_map = {} 

    start_time = time.time()

    # --- STEP 1: WRITE 10,000 PAGES ---
    for i in range(NUM_PAGES):
        page_id = i
        
        # 1. Generate Random Data
        data_len = random.randint(4, MAX_DATA_SIZE)
        random_data = os.urandom(data_len)
        
        # 2. Store in Python for verification later
        verification_map[page_id] = random_data
        
        # 3. Create & Write to C++ Page
        lib.PM_CreatePage(pm, page_id, data_len)
        
        c_data = (ctypes.c_uint8 * data_len).from_buffer_copy(random_data)
        lib.PM_Write(pm, page_id, c_data, data_len, 0)

        # Progress Indicator
        if i % 1000 == 0:
            print(f" > Written {i}/{NUM_PAGES} pages...", end="\r")

    write_time = time.time() - start_time
    print(f" > COMPLETE: Wrote {NUM_PAGES} pages in {write_time:.2f}s ({NUM_PAGES/write_time:.0f} pages/sec)")


    # --- STEP 2: VERIFY ALL 10,000 PAGES ---
    print(f"\n[VERIFICATION] Reading back {NUM_PAGES} Pages...")
    
    errors = 0
    start_time = time.time()

    for i in range(NUM_PAGES):
        page_id = i
        expected_data = verification_map[page_id]
        expected_len = len(expected_data)
        
        # 1. Get Size from C++
        actual_len = lib.PM_GetSize(pm, page_id)
        
        if actual_len != expected_len:
            print(f" ! ERROR Page {page_id}: Size Mismatch! Expected {expected_len}, Got {actual_len}")
            errors += 1
            continue

        # 2. Get Data Pointer
        ptr = lib.PM_GetData(pm, page_id)
        if not ptr:
            print(f" ! ERROR Page {page_id}: Null Pointer returned!")
            errors += 1
            continue

        # 3. Read & Compare
        actual_data = ctypes.string_at(ptr, actual_len)
        
        if actual_data != expected_data:
            print(f" ! ERROR Page {page_id}: Data Corruption!")
            # Print first 10 bytes for debug
            print(f"   Exp: {expected_data[:10].hex()}...")
            print(f"   Got: {actual_data[:10].hex()}...")
            errors += 1
        
        if i % 2000 == 0:
            print(f" > Verified {i}/{NUM_PAGES}...", end="\r")

    verify_time = time.time() - start_time
    print(f" > COMPLETE: Verified in {verify_time:.2f}s")

    # --- STEP 3: PERSISTENCE CHECK (OPTIONAL) ---
    print(f"\n[PERSISTENCE] Saving all pages to disk (Simulated via Destroy)...")
    destroy_start = time.time()
    
    # Destroying the manager triggers the destructor loop -> save_page()
    lib.PM_Destroy(pm) 
    
    destroy_time = time.time() - destroy_start
    print(f" > Saved & Closed in {destroy_time:.2f}s")

    # Final Report
    print(f"\n{'='*30}")
    if errors == 0:
        print(f"SUCCESS: {NUM_PAGES} Pages written, verified, and saved.")
        print(f"No data corruption detected.")
    else:
        print(f"FAILURE: {errors} corruptions detected.")
    print(f"{'='*30}")

if __name__ == "__main__":
    run_stress_test()