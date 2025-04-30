import os
import ctypes
import multiprocessing
import time

DLL_NAME = "crypter.dll"
FILE_NAME = "process.txt"

def create_process_file():
    cpu_cores = os.cpu_count() or 4  # Default to 4 if detection fails
    num_files = max(1, cpu_cores - 2)  # Ensure at least one file is written

    with open(FILE_NAME, "w") as f:
        for i in range(num_files):
            f.write(f"tmp{i}.txt\n")

    print(f"Created {FILE_NAME} with {num_files} entries.")

def call_encrypt():
    """Calls encrypt() only when the first line disappears."""
    crypter = ctypes.CDLL(os.path.join(os.path.dirname(__file__), DLL_NAME))

    while True:
        if not os.path.exists(FILE_NAME) or os.path.getsize(FILE_NAME) == 0:
            print("No more names left. Exiting.")
            break  # Stop when the file is empty

        with open(FILE_NAME, "r") as f:
            first_line = f.readline().strip()

        if first_line:  # If there's a first line, wait until it's gone
            while True:
                time.sleep(0.1)  # Keep checking every 100ms
                with open(FILE_NAME, "r") as f:
                    new_first_line = f.readline().strip()
                if new_first_line != first_line:
                    break  # First line changed, proceed with encryption

        crypter.encrypt()

if __name__ == "__main__":
    create_process_file()
    
    num_workers = os.cpu_count() or 4  # Max out CPU usage
    processes = []

    for _ in range(num_workers):
        p = multiprocessing.Process(target=call_encrypt)
        p.start()
        processes.append(p)

    for p in processes:
        p.join()  # Wait for all processes to finish
