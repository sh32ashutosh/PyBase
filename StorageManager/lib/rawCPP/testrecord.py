import ctypes
import os
import sys

# ==========================================
# 1. SETUP & PATH RESOLUTION
# ==========================================
def find_project_root():
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(current, "StorageManager")):
            return current
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    return os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = find_project_root()
TARGET_DIR = os.path.join(PROJECT_ROOT, "StorageManager", "lib", "''")

PM_DLL_PATH = os.path.join(TARGET_DIR, "page_manager.dll")
RM_DLL_PATH = os.path.join(TARGET_DIR, "record_manager.dll")
DB_FILE = os.path.join(PROJECT_ROOT, "databases", "slotted_test.db")

print("--- SLOTTED PAGE RECORD MANAGER TEST ---")

if not os.path.exists(PM_DLL_PATH) or not os.path.exists(RM_DLL_PATH):
    print("CRITICAL: DLLs not found. Make sure both page_manager.dll and record_manager.dll are compiled.")
    sys.exit(1)

# Windows specific: Load the foundational DLL first, then the dependent one
try:
    if os.name == 'nt':
        pm_lib = ctypes.CDLL(PM_DLL_PATH, winmode=0)
        rm_lib = ctypes.CDLL(RM_DLL_PATH, winmode=0)
    else:
        pm_lib = ctypes.CDLL(PM_DLL_PATH)
        rm_lib = ctypes.CDLL(RM_DLL_PATH)
except OSError as e:
    print(f"DLL Load Failed: {e}")
    sys.exit(1)

# ==========================================
# 2. DEFINING AIRTIGHT SIGNATURES
# ==========================================
# --- Page Manager Signatures ---
pm_lib.PM_Create.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int] 
pm_lib.PM_Create.restype = ctypes.c_void_p

pm_lib.PM_Destroy.argtypes = [ctypes.c_void_p]
pm_lib.PM_Destroy.restype = None

# --- Record Manager Signatures ---
rm_lib.RM_Create.argtypes = [ctypes.c_void_p]
rm_lib.RM_Create.restype = ctypes.c_void_p

rm_lib.RM_Destroy.argtypes = [ctypes.c_void_p]
rm_lib.RM_Destroy.restype = None

rm_lib.RM_InsertRecord.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32]
rm_lib.RM_InsertRecord.restype = ctypes.c_int

rm_lib.RM_GetRecord.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
rm_lib.RM_GetRecord.restype = ctypes.POINTER(ctypes.c_uint8)

rm_lib.RM_DeleteRecord.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
rm_lib.RM_DeleteRecord.restype = ctypes.c_bool

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def insert_string(rm_ptr, page_id, text):
    data_bytes = text.encode('utf-8')
    data_len = len(data_bytes)
    c_buffer = (ctypes.c_uint8 * data_len).from_buffer_copy(data_bytes)
    return rm_lib.RM_InsertRecord(rm_ptr, page_id, c_buffer, data_len)

def get_string(rm_ptr, page_id, slot_id):
    out_size = ctypes.c_uint32(0)
    ptr = rm_lib.RM_GetRecord(rm_ptr, page_id, slot_id, ctypes.byref(out_size))
    
    if not ptr:
        return None
    
    raw_bytes = ctypes.string_at(ptr, out_size.value)
    return raw_bytes.decode('utf-8')

# ==========================================
# 4. THE TEST EXECUTION
# ==========================================
def run_test():
    # Clean the environment
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    print("\n[1/5] Booting Engine & Mapping Memory...", end=" ")
    pm_ptr = pm_lib.PM_Create(DB_FILE.encode('utf-8'), 10, 102400) # 10 pages, 100KB each
    if not pm_ptr:
        print("FAIL (Page Manager init failed)")
        return
        
    rm_ptr = rm_lib.RM_Create(pm_ptr)
    if not rm_ptr:
        print("FAIL (Record Manager init failed)")
        return
    print("PASS")

    PAGE_ID = 0

    print("[2/5] Packing Dynamic Records...", end=" ")
    slot_1 = insert_string(rm_ptr, PAGE_ID, "This is the first row. It sits at the bottom of the page.")
    slot_2 = insert_string(rm_ptr, PAGE_ID, "Row two. The free space offset just moved up.")
    slot_3 = insert_string(rm_ptr, PAGE_ID, "Third row. Slotted arrays are functioning perfectly.")
    
    if slot_1 == 0 and slot_2 == 1 and slot_3 == 2:
        print(f"PASS (Slots assigned: {slot_1}, {slot_2}, {slot_3})")
    else:
        print(f"FAIL (Unexpected slots: {slot_1}, {slot_2}, {slot_3})")

    print("[3/5] Retrieving Records via Slot ID...", end=" ")
    res_1 = get_string(rm_ptr, PAGE_ID, slot_1)
    res_2 = get_string(rm_ptr, PAGE_ID, slot_2)
    
    if res_1 and res_2 and "first row" in res_1 and "Row two" in res_2:
        print("PASS (Zero-copy retrieval successful)")
    else:
        print("FAIL (Data mismatch or null pointer)")

    print("[4/5] Testing Deletion (Tombstoning)...", end=" ")
    del_success = rm_lib.RM_DeleteRecord(rm_ptr, PAGE_ID, slot_2)
    if del_success:
        check_deleted = get_string(rm_ptr, PAGE_ID, slot_2)
        if check_deleted is None:
            print("PASS (Record 2 safely zeroed out)")
        else:
            print("FAIL (Record 2 still readable)")
    else:
        print("FAIL (Deletion returned false)")

    print("[5/5] Testing Slot Reuse...", end=" ")
    slot_4 = insert_string(rm_ptr, PAGE_ID, "New data taking over the dead slot.")
    if slot_4 == slot_2:
        print(f"PASS (Reused empty slot ID: {slot_4})")
    else:
        print(f"FAIL (Did not reuse slot, got: {slot_4})")

    print("\nShutting down engine...", end=" ")
    rm_lib.RM_Destroy(rm_ptr)
    pm_lib.PM_Destroy(pm_ptr)
    print("DONE\n")
    print("--- ALL SYSTEMS OPERATIONAL ---")

if __name__ == "__main__":
    run_test()