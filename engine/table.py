from filesystem import _folder_exists
class Table():
    def __init__(self):
        self.user = set()
        self.type = ''
        self.name = ''
        self.old_name=[]
        self.fields = dict[str,tuple] # schema: {field_name: {offset, size, type}}
        self.records = []
        self.meta = {
            'created': None,
            'count': 0,
            'read': 0,
            'write': 0
        }

    def _set_name(self, name: str):
        self.old_version.append(self.name)
        self.name=name

    def _set_type(self, type: str):
        from modules.blob import Blob
        if type.lower() not in('str', 'int','float','blob'):
            raise TypeError('the object type is unsupported if binary use blob')
        self.type = type

    def _set_fields(self, fields: dict[str:tuple]):
        self.fields = fields

    def _set_meta(self, count=0, read=0, write=0,rollback_after_commit=False):
        from datetime import datetime
        self.meta['created'] = else datetime.utcnow().isoformat()
        self.meta['count'] = count
        self.meta['read'] = read
        self.meta['write'] = write
        self.meta['rollback_after_commit']=rollback_after_commit

    def _insert_record(self, record: dict):
        self.meta['write']+=1
        for key in record.keys():
            if key not in self.fields.keys():
                raise ValueError(f"Invalid field in record: {key}")
        if record
        self.records.append(record)
        self.meta['count'] += 1
        self.meta['write'] -= 1
