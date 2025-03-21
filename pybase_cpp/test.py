from cffi import FFI
import os

ffi = FFI()

# Define the C interface
ffi.cdef("""
    char* encrypt_text(const char* input);
    char* decrypt_text(const char* input);
    void free_memory(char* ptr);
""")

# Load the DLL
dll_path = './crypter.dll'  # Adjust the path as necessary
print(f"Trying to load DLL from: {os.path.abspath(dll_path)}")

try:
    my_dll = ffi.dlopen(dll_path)  # Adjust the path as necessary
except OSError as e:
    print(f"Failed to load DLL: {e}")
    exit(1)

# Example usage
plaintext = "Hello, World!"
encrypted = my_dll.encrypt_text(plaintext.encode('utf-8'))
print(f"Encrypted: {ffi.string(encrypted).decode('utf-8')}")

# Decrypt the text
decrypted = my_dll.decrypt_text(encrypted)
print(f"Decrypted: {ffi.string(decrypted).decode('utf-8')}")

# Free the allocated memory
my_dll.free_memory(encrypted)
my_dll.free_memory(decrypted)