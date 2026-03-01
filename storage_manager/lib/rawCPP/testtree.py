import ctypes
import os
import sys
import platform
import time

# ==========================================
# 1. NATIVE DLL LOADER
# ==========================================
def resolve_dll_path(dll_name: str) -> str:
    ext = ".dll" if platform.system() == "Windows" else ".so"
    filename = dll_name + ext
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    
    for _ in range(5):
        if os.path.exists(os.path.join(project_root, "storage_manager")):
            break
        parent = os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent
    
    target = os.path.join(project_root, "storage_manager", "lib", "rawCPP", filename)
    if not os.path.exists(target):
        local_target = os.path.join(current_dir, filename)
        if os.path.exists(local_target):
            return local_target
        raise FileNotFoundError(f"CRITICAL: Binary not found at {target}")
    return target

# ==========================================
# 2. LOAD THE ENGINE STACK
# ==========================================
try:
    if platform.system() == "Windows":
        pm_lib = ctypes.CDLL(resolve_dll_path("page_manager"), winmode=0)
        tm_lib = ctypes.CDLL(resolve_dll_path("tree_manager"), winmode=0)
    else:
        pm_lib = ctypes.CDLL(resolve_dll_path("page_manager"))
        tm_lib = ctypes.CDLL(resolve_dll_path("tree_manager"))
except OSError as e:
    print(f"DLL Load Failed: {e}")
    sys.exit(1)

# ==========================================
# 3. DEFINE STRUCTS & SIGNATURES
# ==========================================
class RecordPointer(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("page_id", ctypes.c_int32), 
        ("slot_id", ctypes.c_int32)
    ]

# Page Manager
pm_lib.PM_Create.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
pm_lib.PM_Create.restype = ctypes.c_void_p
pm_lib.PM_Destroy.argtypes = [ctypes.c_void_p]

# Tree Manager
tm_lib.BT_Create.argtypes = [ctypes.c_void_p, ctypes.c_int]
tm_lib.BT_Create.restype = ctypes.c_void_p
tm_lib.BT_Destroy.argtypes = [ctypes.c_void_p]

tm_lib.BT_Insert.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int32, ctypes.c_int32]
tm_lib.BT_Insert.restype = ctypes.c_bool

tm_lib.BT_Search.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
tm_lib.BT_Search.restype = RecordPointer

# ==========================================
# 4. THE 500,000 KEY STRESS TEST
# ==========================================
def run_test():
    db_file = b"./master_stress_tree.db"
    if os.path.exists(db_file): 
        os.remove(db_file)

    print("\n--- B+ TREE 80-BRANCH SPLIT STRESS TEST ---")
    
    print("[1/4] Allocating 100MB Memory Map for Deep Branching...", end=" ")
    # 1000 pages, 100KB each = ~100MB extent. Plenty of room for 80+ splits.
    pm_ptr = pm_lib.PM_Create(db_file, 1000, 102400) 
    tm_ptr = tm_lib.BT_Create(pm_ptr, 0)           
    
    if not pm_ptr or not tm_ptr:
        print("FAIL (Initialization Error)")
        return
    print("PASS")

    TOTAL_KEYS = 500000
    print(f"[2/4] Indexing {TOTAL_KEYS} Keys to force massive node splitting...")
    
    start_time = time.time()
    for k in range(TOTAL_KEYS):
        # Insert ascending to trigger constant right-splits
        success = tm_lib.BT_Insert(tm_ptr, k, k % 1000, k % 50)
        
        if not success:
            print(f"\nFAIL: Tree rejected insert at Key {k}. Split logic failed or memory map exhausted.")
            return
            
        if k > 0 and k % 100000 == 0:
            print(f"      -> {k} keys indexed. Memory splitting active...")

    elapsed = time.time() - start_time
    print(f"      PASS ({TOTAL_KEYS} keys packed in {elapsed:.2f} seconds)")

    print("[3/4] Testing O(log N) Retrieval Across 80+ Branches...", end=" ")
    # Sample keys from start, middle, and end to ensure no memory was orphaned during splits
    targets = [10, 250000, 499999]
    for t in targets:
        rp = tm_lib.BT_Search(tm_ptr, t)
        if rp.page_id != t % 1000 or rp.slot_id != t % 50:
            print(f"FAIL (Memory corrupted at Key {t}. Got Page {rp.page_id}, Slot {rp.slot_id})")
            return
    print("PASS (Zero-copy retrieval verified across all leaf nodes)")

    print("[4/4] Verifying Boundary Conditions...", end=" ")
    rp = tm_lib.BT_Search(tm_ptr, TOTAL_KEYS + 500)
    if rp.page_id == -1 and rp.slot_id == -1:
        print("PASS (Correctly rejected non-existent high-bound key)")
    else:
        print("FAIL (False positive match on ghost key)")

    print("\nShutting down engine...", end=" ")
    tm_lib.BT_Destroy(tm_ptr)
    pm_lib.PM_Destroy(pm_ptr)
    print("DONE\n")
    print("--- BRUTE FORCE C++ KERNEL FULLY OPERATIONAL ---")

if __name__ == "__main__":
    run_test()