from storage_manager import SchemaManager, DatabaseManager
from tabulate import tabulate

class DataFormatter:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    # Select * from table faster approach
    def fetchall(self, table_name, display_as_table=True):
        data = self.db_manager.fetch_data(table_name)
        if not data:
            return f"No data found in table '{table_name}'."
        
        if display_as_table:
            headers = list(data.keys())
            rows = zip(*[data[col] for col in headers])
            return tabulate(rows, headers=headers, tablefmt='grid')
        
        return data
    # Format the data given to it after filtering
    def format_as(self, data, display_as_table=True):
        if display_as_table:
            headers = list(data.keys())
            rows = zip(*[data[col] for col in headers])
            return tabulate(rows, headers=headers, tablefmt='grid')
        
        return data

if __name__ == "__main__":
    schema_manager = SchemaManager("test_db")
    db_manager = DatabaseManager(schema_manager)
    formatter = DataFormatter(db_manager)
    
    print(formatter.fetchall("students"))
    print(formatter.fetchall("children"))
    