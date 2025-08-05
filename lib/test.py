import ctypes
import os

# Load the DLL (ensure correct path)
pdbx = ctypes.CDLL(os.path.abspath("pdbx.dll"))

# Function signatures
pdbx.create_pdbx.argtypes = [ctypes.c_char_p]
pdbx.create_pdbx.restype = ctypes.c_int

pdbx.add_entry.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
pdbx.add_entry.restype = ctypes.c_int

pdbx.read_entry.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
pdbx.read_entry.restype = ctypes.c_char_p

# Path to the test file
db_path = b"test.pdbx"

# Step 1: Create the DB file
result = pdbx.create_pdbx(db_path)
print("Create DB:", "Success" if result == 0 else "Failed")

# Step 2: Add some entries
pdbx.add_entry(db_path, b"name", b"USB")
pdbx.add_entry(db_path, b"role", b"Student")

# Step 3: Read entries
name = pdbx.read_entry(db_path, b"name")
role = pdbx.read_entry(db_path, b"role")

print("Read name:", name.decode() if name else "Not found")
print("Read role:", role.decode() if role else "Not found")
