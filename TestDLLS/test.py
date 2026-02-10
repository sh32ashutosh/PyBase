import ctypes
import os

# --- 1. Load the DLL ---
dll_name = "calc.dll"
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dll_name)

try:
    my_lib = ctypes.CDLL(dll_path)
except OSError as e:
    print(f"Error loading DLL: {e}")
    print("Make sure 'calc.dll' is in the same directory.")
    exit(1)

print(f"Successfully loaded '{dll_name}'")


# --- 2. Define Function Prototypes (The "Menu") ---
# This tells ctypes what the functions look like.

# The "ticket" is a void pointer
CalcHandle = ctypes.c_void_p

# create(int, int) -> CalcHandle
my_lib.create.argtypes = [ctypes.c_int, ctypes.c_int]
my_lib.create.restype = CalcHandle

# destroy(CalcHandle) -> void
my_lib.destroy.argtypes = [CalcHandle]
my_lib.destroy.restype = None

# add_wrapper(CalcHandle) -> int
my_lib.add_wrapper.argtypes = [CalcHandle]
my_lib.add_wrapper.restype = ctypes.c_int

# sub_wrapper(CalcHandle) -> int
my_lib.sub_wrapper.argtypes = [CalcHandle]
my_lib.sub_wrapper.restype = ctypes.c_int


# --- 3. Use the DLL ---
# We use a 'try...finally' block to make sure we *always*
# call destroy(), even if an error happens.

my_calc = None  # This will hold our "ticket"
try:
    # 1. Create the C++ object
    num1 = 5000
    num2 = 32434
    print(f"\nCreating Calc object with {num1} and {num2}...")
    my_calc = my_lib.create(num1, num2)
    print(f"Got 'ticket' (handle): {my_calc}")

    # 2. Use the 'add' method
    result_add = my_lib.add_wrapper(my_calc)
    print(f"  Calling add_wrapper(): {result_add}")

    # 3. Use the 'sub' method
    result_sub = my_lib.sub_wrapper(my_calc)
    print(f"  Calling sub_wrapper(): {result_sub}")

finally:
    # 4. Destroy the C++ object
    # This is CRITICAL to prevent memory leaks.
    if my_calc:
        print("\nDestroying Calc object...")
        my_lib.destroy(my_calc)
        # You should see the "Calc object destroyed." message print here!

print("Test complete.")