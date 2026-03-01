import ctypes
import os
import sys

# ==========================================
# 1. SMART IMPORT SETUP
# ==========================================
try:
    from ..dll_loader import load_dll
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from dll_loader import load_dll

class PageManager:
    """
    The Fortress around your OS-Native C++ Engine.
    
    This class validates every piece of data coming from Python 
    before letting it touch the kernel-mapped memory space.
    """

    def __init__(self, db_file_path: str, max_pages: int = 10000, page_size: int = 102400):
        """
        Starts the memory-mapped storage engine.
        
        :param db_file_path: The exact path to the master .db file.
        :param max_pages: The maximum number of pages this extent can hold.
        :param page_size: The fixed size of each page in bytes (e.g., 102400 for 100KB).
        """
        if not isinstance(db_file_path, str):
            raise TypeError(f"DB File Path must be a string, got {type(db_file_path)}")
        if not isinstance(max_pages, int) or max_pages <= 0:
            raise ValueError(f"Max Pages must be a positive integer, got: {max_pages}")
        if not isinstance(page_size, int) or page_size <= 0:
            raise ValueError(f"Page Size must be a positive integer, got: {page_size}")

        self.page_size = page_size

        # ---------------------------------------------------------
        # A. FINDING THE DLL/SO
        # ---------------------------------------------------------
        try:
            self._lib = load_dll("page_manager", search_dir="lib/rawCPP") 
        except Exception:
            try:
                self._lib = load_dll("page_manager", search_dir="rawCPP")
            except Exception as e:
                raise RuntimeError(f"CRITICAL: Could not find 'page_manager' binary. Error Details: {e}")

        # ---------------------------------------------------------
        # B. DEFINING THE RULES (Signatures)
        # ---------------------------------------------------------
        # void* PM_Create(const char* path, int max_pages, int page_size)
        self._lib.PM_Create.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int] 
        self._lib.PM_Create.restype = ctypes.c_void_p

        self._lib.PM_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.PM_Destroy.restype = None

        # void PM_CreatePage(void* pm, int id) -> Size is globally fixed now
        self._lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_CreatePage.restype = None

        self._lib.PM_Load.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_Load.restype = ctypes.c_int

        self._lib.PM_Unload.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_Unload.restype = ctypes.c_int

        self._lib.PM_FlushAll.argtypes = [ctypes.c_void_p]
        self._lib.PM_FlushAll.restype = None

        self._lib.PM_Write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int]
        self._lib.PM_Write.restype = ctypes.c_int

        self._lib.PM_GetData.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_GetData.restype = ctypes.POINTER(ctypes.c_uint8)

        self._lib.PM_GetSize.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_GetSize.restype = ctypes.c_int

        # ---------------------------------------------------------
        # C. IGNITION
        # ---------------------------------------------------------
        path_bytes = db_file_path.encode('utf-8')
        self._pm_ptr = self._lib.PM_Create(path_bytes, max_pages, page_size)

        if not self._pm_ptr:
            raise MemoryError("C++ failed to map OS memory. Check disk space or permissions.")

    def create_page(self, page_id: int):
        """Zeroes out a specific page block in the memory map."""
        self._validate_id(page_id)
        self._lib.PM_CreatePage(self._pm_ptr, page_id)

    def load_page(self, page_id: int):
        """Prepares a page (handled implicitly by OS page-faults now)."""
        self._validate_id(page_id)
        result = self._lib.PM_Load(self._pm_ptr, page_id)
        if result == 0:
            raise IOError(f"Failed to load page {page_id}.")

    def unload_page(self, page_id: int):
        """Forces the OS to flush this specific memory block to disk."""
        self._validate_id(page_id)
        result = self._lib.PM_Unload(self._pm_ptr, page_id)
        if result == 0:
            raise ValueError(f"Failed to unload page {page_id}.")

    def flush_all(self):
        """Forces the OS to synchronize the entire memory map to disk."""
        if self._pm_ptr:
            self._lib.PM_FlushAll(self._pm_ptr)

    def write(self, page_id: int, data: bytes, offset: int = 0):
        """Writes raw bytes directly into the OS memory map."""
        self._validate_id(page_id)
        
        if not isinstance(data, bytes):
            raise TypeError(f"I expect bytes (b'hello'), but you passed a {type(data).__name__}.")
        
        if not isinstance(offset, int) or offset < 0:
            raise ValueError(f"Offset cannot be negative. You gave: {offset}")

        data_len = len(data)
        if data_len == 0: return

        if offset + data_len > self.page_size:
            raise BufferError(f"Write exceeds page boundaries. Page size is {self.page_size}.")

        c_buffer = (ctypes.c_uint8 * data_len).from_buffer_copy(data)
        
        result = self._lib.PM_Write(self._pm_ptr, page_id, c_buffer, data_len, offset)
        if result == 0:
            raise RuntimeError(f"Failed to write to page {page_id}. Out of bounds or lock failed.")

    def read(self, page_id: int) -> bytes:
        """Returns the contents of a page from the memory map."""
        self._validate_id(page_id)
        
        ptr = self._lib.PM_GetData(self._pm_ptr, page_id)
        
        if not ptr:
            raise RuntimeError(f"Pointer mapping failed for page {page_id}.")
        
        size = self._lib.PM_GetSize(self._pm_ptr, page_id)
        return ctypes.string_at(ptr, size)

    def get_size(self, page_id: int) -> int:
        """Returns the fixed size of the extent page."""
        self._validate_id(page_id)
        return self._lib.PM_GetSize(self._pm_ptr, page_id)

    def destroy(self):
        """Unmaps the OS memory and closes file handles."""
        if self._pm_ptr:
            self._lib.PM_Destroy(self._pm_ptr)
            self._pm_ptr = None

    def _validate_id(self, page_id):
        if not isinstance(page_id, int):
            raise TypeError(f"Page ID must be an integer.")
        if page_id < 0:
            raise ValueError("Page ID cannot be negative.")

    def __del__(self):
        if hasattr(self, '_pm_ptr') and self._pm_ptr:
            self._lib.PM_Destroy(self._pm_ptr)
            self._pm_ptr = None

