import random
import string
import os
import pickle
import numpy as np
import time
import threading
import queue
from test import encrypt, decrypt
import multiprocessing

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
        self.crypter_lock = threading.Lock()
        
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
        
        # Get the columns to encrypt
        columns_to_encrypt = list(table_info['columns'].keys())
        values_to_encrypt = []
        
        # Prepare values for each column (ensuring we have a value for each column)
        for col in columns_to_encrypt:
            if col in data:
                values_to_encrypt.append(str(data[col]))
            else:
                values_to_encrypt.append("")
                
        # Encrypt all values as a batch
        encrypted_values = encrypt(values_to_encrypt, passkey)
        
        # Store encrypted values
        for i, col in enumerate(columns_to_encrypt):
            if i < len(encrypted_values):
                self.database[table_name][col].append(encrypted_values[i])
            else:
                self.database[table_name][col].append("")
        
        print(f"Data inserted into '{table_name}' in {time.time() - start_time:.6f} seconds")
    
    def _process_batch(self, passkey, columns, encrypted_data, start_idx, end_idx, result_queue):
        """Process a batch of rows for decryption"""
        # Collect all encrypted values from this batch across all columns
        batch_values = []
        column_indices = []  # Track which column each value belongs to
        
        for col_idx, col in enumerate(columns):
            values = encrypted_data[col]
            for row_idx in range(start_idx, min(end_idx, len(values))):
                batch_values.append(values[row_idx])
                column_indices.append((col, row_idx))
        
        # Decrypt the batch
        decrypted_values = decrypt(batch_values, passkey)
        
        # Organize results by column and row
        results = {}
        for i, decrypted_value in enumerate(decrypted_values):
            col, row_idx = column_indices[i]
            if col not in results:
                results[col] = {}
            results[col][row_idx] = decrypted_value
        
        # Put results in the queue
        result_queue.put(results)
    
    def fetch_data(self, table_name, num_threads=None):
        """
        Fetch and decrypt data from a table using multiple threads.
        
        Args:
            table_name: Name of the table to fetch data from
            num_threads: Number of threads to use (defaults to CPU count - 1)
        """
        start_time = time.time()
        
        if table_name not in self.database:
            raise NonExistantTableException()
        
        encrypted_data = self.database.get(table_name, {})
        passkey = self.schema_manager.get_passkey()
        
        # Set default number of threads if not specified
        if num_threads is None:
            num_threads = max(1, multiprocessing.cpu_count() - 1)
        
        # Get columns and determine max row count
        columns = list(encrypted_data.keys())
        if not columns:
            return {}
            
        max_rows = max(len(encrypted_data[col]) for col in columns)
        if max_rows == 0:
            return {col: [] for col in columns}
        
        # Calculate batch size for threading
        batch_size = max(1, max_rows // num_threads)
        
        # Initialize threads and results queue
        threads = []
        result_queue = queue.Queue()
        
        # Create and start threads for each batch of rows
        for start_idx in range(0, max_rows, batch_size):
            end_idx = min(start_idx + batch_size, max_rows)
            
            thread = threading.Thread(
                target=self._process_batch,
                args=(passkey, columns, encrypted_data, start_idx, end_idx, result_queue)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # Initialize result dictionary
        decrypted_data = {col: np.empty(len(encrypted_data[col]), dtype=object) for col in columns}
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results from the queue
        while not result_queue.empty():
            batch_results = result_queue.get()
            for col, row_results in batch_results.items():
                for row_idx, value in row_results.items():
                    decrypted_data[col][row_idx] = value
        
        print(f"Data fetched from '{table_name}' in {time.time() - start_time:.6f} seconds using {num_threads} threads")
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
    
    # Use the multithreaded fetch_data method
    student_data = db_manager.fetch_data("student")
    children_data = db_manager.fetch_data("children")
    print(f"Fetched {len(student_data['id'])} records from 'student' table.")
    print(f"Fetched {len(children_data['child_id'])} records from 'children' table.")
    print(student_data)