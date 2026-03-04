import ctypes
import os
import sys
import platform

# ==========================================
# 1. CUSTOM ENGINE EXCEPTIONS
# ==========================================
class PageError(Exception):
    """Base exception for the Page Manager."""
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

    # Pointing strictly at the 'lib' folder
    target_path = os.path.join(project_root, "StorageManager", "lib", filename)
    
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"CRITICAL: Binary not found at {target_path}")
        
    return target_path

# ==========================================
# 3. THE PAGE MANAGER WRAPPER
# ==========================================
class PageManager:
    """
    The Python Bodyguard for the Memory-Mapped OS Pages.
    Handles the raw byte transportation between the disk and the C++ kernel.
    """
    def __init__(self, db_path: str, max_pages: int = 10000, page_size: int = 102400):
        dll_path = resolve_dll_path("page_manager")
        try:
            if platform.system() == "Windows":
                self._lib = ctypes.CDLL(dll_path, winmode=0)
            else:
                self._lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise PageError(f"Failed to load native library {dll_path}: {e}")

        # Define C++ Signatures
        self._lib.PM_Create.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        self._lib.PM_Create.restype = ctypes.c_void_p

        self._lib.PM_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.PM_Destroy.restype = None

        self._lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_CreatePage.restype = ctypes.c_bool

        self._lib.PM_ReadPage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8)]
        self._lib.PM_ReadPage.restype = ctypes.c_bool

        self._lib.PM_WritePage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8)]
        self._lib.PM_WritePage.restype = ctypes.c_bool

        self._lib.PM_FlushAll.argtypes = [ctypes.c_void_p]
        self._lib.PM_FlushAll.restype = None

        self.page_size = page_size
        
        # Ignite the C++ Core
        path_bytes = db_path.encode('utf-8')
        self._pm_ptr = self._lib.PM_Create(path_bytes, max_pages, page_size)
        
        if not self._pm_ptr:
            raise PageError("C++ failed to initialize the Page Manager.")

    def create_page(self, page_id: int) -> bool:
        """Instructs the C++ kernel to allocate a new slotted page."""
        return self._lib.PM_CreatePage(self._pm_ptr, page_id)

    def read_page(self, page_id: int) -> bytearray:
        """Pulls a page out of the C++ memory map into Python."""
        buffer = (ctypes.c_uint8 * self.page_size)()
        success = self._lib.PM_ReadPage(self._pm_ptr, page_id, buffer)
        if not success:
            raise PageError(f"Failed to read page {page_id}. It may not exist.")
        return bytearray(buffer)

    def write_page(self, page_id: int, data: bytes) -> bool:
        """Pushes raw bytes from Python down into the C++ memory map."""
        if len(data) != self.page_size:
            raise ValueError(f"Data size ({len(data)}) must exactly match page size ({self.page_size}).")
            
        c_buffer = (ctypes.c_uint8 * self.page_size).from_buffer_copy(data)
        success = self._lib.PM_WritePage(self._pm_ptr, page_id, c_buffer)
        if not success:
            raise PageError(f"Failed to write to page {page_id}.")
        return True

    def flush_all(self):
        """Forces the OS to sync all memory-mapped changes to the physical disk."""
        self._lib.PM_FlushAll(self._pm_ptr)

    def destroy(self):
        if hasattr(self, '_pm_ptr') and self._pm_ptr:
            self._lib.PM_Destroy(self._pm_ptr)
            self._pm_ptr = None

    def __del__(self):
        self.destroy()