# ==========================================
# TEST SUITE
# ==========================================
if __name__ == "__main__":
    TEST_DB_FILE = "./master_test_extent.db"
    if os.path.exists(TEST_DB_FILE):
        try: os.remove(TEST_DB_FILE)
        except: pass 

    print(f"\n--- STARTING SAFE WRAPPER TESTS ---")
    print(f"Target DB: {os.path.abspath(TEST_DB_FILE)}")

    try:
        print("[1/6] Initializing Mapped Manager...", end=" ")
        # 10 pages, 1KB each
        pm = PageManager(TEST_DB_FILE, max_pages=10, page_size=1024)
        print("PASS")

        print("[2/6] Zeroing Page 1...", end=" ")
        pm.create_page(1)
        print("PASS")

        print("[3/6] Writing Payload...", end=" ")
        payload = b"Engine is mapped and lethal."
        pm.write(1, payload)
        print("PASS")

        print("[4/6] Verifying Data in Map...", end=" ")
        data = pm.read(1)
        if data.startswith(payload):
            print(f"PASS (Matched: '{payload.decode()}')")
        else:
            print(f"FAIL (Mismatch!)")

        print("[5/6] Testing Safety Guardrails...", end=" ")
        try:
            pm.write(1, "I am a string, not bytes") 
            print("FAIL (The guardrail failed!)")
        except TypeError:
            print("PASS (Blocked invalid input)")

        print("[6/6] Testing OS Unmap & Persistence...", end=" ")
        pm.destroy() 
        
        if os.path.exists(TEST_DB_FILE):
            actual_size = os.path.getsize(TEST_DB_FILE)
            expected_size = 10 * 1024
            if actual_size == expected_size:
                print(f"PASS (File found, exact size: {actual_size} bytes)")
            else:
                print(f"FAIL (File size {actual_size} != {expected_size})")
        else:
            print("FAIL (File missing)")

        print("\n--- ALL SYSTEMS GO ---")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")