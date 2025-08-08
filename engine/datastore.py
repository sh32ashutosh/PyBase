# engine/datastore.py — PyBase adaptive engine core (CLEAN VERSION)

from datetime import datetime



class DataStore:
    def __init__(self, backend=None):
        self.tables = {}  # table_name -> Table
        self.backend = backend

    def create_table(self, table_name: str, type_: str, fields: dict):
        if table_name in self.tables:
            raise ValueError("Table already exists")

        table = Table()
        table._set_name(table_name)
        table._set_type(type_)
        table._set_fields(fields)
        table._set_meta()

        self.tables[table_name] = table

        if self.backend:
            self.backend.create_table_backend(table_name, fields)

    def insert(self, table_name: str, data: dict):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")

        table = self.tables[table_name]
        table._insert_record(data)

        if self.backend:
            self.backend.insert_record(table_name, data)

        return 0

    def select(self, table_name: str):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")

        table = self.tables[table_name]
        table.meta['read'] += 1

        if self.backend:
            return self.backend.read_all_records(table_name)

        return table.records

    def select_by_index(self, table_name: str, index: int):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")

        table = self.tables[table_name]
        if index >= len(table.records):
            raise IndexError("No such record index")

        if self.backend:
            return self.backend.read_record_by_index(table_name, index)

        return table.records[index]

    def update(self, table_name: str, index: int, new_data: dict):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")

        table = self.tables[table_name]
        if index >= len(table.records):
            raise IndexError("No such record index")

        table.records[index].update(new_data)
        table.meta['write'] += 1

        if self.backend:
            self.backend.update_record(table_name, index, new_data)

    def delete(self, table_name: str):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")

        del self.tables[table_name]

        if self.backend:
            self.backend.delete_table_backend(table_name)

    def get_table_meta(self, table_name: str):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")
        return self.tables[table_name].meta
    
    
