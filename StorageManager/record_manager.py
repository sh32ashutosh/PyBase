import ctypes
import os
import sys
import platform

# ==========================================
# 1. CUSTOM ENGINE EXCEPTIONS
# ==========================================
class StorageEngineError(Exception):
    pass

class MemoryMapError(StorageEngineError):
    pass

class PageFullError(StorageEngineError):
    pass

class RecordNotFoundError(StorageEngineError):
    pass

# ==========================================
# 2. NATIVE DLL LOADER
# ==========================================
def resolve_dll_path(dll_name: str) -> str:
    ext = ".dll" if platform.system() == "Windows" else ".so"
    filename = dll_name + ext
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    
    for _ in range(5):
        if os.path.exists(os.path.join(project_root, "StorageManager")):
            break
        parent = os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent

    # THE FIX: Pointing strictly at the 'lib' folder, bypassing 'rawCPP'
    target_path = os.path.join(project_root, "StorageManager", "lib", filename)
    
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"CRITICAL: Binary not found at {target_path}")
        
    return target_path
# ==========================================
# 3. THE RECORD MANAGER WRAPPER
# ==========================================
class RecordManager:
    """
    The Python Bodyguard for the Slotted Page Record Manager.
    Enforces strict type safety, custom error throwing, and zero-copy retrieval.
    """

    def __init__(self, page_manager):
        if not hasattr(page_manager, '_pm_ptr') or not page_manager._pm_ptr:
            raise StorageEngineError("RecordManager requires an active, initialized PageManager instance.")

        self.pm = page_manager

        dll_path = resolve_dll_path("record_manager")
        try:
            if platform.system() == "Windows":
                self._lib = ctypes.CDLL(dll_path, winmode=0)
            else:
                self._lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise StorageEngineError(f"Failed to load native library {dll_path}: {e}")

        # Define C++ Signatures
        self._lib.RM_Create.argtypes = [ctypes.c_void_p]
        self._lib.RM_Create.restype = ctypes.c_void_p

        self._lib.RM_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.RM_Destroy.restype = None

        self._lib.RM_InsertRecord.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32
        ]
        self._lib.RM_InsertRecord.restype = ctypes.c_int

        self._lib.RM_GetRecord.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)
        ]
        self._lib.RM_GetRecord.restype = ctypes.POINTER(ctypes.c_uint8)

        self._lib.RM_DeleteRecord.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self._lib.RM_DeleteRecord.restype = ctypes.c_bool

        # NEW: Expose the slot count for SeqScans
        self._lib.RM_GetNumSlots.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.RM_GetNumSlots.restype = ctypes.c_int

        # Initialize
        self._rm_ptr = self._lib.RM_Create(self.pm._pm_ptr)
        if not self._rm_ptr:
            raise MemoryMapError("C++ failed to initialize the Record Manager.")

    def insert(self, page_id: int, data: bytes) -> int:
        self._validate_ids(page_id)
        if not isinstance(data, bytes):
            raise TypeError(f"Data must be raw bytes, got {type(data).__name__}.")
        
        data_len = len(data)
        if data_len == 0:
            raise ValueError("Cannot insert empty payload.")

        c_buffer = (ctypes.c_uint8 * data_len).from_buffer_copy(data)
        slot_id = self._lib.RM_InsertRecord(self._rm_ptr, page_id, c_buffer, data_len)
        
        if slot_id == -1:
            raise PageFullError(f"Page {page_id} is full. Cannot fit {data_len} bytes.")
            
        return slot_id

    def get(self, page_id: int, slot_id: int) -> bytes:
        self._validate_ids(page_id, slot_id)
        
        out_size = ctypes.c_uint32(0)
        ptr = self._lib.RM_GetRecord(self._rm_ptr, page_id, slot_id, ctypes.byref(out_size))
        
        if not ptr:
            raise RecordNotFoundError(f"Slot {slot_id} on Page {page_id} is empty or deleted.")
        
        return ctypes.string_at(ptr, out_size.value)

    def delete(self, page_id: int, slot_id: int) -> bool:
        self._validate_ids(page_id, slot_id)
        success = self._lib.RM_DeleteRecord(self._rm_ptr, page_id, slot_id)
        if not success:
            raise RecordNotFoundError(f"Cannot delete. Slot {slot_id} on Page {page_id} is already empty.")
        return True

    def scan_page(self, page_id: int):
        """
        Sequential Scan Generator.
        Yields (slot_id, bytes) for every valid record on the page.
        Skips deleted tombstones automatically.
        """
        self._validate_ids(page_id)
        num_slots = self._lib.RM_GetNumSlots(self._rm_ptr, page_id)
        
        for slot_id in range(num_slots):
            try:
                record = self.get(page_id, slot_id)
                yield slot_id, record
            except RecordNotFoundError:
                # Skip tombstoned records
                continue

    def destroy(self):
        if self._rm_ptr:
            self._lib.RM_Destroy(self._rm_ptr)
            self._rm_ptr = None

    def _validate_ids(self, page_id, slot_id=0):
        if not isinstance(page_id, int) or page_id < 0:
            raise ValueError("Page ID must be a non-negative integer.")
        if not isinstance(slot_id, int) or slot_id < 0:
            raise ValueError("Slot ID must be a non-negative integer.")

    def __del__(self):
        if hasattr(self, '_rm_ptr') and self._rm_ptr:
            self._lib.RM_Destroy(self._rm_ptr)
            self._rm_ptr = None

# ==========================================
# TEST SUITE
# ==========================================
if __name__ == "__main__":
    from page import PageManager
    
    TEST_DB_FILE = "./master_test_seqscan.db"
    if os.path.exists(TEST_DB_FILE):
        try: os.remove(TEST_DB_FILE)
        except: pass 

    print("\n--- STARTING SEQUENTIAL SCANNER TESTS ---")
    try:
        pm = PageManager(TEST_DB_FILE, max_pages=10, page_size=102400)
        rm = RecordManager(pm)
        
        PAGE_ID = 0
        pm.create_page(PAGE_ID)

        print("[1/3] Packing target page with data...", end=" ")
        s1 = rm.insert(PAGE_ID, b"Record A - Valid")
        s2 = rm.insert(PAGE_ID, b"Record B - Target for Deletion")
        s3 = rm.insert(PAGE_ID, b"Record C - Valid")
        print("PASS")

        print("[2/3] Tombstoning middle record...", end=" ")
        rm.delete(PAGE_ID, s2)
        print("PASS")

        print("[3/3] Executing Sequential Scan Generator...")
        found_records = 0
        for slot_id, record_bytes in rm.scan_page(PAGE_ID):
            print(f"      -> Yielded Slot {slot_id}: {record_bytes.decode()}")
            found_records += 1
            
        if found_records == 2:
            print("PASS (Scanner successfully ignored the deleted tombstone)")
        else:
            print("FAIL (Scanner yielded incorrect number of records)")

        rm.destroy()
        pm.destroy()
        print("\n--- ALL SYSTEMS GO ---")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")