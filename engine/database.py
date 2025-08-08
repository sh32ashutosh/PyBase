from filesystem import _folder_exists
import os
import pickle
from datetime import datetime
import random
from table import Table

def get_parent_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Database:
    def __init__(self, name):
        self.name = name
        self._dir = os.path.join(get_parent_dir(), 'data', self.name)
        if not _folder_exists(self._dir):
            os.makedirs(self._dir)  
            self.meta = {
            'name': self.name,
            'created': datetime.utcnow().isoformat() + 'Z',
            'tables': self.tables,
            'key':random.randint(0,1200),
                        }
            self._write_meta()
        else:
            self.meta=self._load_meta()
        
        self.tables={}
        self.use = False

    def get_name(self):
        return self.name

    def _write_meta(self):
        

        meta_path = os.path.join(self._dir, 'db.meta')
        with open(meta_path, 'wb') as file:
            pickle.dump(self.meta, file)
    
    def add_table(self,table:Table):
        if _folder_exists(os.path.join(self._dir,f'\data\{self.name}\{table.name}')):
            raise 
        self.tables+={table.name}
        os.makedirs(os.path.join(self._dir,f'/data/{self.name}/{table.name}'))
        table.path



class ExistingTable(Exception):
    def __init__(self):
        super().__init__("Table alredy present in database")

db = Database("testdb")
print("Database name:", db.get_name())
print("Metadata:", db.meta)
print("Stored at:", db._dir)
