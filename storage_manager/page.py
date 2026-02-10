import ctypes
import os
import sys

# ==========================================
# 1. SMART IMPORT SETUP
# ==========================================
# This block handles the "Import Nightmare". 
# It ensures this file works whether you run it directly (python page.py)
# OR import it as a module (from storage_manager.lib.page import ...)
try:
    # Attempt 1: The "Proper" Python Package way
    from ..dll_loader import load_dll
except (ImportError, ValueError):
    # Attempt 2: The "Hacker" way (if running script directly)
    # We manually add the parent folder to the system path so we can find dll_loader
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from dll_loader import load_dll

class PageManager:
    """
    The Fortress around your C++ Engine.
    
    This class acts as a bodyguard. It validates every piece of data coming from
    Python (IDs, bytes, sizes) before letting it touch the C++ memory.
    
    If Python sends garbage, this class stops it. If C++ crashes, it's usually
    because this class let something bad through.
    """

    def __init__(self, storage_path: str):
        """
        Starts the storage engine.
        
        :param storage_path: The folder where your .bin files will live.
        """
        if not isinstance(storage_path, str):
            raise TypeError(f"Storage Path must be a text string, you gave me a {type(storage_path)}")

        # ---------------------------------------------------------
        # A. FINDING THE DLL (The tricky part)
        # ---------------------------------------------------------
        # The DLL is usually in 'lib/rawCPP', but depending on where you run
        # the script from, Python gets confused. We check two likely spots.
        
        try:
            # Option 1: We are running from the project root.
            # Look in storage_manager/lib/rawCPP
            self._lib = load_dll("page", search_dir="lib/rawCPP") 
        except Exception:
            try:
                # Option 2: We are running from inside the 'lib' folder.
                # Look in ./rawCPP
                self._lib = load_dll("page", search_dir="rawCPP")
            except Exception as e:
                # Give up and show a helpful error
                raise RuntimeError(f"CRITICAL: Could not find 'page.dll'. I looked in 'lib/rawCPP' and 'rawCPP'.\nError Details: {e}")

        # ---------------------------------------------------------
        # B. DEFINING THE RULES (Signatures)
        # ---------------------------------------------------------
        # C++ is strict. It needs to know EXACTLY what data types to expect.
        # If we send a Python Integer (which is an Object) to a C++ int slot,
        # the program will explode. We define the mapping here.
        
        # void* PM_Create(const char* path)
        self._lib.PM_Create.argtypes = [ctypes.c_char_p] # Expects bytes
        self._lib.PM_Create.restype = ctypes.c_void_p    # Returns a pointer address

        # void PM_Destroy(void* pm)
        self._lib.PM_Destroy.argtypes = [ctypes.c_void_p]
        self._lib.PM_Destroy.restype = None

        # void PM_CreatePage(void* pm, int id, int size)
        self._lib.PM_CreatePage.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self._lib.PM_CreatePage.restype = None

        # void PM_Load(void* pm, int id)
        self._lib.PM_Load.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_Load.restype = None

        # void PM_Unload(void* pm, int id)
        self._lib.PM_Unload.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_Unload.restype = None

        # void PM_Write(void* pm, int id, uint8_t* data, int size, int offset)
        self._lib.PM_Write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int]
        self._lib.PM_Write.restype = None

        # uint8_t* PM_GetData(void* pm, int id)
        self._lib.PM_GetData.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_GetData.restype = ctypes.POINTER(ctypes.c_uint8)

        # int PM_GetSize(void* pm, int id)
        self._lib.PM_GetSize.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.PM_GetSize.restype = ctypes.c_int

        # ---------------------------------------------------------
        # C. IGNITION
        # ---------------------------------------------------------
        # C++ strings must be bytes (UTF-8 encoded).
        path_bytes = storage_path.encode('utf-8')
        
        # Ask C++ to create the object and give us the memory address (pointer).
        # We store this pointer in self._pm_ptr and pass it back to C++ for every command.
        self._pm_ptr = self._lib.PM_Create(path_bytes)

        if not self._pm_ptr:
            raise MemoryError("C++ failed to initialize. It returned a Null Pointer (0x0).")

    def create_page(self, page_id: int, size: int):
        """
        Allocates a new empty page in RAM.
        """
        self._validate_id(page_id)
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Size must be a positive integer. You gave me: {size}")
        
        self._lib.PM_CreatePage(self._pm_ptr, page_id, size)

    def load_page(self, page_id: int):
        """
        Reads a page file from disk (page_X.bin) into RAM.
        """
        self._validate_id(page_id)
        self._lib.PM_Load(self._pm_ptr, page_id)

    def unload_page(self, page_id: int):
        """
        Kicks a page out of RAM. 
        If it was modified, it automatically saves to disk first.
        """
        self._validate_id(page_id)
        self._lib.PM_Unload(self._pm_ptr, page_id)

    def write(self, page_id: int, data: bytes, offset: int = 0):
        """
        Writes raw bytes into a specific page.
        """
        self._validate_id(page_id)
        
        # Strict Type Check: We only accept bytes. No strings allowed.
        if not isinstance(data, bytes):
            raise TypeError(f"I expect bytes (b'hello'), but you passed a {type(data).__name__} ('hello').")
        
        if not isinstance(offset, int) or offset < 0:
            raise ValueError(f"Offset cannot be negative. You gave: {offset}")

        data_len = len(data)
        if data_len == 0: return # Nothing to write, lazy exit.

        # Convert Python Bytes -> C Byte Array
        c_buffer = (ctypes.c_uint8 * data_len).from_buffer_copy(data)
        
        self._lib.PM_Write(self._pm_ptr, page_id, c_buffer, data_len, offset)

    def read(self, page_id: int) -> bytes:
        """
        Returns the contents of a page as a Python bytes object.
        """
        self._validate_id(page_id)
        
        # 1. Get the memory address of the data
        ptr = self._lib.PM_GetData(self._pm_ptr, page_id)
        
        # 2. Safety Check: If address is 0 (NULL), the page isn't loaded.
        if not ptr:
            raise RuntimeError(f"Page {page_id} is not loaded in memory. Did you forget to call load_page()?")
        
        # 3. Get the size so we know how much to read
        size = self._lib.PM_GetSize(self._pm_ptr, page_id)
        
        # 4. Copy data from C++ RAM to Python RAM
        return ctypes.string_at(ptr, size)

    def get_size(self, page_id: int) -> int:
        """Returns the size of the page in bytes."""
        self._validate_id(page_id)
        return self._lib.PM_GetSize(self._pm_ptr, page_id)

    def destroy(self):
        """
        Manual Shutdown.
        Forces C++ to save all dirty pages and free memory immediately.
        """
        if self._pm_ptr:
            self._lib.PM_Destroy(self._pm_ptr)
            self._pm_ptr = None

    def _validate_id(self, page_id):
        """Internal helper to ensure IDs are valid numbers."""
        if not isinstance(page_id, int):
            raise TypeError(f"Page ID must be an integer (whole number).")
        if page_id < 0:
            raise ValueError("Page ID cannot be negative.")

    def __del__(self):
        """
        The Garbage Collector.
        If you forget to call destroy(), Python calls this automatically when 
        the object is deleted to prevent memory leaks.
        """
        if hasattr(self, '_pm_ptr') and self._pm_ptr:
            self._lib.PM_Destroy(self._pm_ptr)
            self._pm_ptr = None

