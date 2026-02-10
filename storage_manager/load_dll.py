import ctypes
import os
import platform
import sys

class DLLNotFoundError(FileNotFoundError):
    """Custom exception raised when the DLL cannot be located."""
    pass

def load_dll(dll_name: str, lib_folder: str = "lib") -> ctypes.CDLL:
    """
    Searches for and loads a DLL from a specified folder relative to this script.
    
    Args:
        dll_name (str): The name of the library (e.g., "page" or "page.dll").
        lib_folder (str): The folder name where DLLs are stored (default: "lib").
    
    Returns:
        ctypes.CDLL: The loaded library object.
    
    Raises:
        DLLNotFoundError: If the file does not exist.
        OSError: If the file exists but cannot be loaded (e.g., missing dependencies).
    """
    
    # 1. Determine the OS-specific extension
    system = platform.system()
    if system == "Windows":
        extension = ".dll"
    elif system == "Linux":
        extension = ".so"
    elif system == "Darwin": # MacOS
        extension = ".dylib"
    else:
        raise OSError(f"Unsupported operating system: {system}")

    # 2. Ensure dll_name has the correct extension
    if not dll_name.endswith(extension):
        dll_name += extension

    # 3. Resolve the absolute path
    # We look for the folder relative to *this script's location*
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct potential paths (Current dir -> lib -> dll)
    # We verify if the user provided a full path or just a folder name
    if os.path.isabs(lib_folder):
        dll_path = os.path.join(lib_folder, dll_name)
    else:
        dll_path = os.path.join(current_dir, lib_folder, dll_name)

    # 4. Check if file exists
    if not os.path.exists(dll_path):
        # Optional: Try looking one directory up if we are inside a subdir like 'src' or 'tests'
        parent_path = os.path.join(os.path.dirname(current_dir), lib_folder, dll_name)
        if os.path.exists(parent_path):
            dll_path = parent_path
        else:
            raise DLLNotFoundError(
                f"DLL '{dll_name}' not found.\n"
                f"Searched in: {dll_path}\n"
                f"And parent:  {parent_path}"
            )

    # 5. Load the DLL
    print(f"Loading DLL from: {dll_path}")
    
    try:
        # winmode=0 is REQUIRED for Python 3.8+ on Windows to find dependencies
        if system == "Windows":
            return ctypes.CDLL(dll_path, winmode=0)
        else:
            return ctypes.CDLL(dll_path)
    except OSError as e:
        raise OSError(
            f"Found DLL at '{dll_path}' but failed to load it.\n"
            f"Error: {e}\n"
            "Tip: Ensure you compiled with '-static' or have all dependency DLLs in the same folder."
        )

# --- Usage Example ---
if __name__ == "__main__":
    try:
        # Assuming your structure is: project/lib/page.dll
        # And this script is running from project/
        
        # You can pass the folder name explicitly
        my_lib = load_dll("page", lib_folder="rawCPP") 
        
        print("Library loaded successfully!")
        
        # Setup signatures
        my_lib.PM_Create.restype = ctypes.c_void_p
        # ... rest of your setup ...
        
    except DLLNotFoundError as e:
        print(f"CRITICAL: {e}")
    except Exception as e:
        print(f"ERROR: {e}")