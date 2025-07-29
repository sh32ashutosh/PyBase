# test_dll.py
import ctypes
import os

# Get the directory of the current script
script_dir = os.path.dirname(__file__)
dll_path = os.path.join(script_dir, 'mydll.dll')

try:
    # Load the DLL
    # Use WinDLL for functions with __stdcall calling convention (common for Windows API)
    # Use CDLL for functions with __cdecl calling convention (default for C/C++)
    # Since we didn't specify __stdcall in C++, __cdecl is the default.
    my_dll = ctypes.CDLL(dll_path)
    print(f"DLL loaded successfully from: {dll_path}")

    # 1. Calling add_integers
    # Define argument types (optional but good practice for clarity and error checking)
    my_dll.add_integers.argtypes = [ctypes.c_int, ctypes.c_int]
    # Define return type (optional, default is c_int)
    my_dll.add_integers.restype = ctypes.c_int

    result = my_dll.add_integers(10, 25)
    print(f"10 + 25 = {result}")

    # 2. Calling greet_name
    my_dll.greet_name.argtypes = [ctypes.c_char_p]
    my_dll.greet_name.restype = None # This function doesn't return anything

    name = "Python User"
    # c_char_p expects bytes, so encode the string
    my_dll.greet_name(name.encode('utf-8'))

    # 3. Calling multiply_array
    my_dll.multiply_array.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
    my_dll.multiply_array.restype = None

    # Create a Python list
    py_array = [1, 2, 3, 4, 5]
    array_size = len(py_array)

    # Convert Python list to a C array type
    C_INT_ARRAY = ctypes.c_int * array_size
    c_array = C_INT_ARRAY(*py_array)

    multiplier = 10
    print(f"Original array: {list(c_array)}")
    my_dll.multiply_array(c_array, array_size, multiplier)
    print(f"Modified array: {list(c_array)}")

except OSError as e:
    print(f"Error loading DLL or calling function: {e}")
    print("Make sure 'mydll.dll' is in the same directory as this script, or provide the full path.")
    print("Also, ensure you compiled it as 64-bit if your Python is 64-bit (recommended).")