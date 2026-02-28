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
    The Fortress around your C++ Engine.
    
    This class validates every piece of data coming from Python 
    before letting it touch the C++ memory.
    """

    def __init__(self, storage_path: str, max_pages: int = 1000):
        """
        Starts the storage engine.
        
        :param storage_path: The folder where your .bin files will live.
        :param max_pages: The maximum number of pages to keep in RAM before evicting.
        """
        if not isinstance(storage_path, str):
            raise TypeError(f"Storage Path must be a text string, you gave me a {type(storage_path)}")
        if not isinstance(max_pages, int) or max_pages <= 0:
            raise ValueError(f"Max Pages must be a positive integer, you gave me: {max_pages}")

        # ---------------------------------------------------------
        # A. FINDING THE DLL
        # ---------------------------------------------------------
        try:
            self._lib = load_dll("page_manager", search_dir="lib/rawCPP") 
        except Exception:
            try:
                self._lib = load_dll("page_manager", search_dir="rawCPP")
            except Exception as e:
                raise RuntimeError(f"CRITICAL: Could not find 'page_manager.dll'. Error Details: {e}")

        # ---------------------------------------------------------
        # B. DEFINING THE RULES (Signatures)
        # ---------------------------------------------------------
        self._lib.PM_Create.argtypes = [ctypes.c_char_p, ctypes.c_int] 
        self._lib.PM_Create.restype = ctypes.c_void_p

        self._lib.PM_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.PM_Destroy.restype = None

        self._lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
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
        path_bytes = storage_path.encode('utf-8')
        self._pm_ptr = self._lib.PM_Create(path_bytes, max_pages)

        if not self._pm_ptr:
            raise MemoryError("C++ failed to initialize. It returned a Null Pointer (0x0).")

    def create_page(self, page_id: int, size: int):
        """Allocates a new empty page in RAM."""
        self._validate_id(page_id)
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Size must be a positive integer. You gave me: {size}")
        
        self._lib.PM_CreatePage(self._pm_ptr, page_id, size)

    def load_page(self, page_id: int):
        """Reads a page file from disk into RAM."""
        self._validate_id(page_id)
        result = self._lib.PM_Load(self._pm_ptr, page_id)
        if result == 0:
            raise IOError(f"Failed to load page {page_id}. Does the file exist?")

    def unload_page(self, page_id: int):
        """Kicks a page out of RAM, saving to disk if modified."""
        self._validate_id(page_id)
        result = self._lib.PM_Unload(self._pm_ptr, page_id)
        if result == 0:
            raise ValueError(f"Failed to unload page {page_id}. It might not be in memory.")

    def flush_all(self):
        """Forces all dirty pages currently in RAM to be written to disk."""
        if self._pm_ptr:
            self._lib.PM_FlushAll(self._pm_ptr)

    def write(self, page_id: int, data: bytes, offset: int = 0):
        """Writes raw bytes into a specific page."""
        self._validate_id(page_id)
        
        if not isinstance(data, bytes):
            raise TypeError(f"I expect bytes (b'hello'), but you passed a {type(data).__name__}.")
        
        if not isinstance(offset, int) or offset < 0:
            raise ValueError(f"Offset cannot be negative. You gave: {offset}")

        data_len = len(data)
        if data_len == 0: return

        c_buffer = (ctypes.c_uint8 * data_len).from_buffer_copy(data)
        
        result = self._lib.PM_Write(self._pm_ptr, page_id, c_buffer, data_len, offset)
        if result == 0:
            raise RuntimeError(f"Failed to write to page {page_id}. Is it loaded?")

    def read(self, page_id: int) -> bytes:
        """Returns the contents of a page as a Python bytes object."""
        self._validate_id(page_id)
        
        ptr = self._lib.PM_GetData(self._pm_ptr, page_id)
        
        if not ptr:
            raise RuntimeError(f"Page {page_id} is not loaded in memory. Call load_page() first.")
        
        size = self._lib.PM_GetSize(self._pm_ptr, page_id)
        return ctypes.string_at(ptr, size)

    def get_size(self, page_id: int) -> int:
        """Returns the size of the page in bytes."""
        self._validate_id(page_id)
        return self._lib.PM_GetSize(self._pm_ptr, page_id)

    def destroy(self):
        """Manual Shutdown. Forces C++ to save dirty pages and free memory."""
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
    import shutil

    TEST_DB = "./test_db_safe"
    if os.path.exists(TEST_DB):
        try: shutil.rmtree(TEST_DB)
        except: pass 
    os.makedirs(TEST_DB, exist_ok=True)

    print(f"\n--- STARTING SAFE WRAPPER TESTS ---")
    print(f"Target DB: {os.path.abspath(TEST_DB)}")

    try:
        print("[1/6] Initializing Manager...", end=" ")
        pm = PageManager(TEST_DB)
        print("PASS")

        print("[2/6] Creating Page 1 (1KB)...", end=" ")
        pm.create_page(1, 1024)
        print("PASS")

        print("[3/6] Writing Payload...", end=" ")
        payload = b"Use the Force, Luke."
        pm.write(1, payload)
        print("PASS")

        print("[4/6] Verifying Data in RAM...", end=" ")
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

        print("[6/6] Testing Disk Persistence...", end=" ")
        pm.destroy() 
        
        if os.path.exists(os.path.join(TEST_DB, "page_1.bin")):
            print("PASS (File found on disk)")
        else:
            print("FAIL (File missing)")

        print("\n--- ALL SYSTEMS GO ---")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")