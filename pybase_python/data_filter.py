import re
from storage_manager import *
import os

# Exception when the database directory is not existent
class NonExistantDatabaseException(Exception):
    def __init__(self):
        super().__init__("Warning: the database does not exist")

# Exception when the table name is not given
class TableNotPresent(Exception):
    def __init__(self):
        super().__init__("The table does not exist in the current scenario")

# Exception when column is not present 
class ColumnNotPresent(Exception):
    def __init__(self):
        super().__init__("The column specified does not exist")

class Select:
    def __init__(self, database, query):
        self.query = query.strip()
        self.database = database
        
        if not os.path.exists(self.database):
            raise NonExistantDatabaseException()
        
        self.columns, self.table_name = self._extract_columns_and_table()
        self.constraints = self._extract_constraints()

        if not self.table_name or not self.columns:
            raise TableNotPresent()
        
    def _extract_columns_and_table(self):
        """Extracts selected columns and table name from the query."""
        match = re.match(r"(?i)SELECT\s+(.*?)\s+FROM\s+(\w+)", self.query)
        if match:
            columns = match.group(1).strip()
            table_name = match.group(2).strip()
            
            # Handle SELECT * scenario
            if columns == "*":
                return ["*"], table_name

            # Handle multiple columns and potential aliases
            columns = [col.strip() for col in columns.split(",")]
            return columns, table_name
        return None, None

    def _extract_constraints(self):    
        """Extracts WHERE, GROUP BY, HAVING, and ORDER BY clauses from the query."""
        constraints = {}

        # Extract WHERE clause
        where_match = re.search(r"(?i)WHERE\s+(.+?)(?=\s*(ORDER BY|GROUP BY|HAVING|LIMIT|$))", self.query, re.IGNORECASE)
        constraints["WHERE"] = where_match.group(1).strip() if where_match else None

        # Extract GROUP BY clause
        group_by_match = re.search(r"(?i)GROUP BY\s+(.+?)(?=\s*(HAVING|LIMIT|$))", self.query, re.IGNORECASE)
        constraints["GROUP BY"] = group_by_match.group(1).strip() if group_by_match else None

        # Extract HAVING clause
        having_match = re.search(r"(?i)HAVING\s+(.+?)(?=\s*(LIMIT|$))", self.query, re.IGNORECASE)
        constraints["HAVING"] = having_match.group(1).strip() if having_match else None

        # Extract ORDER BY clause
        order_by_match = re.search(r"(?i)ORDER BY\s+(.+?)(?=\s*(GROUP BY|HAVING|LIMIT|$))",self.query, re.IGNORECASE)
        constraints["ORDER BY"] = order_by_match.group(1).strip() if order_by_match else None

        return constraints


# Example Usage
q1 = "select marks from students where class = 'Q' AND Department = 'CSE';"
q2 = "SELECT department, AVG(marks) AS avg_marks FROM student GROUP BY department;"
q3 = "SELECT department, AVG(marks) AS avg_marks FROM student GROUP BY department HAVING AVG(marks) > 75;"
q4 = "SELECT id, name, age, marks, department FROM student ORDER BY marks DESC;"

s1 = Select("database", q1)
s2 = Select("database", q2)
s3 = Select("database", q3)
s4 = Select("database", q4)

print(f"Table Name: {s1.table_name}")
print(f"Columns: {s1.columns}")
print(f"Constraints: {s1.constraints}")  # Output: salary > 50000 AND department = 'IT'
print(f"Table Name: {s2.table_name}")
print(f"Columns: {s2.columns}")
print(f"Constraints: {s2.constraints}") # Output: age > 30
print(f"Table Name: {s3.table_name}")
print(f"Columns: {s3.columns}")
print(f"Constraints: {s3.constraints}")  # Output: name LIKE 'John%'
print(f"Table Name: {s4.table_name}")
print(f"Columns: {s4.columns}")
print(f"Constraints: {s4.constraints}")  # Output: None

query = "SELECT id, name, age, marks, department FROM student WHERE department = 'CS' AND marks > 80 ORDER BY name"
match = re.search(r"(?i)WHERE\s+(.+?)(?=\s*(ORDER BY|GROUP BY|HAVING|LIMIT|$))", query)

if match:
    print("✅ Extracted WHERE clause:", match.group(1))
else:
    print("❌ No WHERE clause found.")