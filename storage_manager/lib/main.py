import ctypes
import os

# 1. Load the DLL
# Use os.path.abspath to ensure Python finds it regardless of where you run the script from
dll_path = os.path.abspath("./example_dll.dll")
my_dll = ctypes.CDLL(dll_path)

# 2. Configure function signatures (Best Practice)
# This tells Python what data types the C functions expect and return.
# If you skip this, Python guesses, which can lead to crashes with non-integer data.

# int math_add(int a, int b);
my_dll.math_add.argtypes = [ctypes.c_int, ctypes.c_int]
my_dll.math_add.restype = ctypes.c_int

# void print_message(const char* msg);
# c_char_p handles standard ASCII/UTF-8 byte strings
my_dll.print_message.argtypes = [ctypes.c_char_p]
my_dll.print_message.restype = None

# 3. Call the functions
print("--- Python Client Starting ---")

# Calling math_add
result = my_dll.math_add(10, 20)
print(f"Python: 10 + 20 = {result}")

# Calling print_message
# IMPORTANT: Python 3 strings are Unicode. C wants raw bytes.
# You must use .encode('utf-8') to convert the string before passing it.
msg = "Hello from Python!".encode('utf-8')
my_dll.print_message(msg)

print("--- Python Client Finished ---")