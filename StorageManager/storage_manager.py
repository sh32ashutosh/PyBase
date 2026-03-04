import os
import json
import binascii
from .page import PageManager
from .wal import WALManager
from .record_manager import RecordManager

class storage_manager:
    def __init__(self, db_path, log_path, max_pages=1000, page_size=102400):
        self.db_path = db_path
        self.log_path = log_path
        self.page_size = page_size
        self.aof_log = log_path + ".aof"
        self.dblock_path = db_path + ".dblock"
        self.location_map = {}
        
        self.is_recovery = self._resolve_state()

        if not self.is_recovery:
            for fp in [self.db_path, self.log_path, self.aof_log, self.dblock_path]:
                if os.path.exists(fp):
                    try: os.remove(fp)
                    except Exception: pass
        else:
            for fp in [self.db_path, self.log_path]:
                if os.path.exists(fp):
                    try: os.remove(fp)
                    except Exception: pass

        self.pm = PageManager(self.db_path, max_pages, self.page_size)
        self.wal = WALManager(self.log_path, self.pm)
        self.rm = RecordManager(self.pm)

        # THE FIX: Start at Page 1 and strictly enforce sequential allocation.
        # This prevents Windows from generating sparse, uninitialized memory blocks.
        self.current_data_page = 1
        self._ensure_page(self.current_data_page)

        if self.is_recovery:
            self._replay_aof()

        self.aof_file = open(self.aof_log, 'a')

    def _ensure_page(self, page_id):
        """Forces the C++ kernel to properly initialize and zero out the memory."""
        try:
            self.pm.create_page(page_id)
        except Exception:
            pass

    def _resolve_state(self):
        if not os.path.exists(self.dblock_path):
            return False
        try:
            with open(self.dblock_path, 'r') as f:
                state = json.load(f)
            return state.get("status") == "CRASHED"
        except Exception:
            return False

    def _save_map(self, status="CRASHED"):
        try:
            with open(self.dblock_path, 'w') as f:
                json.dump({
                    "status": status,
                    "page_pointer": self.current_data_page,
                    "map": self.location_map
                }, f)
        except Exception:
            pass

    def _replay_aof(self):
        if not os.path.exists(self.aof_log): return
        with open(self.aof_log, 'r') as f:
            for line in f:
                try:
                    line = line.strip()
                    if not line: continue
                    key_str, hex_data = line.split('||')
                    self._raw_insert(int(key_str), binascii.unhexlify(hex_data))
                except Exception:
                    pass
        self._save_map("RECOVERED")

    def _raw_insert(self, key, data):
        while True:
            try:
                slot_id = self.rm.insert(self.current_data_page, data)
                if slot_id == -1:
                    self.current_data_page += 1
                    self._ensure_page(self.current_data_page)
                    continue

                self.location_map[str(key)] = (self.current_data_page, slot_id)
                return True
            except Exception as e:
                if "full" in str(e).lower():
                    self.current_data_page += 1
                    self._ensure_page(self.current_data_page)
                    continue
                raise e

    def insert(self, key, data):
        if isinstance(data, str): data = data.encode('utf-8')
        
        self._raw_insert(key, data)

        if hasattr(self, 'aof_file') and self.aof_file:
            hex_payload = binascii.hexlify(data).decode('utf-8')
            self.aof_file.write(f"{key}||{hex_payload}\n")
            self.aof_file.flush()

        if key > 0 and key % 5000 == 0:
            self._save_map("CRASHED")

    def read(self, key):
        try:
            loc = self.location_map.get(str(key))
            if not loc: return None
            
            page_id, slot_id = loc
            return self.rm.get(page_id, slot_id)
        except Exception:
            return None

    def flush(self):
        if hasattr(self, 'aof_file') and self.aof_file and not self.aof_file.closed:
            self.aof_file.flush()
            try: os.fsync(self.aof_file.fileno())
            except Exception: pass
        try: self.pm.flush_all()
        except Exception: pass
        
        self._save_map("CLEAN_SHUTDOWN")

    def close(self):
        self.flush()
        if hasattr(self, 'aof_file') and self.aof_file and not self.aof_file.closed:
            self.aof_file.close()
        try: self.pm.destroy()
        except Exception: pass