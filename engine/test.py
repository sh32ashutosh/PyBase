# docs/test.py

import os
from datastore import DataStore

# ---- Mock Backend mimicking filesystem.py ----
class MockFilesystemBackend:
    def __init__(self, base_path="data"):
        self.base_path = base_path

    def create_table_backend(self, table_name, schema):
        os.makedirs(f"{self.base_path}/testdb", exist_ok=True)
        # Simulate creating .pdi, .pdx, .page files
        for ext in ['.pdi', '.pdx', '.page']:
            open(f"{self.base_path}/testdb/{table_name}{ext}", 'wb').close()

    def insert_record(self, table_name, data):
        # Just log for now; no real I/O
        print(f"[insert_record] {table_name}: {data}")

    def read_all_records(self, table_name):
        return []

    def read_record_by_index(self, table_name, index):
        return {}

    def update_record(self, table_name, index, data):
        pass

    def delete_table_backend(self, table_name):
        pass

# Test execution section

# Define a basic schema
schema = {
    "id": {"offset": 0, "size": 4, "type": "int"},
    "name": {"offset": 4, "size": 20, "type": "str"}
}

backend = MockFilesystemBackend()
ds = DataStore(backend)

# Create table and insert
ds.create_table("users", "base", schema)
ds.insert("users", {"id": 1, "name": "Alice"})

# Check if expected files were created
base_path = "data/testdb"
required_files = [f"{base_path}/users.pdi", f"{base_path}/users.pdx", f"{base_path}/users.page"]

all_exist = all(os.path.isfile(f) for f in required_files)

if all_exist:
    print("✅ All files created successfully.")
else:
    print("❌ Missing files:")
    for f in required_files:
        if not os.path.isfile(f):
            print(f" - {f}")