# ==========================================
# TEST SUITE (Run this file directly to test)
# ==========================================
if __name__ == "__main__":
    import shutil
    import time

    # Setup a dummy folder for testing
    TEST_DB = "./test_db_safe"
    if os.path.exists(TEST_DB):
        try: shutil.rmtree(TEST_DB)
        except: pass # Ignore if file locked
    os.makedirs(TEST_DB, exist_ok=True)

    print(f"\n--- 🛡️  STARTING SAFE WRAPPER TESTS ---")
    print(f"Target DB: {os.path.abspath(TEST_DB)}")

    try:
        # 1. Init
        print("[1/6] Initializing Manager...", end=" ")
        pm = PageManager(TEST_DB)
        print("✅ PASS")

        # 2. Create
        print("[2/6] Creating Page 1 (1KB)...", end=" ")
        pm.create_page(1, 1024)
        print("✅ PASS")

        # 3. Write
        print("[3/6] Writing Payload...", end=" ")
        payload = b"Use the Force, Luke."
        pm.write(1, payload)
        print("✅ PASS")

        # 4. Read Verification
        print("[4/6] Verifying Data in RAM...", end=" ")
        data = pm.read(1)
        if data.startswith(payload):
            print(f"✅ PASS (Matched: '{payload.decode()}')")
        else:
            print(f"❌ FAIL (Mismatch!)")

        # 5. Type Safety Check (The Bodyguard Test)
        print("[5/6] Testing Safety Guardrails...", end=" ")
        try:
            pm.write(1, "I am a string, not bytes") # This should fail
            print("❌ FAIL (The guardrail failed!)")
        except TypeError:
            print("✅ PASS (Blocked invalid input)")

        # 6. Persistence
        print("[6/6] Testing Disk Persistence...", end=" ")
        pm.destroy() # Force save
        
        # Check if file exists
        if os.path.exists(os.path.join(TEST_DB, "page_1.bin")):
            print("✅ PASS (File found on disk)")
        else:
            print("❌ FAIL (File missing)")

        print("\n--- ALL SYSTEMS GO 🚀 ---")

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")