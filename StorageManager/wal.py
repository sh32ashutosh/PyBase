import ctypes
import os
import sys
import platform

# ==========================================
# 1. CUSTOM ENGINE EXCEPTIONS
# ==========================================
class WALEngineError(Exception):
    """Base exception for the Write-Ahead Log engine."""
    pass

class WALInitializationError(WALEngineError):
    """Raised when the WAL DLL fails to load or ignite."""
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

    target_path = os.path.join(project_root, "StorageManager", "lib", filename)
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"CRITICAL: Binary not found at {target_path}")
        
    return target_path

# ==========================================
# 3. THE WAL WRAPPER
# ==========================================
class WALManager:
    """
    The Python Bodyguard for the Write-Ahead Log Manager.
    Ensures sequential disk logging for ACID compliance.
    """

    def __init__(self, log_path: str, page_manager):
        if not hasattr(page_manager, '_pm_ptr') or not page_manager._pm_ptr:
            raise WALEngineError("WALManager requires an active PageManager instance to perform crash recovery.")

        self.pm = page_manager
        
        dll_path = resolve_dll_path("wal")
        try:
            if platform.system() == "Windows":
                self._lib = ctypes.CDLL(dll_path, winmode=0)
            else:
                self._lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise WALInitializationError(f"Failed to load native library {dll_path}: {e}")

        # Define Signatures
        self._lib.WAL_Create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        self._lib.WAL_Create.restype = ctypes.c_void_p

        self._lib.WAL_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.WAL_Destroy.restype = None

        self._lib.WAL_LogInsert.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32]
        self._lib.WAL_LogInsert.restype = ctypes.c_uint64

        self._lib.WAL_LogDelete.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self._lib.WAL_LogDelete.restype = ctypes.c_uint64

        self._lib.WAL_LogPageAlloc.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.WAL_LogPageAlloc.restype = ctypes.c_uint64

        self._lib.WAL_Flush.argtypes = [ctypes.c_void_p]
        self._lib.WAL_Flush.restype = None

        self._lib.WAL_Recover.argtypes = [ctypes.c_void_p]
        self._lib.WAL_Recover.restype = None

        # Ignite the C++ Core
        path_bytes = log_path.encode('utf-8')
        self._wal_ptr = self._lib.WAL_Create(path_bytes, self.pm._pm_ptr)
        
        if not self._wal_ptr:
            raise WALInitializationError("C++ failed to initialize the WAL Manager.")

    def log_insert(self, page_id: int, slot_id: int, data: bytes) -> int:
        """Logs an intent to insert a record. Returns the Log Sequence Number (LSN)."""
        if not isinstance(data, bytes):
            raise TypeError("Data must be raw bytes.")
            
        c_buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        return self._lib.WAL_LogInsert(self._wal_ptr, page_id, slot_id, c_buffer, len(data))

    def log_delete(self, page_id: int, slot_id: int) -> int:
        """Logs an intent to tombstone a record. Returns the LSN."""
        return self._lib.WAL_LogDelete(self._wal_ptr, page_id, slot_id)

    def log_page_alloc(self, page_id: int) -> int:
        """Logs an intent to allocate a new page in the memory map. Returns the LSN."""
        return self._lib.WAL_LogPageAlloc(self._wal_ptr, page_id)

    def flush(self):
        """Forces the OS to sync the log file to physical disk."""
        self._lib.WAL_Flush(self._wal_ptr)

    def recover(self):
        """Replays the sequential log to rebuild the database after a crash."""
        self._lib.WAL_Recover(self._wal_ptr)

    def destroy(self):
        if hasattr(self, '_wal_ptr') and self._wal_ptr:
            self._lib.WAL_Destroy(self._wal_ptr)
            self._wal_ptr = None

    def __del__(self):
        self.destroy()

if __name__=="__main__":
    print("running")
    wal=WALManager()
    
