import ctypes
import os
import sys
import platform

# ==========================================
# 1. CUSTOM ENGINE EXCEPTIONS
# ==========================================
class IndexEngineError(Exception):
    """Base exception for the B+ Tree Index engine."""
    pass

class IndexFullError(IndexEngineError):
    """Raised when a B+ Tree node cannot accept more keys (Needs Split)."""
    pass

# ==========================================
# 2. NATIVE DLL LOADER & STRUCTS
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

    target_path = os.path.join(project_root, "storage_manager", "lib", "rawCPP", filename)
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"CRITICAL: Binary not found at {target_path}")
    return target_path

class RecordPointer(ctypes.Structure):
    """Maps exactly to the C++ RecordPointer struct."""
    _pack_ = 1
    _fields_ = [
        ("page_id", ctypes.c_int32), 
        ("slot_id", ctypes.c_int32)
    ]

# ==========================================
# 3. THE B+ TREE WRAPPER
# ==========================================
class TreeManager:
    """
    The Python Bodyguard for the B+ Tree Index Manager.
    Maps 64-bit integer keys directly to physical Record Pointers in the OS map.
    """

    def __init__(self, page_manager, root_page_id: int = 0):
        if not hasattr(page_manager, '_pm_ptr') or not page_manager._pm_ptr:
            raise IndexEngineError("TreeManager requires an active PageManager instance.")

        self.pm = page_manager
        self.root_page_id = root_page_id

        # Load DLL
        dll_path = resolve_dll_path("tree_manager")
        try:
            if platform.system() == "Windows":
                self._lib = ctypes.CDLL(dll_path, winmode=0)
            else:
                self._lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise IndexEngineError(f"Failed to load native library {dll_path}: {e}")

        # Define Signatures
        self._lib.BT_Create.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.BT_Create.restype = ctypes.c_void_p

        self._lib.BT_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.BT_Destroy.restype = None

        self._lib.BT_Insert.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int32, ctypes.c_int32]
        self._lib.BT_Insert.restype = ctypes.c_bool

        self._lib.BT_Search.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self._lib.BT_Search.restype = RecordPointer

        # Ignite the C++ Core
        self._tm_ptr = self._lib.BT_Create(self.pm._pm_ptr, root_page_id)
        if not self._tm_ptr:
            raise IndexEngineError("C++ failed to initialize the B+ Tree Manager.")

    def insert(self, key: int, page_id: int, slot_id: int):
        """
        Inserts a Key -> Record mapping into the B+ Tree.
        """
        if not isinstance(key, int) or key < 0 or key > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("Key must be an unsigned 64-bit integer.")
        if not isinstance(page_id, int) or not isinstance(slot_id, int):
            raise ValueError("Page ID and Slot ID must be integers.")

        success = self._lib.BT_Insert(self._tm_ptr, key, page_id, slot_id)
        if not success:
            raise IndexFullError(f"Tree node is full. C++ Node Splitting required.")

    def search(self, key: int) -> dict:
        """
        Searches the B+ Tree for a key. 
        Returns a dict {'page_id': X, 'slot_id': Y} if found, or None if not found.
        """
        if not isinstance(key, int) or key < 0:
            raise ValueError("Key must be a positive integer.")

        rp = self._lib.BT_Search(self._tm_ptr, key)
        
        if rp.page_id == -1 and rp.slot_id == -1:
            return None # Key does not exist in the index
            
        return {"page_id": rp.page_id, "slot_id": rp.slot_id}

    def destroy(self):
        if hasattr(self, '_tm_ptr') and self._tm_ptr:
            self._lib.BT_Destroy(self._tm_ptr)
            self._tm_ptr = None

    def __del__(self):
        self.destroy()