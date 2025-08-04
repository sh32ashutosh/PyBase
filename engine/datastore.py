# engine/datastore.py — part of PyBase adaptive engine core

from datetime import datetime

class Table:
    def __init__(self):
        self.user = set()
        self.type = ''
        self.name = ''
        self.fields = []              # schema: expected field names
        self.records = []            # actual data records
        self.meta = {
            'created': None,
            'count': 0,
            'read': 0,
            'write': 0
        }

    def _set_name(self, name: str):
        self.name = name

    def _set_type(self, type_: str):
        self.type = type_

    def _set_fields(self, fields: list):
        self.fields = fields

    def _set_meta(self, count=0, read=0, write=0, created=None):
        self.meta['created'] = created or datetime.now()
        self.meta['count'] = count
        self.meta['read'] = read
        self.meta['write'] = write

    def _insert_record(self, record: dict):
        # Optional: basic field validation
        if not set(record.keys()).issubset(set(self.fields)):
            raise ValueError(f"Invalid fields in record: {record}")
        self.records.append(record)
        self.meta['count'] += 1
        self.meta['write'] += 1


class DataStore:
    def __init__(self):
        self.tables = {}             # table_name -> Table object
        self.procedures = None

    def create_table(self, table_name: str, type_: str, fields: list):
        if table_name in self.tables:
            raise ValueError("Table already present in the database")

        table = Table()
        table._set_name(table_name)
        table._set_type(type_)
        table._set_fields(fields)
        table._set_meta(created=datetime.now())

        self.tables[table_name] = table

    def insert(self, table_name: str, data: dict):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")
        table = self.tables[table_name]
        table._insert_record(data)
        return 0

    def select(self, table_name: str):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")
        table = self.tables[table_name]
        table.meta['read'] += 1
        return table.records

    def update(self, table_name: str, index: int, new_data: dict):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")
        table = self.tables[table_name]
        if index >= len(table.records):
            raise IndexError("No such record index to update")
        table.records[index].update(new_data)
        table.meta['write'] += 1

    def delete(self, table_name: str):
        if table_name not in self.tables:
            raise ValueError("Table does not exist")
        del self.tables[table_name]
