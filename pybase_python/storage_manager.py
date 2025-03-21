import random
import string
import os
import pickle
import numpy as np
import time
from crypter import encrypt, decrypt

class NonExistantTableException(Exception):
    def __init__(self):
        super().__init__("Warning: the table does not exist")

class SchemaManager:
    def __init__(self, database_name, encryption_level=5):
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
        print(f"SchemaManager initialized in {time.time() - start_time:.6f} seconds")
    
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
    
    def add_column(self, table_name, column_name):
        start_time = time.time()
        if table_name in self.schema['tables']:
            if column_name not in self.schema['tables'][table_name]['columns']:
                self.schema['tables'][table_name]['columns'][column_name] = []
                self.save_schema()
            else:
                raise ValueError(f"Column '{column_name}' already exists in table '{table_name}'.")
        else:
            raise NonExistantTableException()
        print(f"Column '{column_name}' added in {time.time() - start_time:.6f} seconds")
    
    def get_table_info(self, table_name):
        return self.schema.get('tables', {}).get(table_name)
    
    def get_passkey(self):
        return self.schema['0lkjKo09']

class DatabaseManager:
    def __init__(self, schema_manager):
        start_time = time.time()
        self.schema_manager = schema_manager
        self.db_file = schema_manager.db_file
        
        with open(self.db_file, "rb") as f:
            self.database = pickle.load(f)
        print(f"DatabaseManager initialized in {time.time() - start_time:.6f} seconds")
    
    def save_database(self):
        start_time = time.time()
        with open(self.db_file, "wb") as f:
            pickle.dump(self.database, f)
        print(f"Database saved in {time.time() - start_time:.6f} seconds")
    
    def insert_data(self, table_name, data):
        start_time = time.time()
        table_info = self.schema_manager.get_table_info(table_name)
        if not table_info:
            raise NonExistantTableException()
        
        if table_info['primary_key'] not in data:
            raise ValueError("Primary key is missing in the data.")
        
        if table_name not in self.database:
            self.database[table_name] = {col: [] for col in table_info['columns']}
        
        passkey = self.schema_manager.get_passkey()
        encrypted_values = {col: encrypt(passkey, str(val)) for col, val in data.items()}
        
        for column, value in encrypted_values.items():
            self.database[table_name][column].append(value)
        print(f"Data inserted into '{table_name}' in {time.time() - start_time:.6f} seconds")
    
    def fetch_data(self, table_name):
        start_time = time.time()
        if table_name not in self.database:
            raise NonExistantTableException()
        encrypted_data = self.database.get(table_name, {})
        passkey = self.schema_manager.get_passkey()
        decrypted_data = {col: np.array([decrypt(passkey, val) for val in values]) for col, values in encrypted_data.items()}
        print(f"Data fetched from '{table_name}' in {time.time() - start_time:.6f} seconds")
        return decrypted_data
    
if __name__ == "__main__":
    schema_manager = SchemaManager("test_db")
    db_manager = DatabaseManager(schema_manager)
    
    #schema_manager.add_table("student", ["id", "name", "age"], "id")
    #schema_manager.add_table("children", ["child_id", "parent_id", "age"], "child_id", foreign_keys={"parent_id": "student.id", "age": "student.age"})
    
    #for i in range(1, 1001):
        #db_manager.insert_data("student", {"id": i, "name": f"Student_{i}", "age": random.randint(18, 25)})
        #db_manager.save_database()
        #db_manager.insert_data("children", {"child_id": i, "parent_id": random.randint(1, 100), "age": random.randint(1, 17)})
        #db_manager.save_database()
    student_data = db_manager.fetch_data("student")
    children_data = db_manager.fetch_data("children")
    print(f"Fetched {len(student_data['id'])} records from 'student' table.")
    print(f"Fetched {len(children_data['child_id'])} records from 'children' table.")
    print(student_data)
