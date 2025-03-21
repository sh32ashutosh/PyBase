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
        
        # Use the crypter lock for thread safety
        with self.crypter_lock:
            encrypted_values = {col: encrypt(passkey, str(val)) for col, val in data.items()}
        
        for column, value in encrypted_values.items():
            self.database[table_name][column].append(value)
        print(f"Data inserted into '{table_name}' in {time.time() - start_time:.6f} seconds")
    
    def _decrypt_batch(self, passkey, column_name, values, start_idx, end_idx, result_queue):
        """Helper function to decrypt a batch of values in a separate thread"""
        decrypted_batch = []
        for i in range(start_idx, end_idx):
            # Use lock to ensure thread-safe access to crypter
            with self.crypter_lock:
                decrypted_value = decrypt(passkey, values[i])
            decrypted_batch.append(decrypted_value)
        
        # Put the result in the queue
        result_queue.put((column_name, start_idx, decrypted_batch))
    
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
        
        # Calculate batch size based on data size and thread count
        # Each column will be processed in parallel
        threads = []
        result_queue = queue.Queue()
        
        # Process each column
        for column_name, values in encrypted_data.items():
            total_values = len(values)
            
            # Skip empty columns
            if total_values == 0:
                continue
                
            # Calculate optimal batch size
            batch_size = max(1, total_values // num_threads)
            
            # Create and start threads for each batch
            for start_idx in range(0, total_values, batch_size):
                end_idx = min(start_idx + batch_size, total_values)
                
                thread = threading.Thread(
                    target=self._decrypt_batch,
                    args=(passkey, column_name, values, start_idx, end_idx, result_queue)
                )
                thread.daemon = True
                thread.start()
                threads.append(thread)
        
        # Initialize result dictionary
        decrypted_data = {col: np.empty(len(values), dtype=object) for col, values in encrypted_data.items() if len(values) > 0}
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results from the queue
        while not result_queue.empty():
            column_name, start_idx, decrypted_batch = result_queue.get()
            # Place the decrypted values in the correct positions in the result array
            decrypted_data[column_name][start_idx:start_idx + len(decrypted_batch)] = decrypted_batch
        
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