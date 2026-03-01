import ctypes
import os
import sys
import platform

# ==========================================
# 1. CUSTOM ENGINE EXCEPTIONS
# ==========================================
class StorageEngineError(Exception):
    """Base exception for the storage engine."""
    pass

class MemoryMapError(StorageEngineError):
    """Raised when the OS fails to map or allocate memory."""
    pass

class PageFullError(StorageEngineError):
    """Raised when a slotted page does not have enough free space for a record."""
    pass

class RecordNotFoundError(StorageEngineError):
    """Raised when attempting to access a slot that is empty, deleted, or out of bounds."""
    pass

# ==========================================
# 2. NATIVE DLL LOADER
# ==========================================
def resolve_dll_path(dll_name: str) -> str:
    """Dynamically finds the compiled binary in the /lib/rawCPP folder."""
    ext = ".dll" if platform.system() == "Windows" else ".so"
    filename = dll_name + ext

    # Start at current file's directory and walk up looking for 'storage_manager'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    
    for _ in range(5):
        if os.path.exists(os.path.join(project_root, "storage_manager")):
            break
        parent = os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent

    target_path = os.path.join(project_root, "storage_manager", "lib", "rawCPP", filename)
    
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

        # Load the DLL natively
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

        # Initialize
        self._rm_ptr = self._lib.RM_Create(self.pm._pm_ptr)
        if not self._rm_ptr:
            raise MemoryMapError("C++ failed to initialize the Record Manager.")

    def insert(self, page_id: int, data: bytes) -> int:
        """Packs a byte payload into the slotted page. Returns the assigned slot_id."""
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
        """Retrieves a record via zero-copy C++ pointer extraction."""
        self._validate_ids(page_id, slot_id)
        
        out_size = ctypes.c_uint32(0)
        ptr = self._lib.RM_GetRecord(self._rm_ptr, page_id, slot_id, ctypes.byref(out_size))
        
        if not ptr:
            raise RecordNotFoundError(f"Slot {slot_id} on Page {page_id} is empty or deleted.")
        
        return ctypes.string_at(ptr, out_size.value)

    def delete(self, page_id: int, slot_id: int) -> bool:
        """Tombstones a slot, marking its space as recyclable."""
        self._validate_ids(page_id, slot_id)
        success = self._lib.RM_DeleteRecord(self._rm_ptr, page_id, slot_id)
        if not success:
            raise RecordNotFoundError(f"Cannot delete. Slot {slot_id} on Page {page_id} is already empty.")
        return True

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