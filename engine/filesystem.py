# /engine/filesystem.py — handles the creation of files and directories within the database

# Get parent directory


# Custom error for duplicate database
class DatabaseExistsError(Exception):
    def __init__(self):
        super().__init__("Database already exists")


# Utility to check if a folder exists
def _folder_exists(path: str) -> bool:
    from os.path import exists, isdir
    return exists(path) and isdir(path)

# Generate a key for our encryption
def generate_key_iv() -> tuple[bytes, bytes]:
    """
    Generate a secure random 256-bit AES key and 128-bit IV (CTR mode).
    :return: (key, iv)
    """
    import os
    key = os.urandom(32)  # 256 bits
    iv = os.urandom(16)   # 128 bits (block size of AES)
    return (key, iv)



# Creates the initial folder structure and metadata for a database
def _create_database(database_name: str, page_size=1024, compression=None, encryption=False):
    from os import mkdir
    from os.path import dirname, abspath, join
    from datetime import datetime
    import pickle

    # Get parent directory of current file
    current_dir = dirname(abspath(__file__))
    parent_dir = dirname(current_dir)

    # Absolute path to /data/<db_name>
    data_root = join(parent_dir, "data")
    db_path = join(data_root, database_name)

    # If the data directory does not exist create data directory and proceed else proceed without creating

    if not _folder_exists(data_root):
        mkdir(data_root)

    

    # Create base database structure
    mkdir(db_path)
    mkdir(join(db_path, ".meta"))
    mkdir(join(db_path, ".index"))
    mkdir(join(db_path, ".config"))
    mkdir(join(db_path, "media"))

    # Write metadata to binary file via pickle
    meta_data = {
        "name": database_name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "version": 0.1,
        "page_size": page_size,
        "encryption": encryption,
        "compression": compression,
        "path": db_path,
        "encryption_key_and_vector":generate_key_iv() 
    }

    meta_file = join(db_path, ".meta", "db.meta")
    with open(meta_file, "wb") as file:
        pickle.dump(meta_data, file)

    # Create empty lock file
    open(join(db_path, ".meta", "db.lock"), "w").close()
    print(f"Created database: {db_path}")


def insert_row(db_name: str, table_name: str, row_dict: dict, pk_field: str):
    from os.path import join
    import struct, pickle

    base_path = join("data", db_name, table_name)
    schema_path = join(base_path, "table.pdi")
    data_path = join(base_path, "table.page")
    index_path = join(base_path, "table.pdx")

    # Load schema
    fields = []
    record_size = 0
    with open(schema_path, "rb") as f:
        for line in f:
            name, offset, size = line.strip().split('|')
            fields.append((name, int(offset), int(size)))
            record_size += int(size)

    # Build binary row
    binary_row = bytearray(record_size)
    for field_name, offset, size in fields:
        val = row_dict.get(field_name, "")
        raw = str(val).encode()[:size].ljust(size, b'\x00')
        binary_row[offset:offset + size] = raw

    # Write to .page
    with open(data_path, "ab") as f:
        f.seek(0, 2)
        offset = f.tell()
        f.write(binary_row)

    # Update index
    try:
        with open(index_path, "rb") as f:
            index = pickle.load(f)
    except:
        index = {}

    primary_key = row_dict[pk_field]
    index[primary_key] = offset

    with open(index_path, "wb") as f:
        pickle.dump(index, f)

    print(f"[+] Inserted row with key '{primary_key}' at offset {offset}")
