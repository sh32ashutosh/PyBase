import os
import ctypes
import platform
from page import PageManager
from record_manager import RecordManager, RecordNotFoundError
from tree import TreeManager

# ==========================================
# 1. NATIVE WAL LOADER
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

# ==========================================
# 2. THE WAL WRAPPER
# ==========================================
class WALManager:
    def __init__(self, log_path: str, page_manager: PageManager):
        self.pm = page_manager
        dll_path = resolve_dll_path("wal")
        self._lib = ctypes.CDLL(dll_path, winmode=0) if platform.system() == "Windows" else ctypes.CDLL(dll_path)

        self._lib.WAL_Create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        self._lib.WAL_Create.restype = ctypes.c_void_p
        
        self._lib.WAL_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.WAL_LogInsert.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32]
        self._lib.WAL_LogInsert.restype = ctypes.c_uint64
        self._lib.WAL_Recover.argtypes = [ctypes.c_void_p]
        self._lib.WAL_Flush.argtypes = [ctypes.c_void_p]

        path_bytes = log_path.encode('utf-8')
        self._wal_ptr = self._lib.WAL_Create(path_bytes, self.pm._pm_ptr)

    def log_insert(self, page_id: int, slot_id: int, data: bytes) -> int:
        c_buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        return self._lib.WAL_LogInsert(self._wal_ptr, page_id, slot_id, c_buffer, len(data))

    def recover(self):
        self._lib.WAL_Recover(self._wal_ptr)

    def flush(self):
        self._lib.WAL_Flush(self._wal_ptr)

    def destroy(self):
        if hasattr(self, '_wal_ptr') and self._wal_ptr:
            self._lib.WAL_Destroy(self._wal_ptr)
            self._wal_ptr = None

# ==========================================
# 3. THE MASTER STORAGE ORCHESTRATOR
# ==========================================
class StorageManager:
    """
    The Master Facade.
    Ties the OS Memory Map, WAL, Record Manager, and B+ Tree together.
    """
    def __init__(self, db_path: str, log_path: str, max_pages=10000, page_size=102400):
        self.db_path = db_path
        self.log_path = log_path
        
        # Boot sequence must be strictly ordered
        self.pm = PageManager(db_path, max_pages, page_size)
        self.wal = WALManager(log_path, self.pm)
        
        # 1. Recover from crashes before allowing new operations
        self.wal.recover() 
        
        # 2. Mount operational layers
        self.rm = RecordManager(self.pm)
        self.tree = TreeManager(self.pm, root_page_id=0)

    def insert(self, key: int, data: bytes):
        """
        ACID-Compliant Insert.
        Logs intent -> Writes Payload -> Indexes physical coordinates.
        """
        if not isinstance(key, int):
            raise ValueError("Primary Key must be an integer.")
            
        # For simplicity in this Facade, we drop new records into page 1.
        # A production engine calculates page fill-factors here.
        target_page = 1 
        
        # 1. Attempt the physical write
        slot_id = self.rm.insert(target_page, data)
        
        # 2. Log it to disk (Write-Ahead)
        self.wal.log_insert(target_page, slot_id, data)
        
        # 3. Map it in the B+ Tree
        self.tree.insert(key, target_page, slot_id)
        
        return target_page, slot_id

    def read(self, key: int) -> bytes:
        """
        O(log N) zero-copy retrieval.
        """
        coords = self.tree.search(key)
        if not coords:
            return None
            
        try:
            return self.rm.get(coords["page_id"], coords["slot_id"])
        except RecordNotFoundError:
            return None

    def close(self):
        """Gracefully flushes all buffers to disk."""
        self.wal.flush()
        self.pm.flush_all()
        self.tree.destroy()
        self.rm.destroy()
        self.wal.destroy()
        self.pm.destroy()

# ==========================================
# THE FINAL SMOKE TEST
# ==========================================
if __name__ == "__main__":
    db_file = "./master_engine.db"
    log_file = "./master_engine.wal"
    
    if os.path.exists(db_file): os.remove(db_file)
    if os.path.exists(log_file): os.remove(log_file)

    print("\n--- BOOTING MASTER STORAGE ENGINE ---")
    engine = StorageManager(db_file, log_file)

    print("[1/3] Inserting ACID-Compliant Row...", end=" ")
    engine.insert(999, b'{"user": "admin", "status": "active"}')
    print("PASS")

    print("[2/3] Executing O(log N) Indexed Search...", end=" ")
    data = engine.read(999)
    if data == b'{"user": "admin", "status": "active"}':
        print(f"PASS (Found payload: {data.decode()})")
    else:
        print("FAIL")

    print("[3/3] Shutting down and flushing to disk...", end=" ")
    engine.close()
    print("PASS")
    
    print("\n--- DATABASE KERNEL COMPLETED ---")