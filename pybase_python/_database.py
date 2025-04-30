import random
import string
import os
import pickle
import numpy as np
import time
import threading
import queue
from crypter import encrypt, decrypt
import multiprocessing


class PreExistingTableException(Exception):
    def __init__(self):
        super.__init__("The table specefied alredy exists in the current database")

class PreExistingFieldException(Exception):
    def __init__(self):
        super().__init__("Field alredy exists")

class NonExistantTableException(Exception):
    def __init__(self):
        super().__init__("Warning: the table does not exist")


class Database():
    def __init__(self, database_name, encryption_level=0):
        self.name=database_name
        start_time = time.time()
        self.database_name = database_name
        self.schema_file = f"database/{database_name}.pbs"
        self.db_file = f"database/{database_name}.pbf"
        self.encryption_level = encryption_level
        if not os.path.exists("database"):
            os.makedirs("database")
        
        if os.path.exists(self.schema_file):
            with open(self.schema_file, "rb") as f:
                self.schema = pickle.load(f)
        else:
            self.schema = {'tables': {}, '0lkjKo09': self.generate_passkey()}
            self.save_schema()
        
        if not os.path.exists(self.db_file):
            with open(self.db_file, "wb") as f:
                pickle.dump({}, f)
        print(f"Database loaded in {time.time() - start_time:.6f} seconds")
    
    def generate_passkey(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=self.encryption_level))
    
    def save_schema(self):
        with open(self.schema_file, "wb") as f:
            pickle.dump(self.schema, f)
    
    def add_table(self, table_name, columns, primary_key, foreign_keys=None):
        start_time = time.time()
        if table_name in self.schema['tables']:
            raise ValueError(f"Table '{table_name}' already exists in the schema.")
        
        self.schema['tables'][table_name] = {
            'columns': {col: [] for col in columns},
            'primary_key': primary_key,
            'foreign_keys': foreign_keys or {},
        }
        self.save_schema()
        print(f"Table '{table_name}' added in {time.time() - start_time:.6f} seconds")
    
    def remove_table(self, table_name):
        start_time = time.time()
        if table_name in self.schema['tables']:
            del self.schema['tables'][table_name]
            self.save_schema()
        else:
            raise NonExistantTableException()
        print(f"Table '{table_name}' removed in {time.time() - start_time:.6f} seconds")
    
    def add_field(self, table_name, field_name):
        start_time = time.time()
        if table_name in self.schema['tables']:
            if field_name not in self.schema['tables'][table_name]['columns']:
                self.schema['tables'][table_name]['columns'][field_name] = []
                self.save_schema()
            else:
                raise ValueError(f"Column '{field_name}' already exists in table '{table_name}'.")
        else:
            raise NonExistantTableException()
        print(f"Column '{field_name}' added in {time.time() - start_time:.6f} seconds")
    
    def get_table_info(self, table_name):
        return self.schema.get('tables', {}).get(table_name)
    
    def get_passkey(self):
        return self.schema['0lkjKo09']

Database("test_db")