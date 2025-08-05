# /engine/filesystem.py — handles the creation of files and directories within the database

# Custom error for duplicate database
class DatabaseExistsError(Exception):
    def __init__(self):
        super().__init__("Database already exists")


# Utility to check if a folder exists
def _folder_exists(path: str) -> bool:
    from os.path import exists, isdir
    return exists(path) and isdir(path)


# Creates the initial folder structure and metadata for a database
def create_database(database_name: str, page_size=1024, compression=None, encryption='None'):
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

    if not _folder_exists(data_root):
        mkdir(data_root)

    if _folder_exists(db_path):
        raise DatabaseExistsError()

    # Create base DB structure
    mkdir(db_path)
    mkdir(join(db_path, ".meta"))
    mkdir(join(db_path, ".index"))
    mkdir(join(db_path, ".config"))
    mkdir(join(db_path, "media"))

    # Write metadata to binary file using pickle
    meta_data = {
        "name": database_name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "version": 0.1,
        "page_size": page_size,
        "encryption": encryption,
        "compression": compression,
        "path": db_path
    }

    meta_file = join(db_path, ".meta", "db.meta")
    with open(meta_file, "wb") as file:
        pickle.dump(meta_data, file)

    # Create empty lock file
    open(join(db_path, ".meta", "db.lock"), "w").close()
    print(f"Created database: {db_path}")


# /engine/filesystem.py

def create_table(db_name: str, table_name: str, schema: dict):
    from os.path import join, exists
    from os import makedirs
    import pickle

    # === Define base path ===
    base_path = join("data", db_name, table_name)
    if exists(base_path):
        raise FileExistsError(f"Table '{table_name}' already exists in database '{db_name}'.")

    makedirs(base_path)

    # === 1. Create .pdi schema file ===
    pdi_path = join(base_path, "table.pdi")
    offset = 0
    with open(pdi_path, "w") as f:
        for field, (_, size) in schema.items():
            f.write(f"{field}|{offset}|{size}\n")
            offset += size

    # === 2. Create empty binary index .pdx ===
    pdx_path = join(base_path, "table.pdx")
    with open(pdx_path, "wb") as f:
        pickle.dump({}, f)

    # === 3. Create empty data page file ===
    page_path = join(base_path, "table.page")
    open(page_path, "wb").close()

    # === 4. Create table lock file ===
    lock_path = join(base_path, "table.lock")
    open(lock_path, "w").close()

    print(f"[+] Table '{table_name}' initialized in '{base_path}'")

