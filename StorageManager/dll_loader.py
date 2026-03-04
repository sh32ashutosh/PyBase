import ctypes
import os
import platform

class DLLNotFoundError(FileNotFoundError):
    """Custom exception raised when the DLL cannot be located."""
    pass

def load_dll(lib_name: str, search_dir: str = ".") -> ctypes.CDLL:
    """
    Smart DLL Loader that searches multiple locations to find your C++ library.
    """
    
    # 1. Determine OS Extension
    system = platform.system()
    if system == "Windows":
        extension = ".dll"
    elif system == "Linux":
        extension = ".so"
    elif system == "Darwin":
        extension = ".dylib"
    else:
        raise OSError(f"Unsupported operating system: {system}")

    if not lib_name.endswith(extension):
        lib_name += extension

    # 2. Define the Search Strategy
    # We will look in these locations in order:
    current_loader_dir = os.path.dirname(os.path.abspath(__file__))
    
    possible_paths = []

    # Strategy A: Absolute Path (User knows best)
    if os.path.isabs(search_dir):
        possible_paths.append(os.path.join(search_dir, lib_name))
    else:
        # Strategy B: Relative to this loader script (Standard)
        # e.g. StorageManager/''/page.dll
        possible_paths.append(os.path.join(current_loader_dir, search_dir, lib_name))

        # Strategy C: Relative to 'lib' (Fixes your specific project structure)
        # e.g. StorageManager/lib/''/page.dll
        possible_paths.append(os.path.join(current_loader_dir, "lib", search_dir, lib_name))
        
        # Strategy D: Check direct subfolder in lib (Fallback)
        # e.g. StorageManager/lib/page.dll
        possible_paths.append(os.path.join(current_loader_dir, "lib", lib_name))

    # 3. Hunt for the file
    found_path = None
    checked_locations = []

    for path in possible_paths:
        norm_path = os.path.normpath(path)
        checked_locations.append(norm_path)
        if os.path.exists(norm_path):
            found_path = norm_path
            break

    # 4. Error Handling
    if not found_path:
        error_msg = f"Could not find library '{lib_name}'.\nSearched locations:\n"
        for loc in checked_locations:
            error_msg += f" - {loc}\n"
        raise DLLNotFoundError(error_msg)

    # 5. Load the DLL
    try:
        # winmode=0 is crucial for Windows Python 3.8+
        if system == "Windows":
            return ctypes.CDLL(found_path, winmode=0)
        else:
            return ctypes.CDLL(found_path)
    except OSError as e:
        raise OSError(
            f"Found DLL at '{found_path}' but failed to load it.\n"
            f"Error: {e}\n"
            "Tip: Ensure you compiled with '-static' or have dependencies in the same folder."
        )