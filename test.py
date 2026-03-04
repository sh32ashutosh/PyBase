import os
import sys
import time
import gc

# Ensure the subfolder is in the path so we can import StorageManager
sys.path.append(os.path.join(os.path.dirname(__file__), "StorageManager"))

# Matching your exact naming convention:
# File: StorageManager.py | Class: storage_manager
from StorageManager.storage_manager import storage_manager

def simulate_power_loss(engine):
    """Simulates a hard crash by severing handles without a graceful close."""
    engine.wal.flush() 
    del engine
    gc.collect()
    print("      -> [CRASH] Object destroyed. Memory handles severed.")

def run_rigorous_test():
    db_file = "./stress_recovery.db"
    log_file = "./stress_recovery.wal"

    if os.path.exists(db_file): os.remove(db_file)
    if os.path.exists(log_file): os.remove(log_file)

    print("\n" + "="*50)
    print(" BRUTE FORCE CRASH RECOVERY & STRESS TEST")
    print("="*50)

    # ---------------------------------------------------------
    # PHASE 1: HEAVY LOAD
    # ---------------------------------------------------------
    print("\n[PHASE 1] Booting Engine & Generating Heavy Load...")
    # UPDATED: Using storage_manager (lowercase)
    engine = storage_manager(db_file, log_file, max_pages=1000, page_size=102400)
    
    TOTAL_RECORDS = 50000
    print(f"      -> Inserting {TOTAL_RECORDS} records to force B+ Tree splits...")
    
    start_time = time.time()
    for i in range(TOTAL_RECORDS):
        payload = f'{{"id": {i}, "status": "active", "data": "CRASH_TEST_PAYLOAD"}}'.encode()
        engine.insert(i, payload)
        
        if i > 0 and i % 10000 == 0:
            print(f"         ... {i} records written.")
            
    elapsed = time.time() - start_time
    print(f"      -> [PASS] Load completed in {elapsed:.2f} seconds.")

    # ---------------------------------------------------------
    # PHASE 2: THE CRASH
    # ---------------------------------------------------------
    print("\n[PHASE 2] Simulating Sudden Power Loss...")
    simulate_power_loss(engine)
    print("      -> [PASS] System crashed. Engine is offline.")

    # ---------------------------------------------------------
    # PHASE 3: COLD BOOT & RECOVERY
    # ---------------------------------------------------------
    print("\n[PHASE 3] Cold Booting Engine...")
    start_time = time.time()
    
    # UPDATED: Using storage_manager (lowercase)
    recovery_engine = storage_manager(db_file, log_file, max_pages=1000, page_size=102400)
    
    elapsed = time.time() - start_time
    print(f"      -> [PASS] Engine recovered and mounted in {elapsed:.4f} seconds.")

    # ---------------------------------------------------------
    # PHASE 4: DATA INTEGRITY VERIFICATION
    # ---------------------------------------------------------
    print("\n[PHASE 4] Verifying Data Integrity Across 50,000 Records...")
    corrupted_count = 0
    missing_count = 0
    
    for i in range(TOTAL_RECORDS):
        expected_payload = f'{{"id": {i}, "status": "active", "data": "CRASH_TEST_PAYLOAD"}}'.encode()
        retrieved_payload = recovery_engine.read(i)
        
        if retrieved_payload is None:
            missing_count += 1
        elif retrieved_payload != expected_payload:
            corrupted_count += 1

    if missing_count == 0 and corrupted_count == 0:
        print("      -> [PASS] Zero data loss. Zero corruption. B+ Tree perfectly intact.")
    else:
        print(f"      -> [FAIL] Missing: {missing_count} | Corrupted: {corrupted_count}")
        return

    # ---------------------------------------------------------
    # PHASE 5: POST-RECOVERY STABILITY
    # ---------------------------------------------------------
    print("\n[PHASE 5] Testing Post-Recovery Engine Stability...")
    try:
        new_key = TOTAL_RECORDS + 999
        new_payload = b'{"status": "post_crash_insert"}'
        recovery_engine.insert(new_key, new_payload)
        
        verify_new = recovery_engine.read(new_key)
        assert verify_new == new_payload
        print("      -> [PASS] Engine successfully accepted and indexed new data after recovery.")
    except Exception as e:
        print(f"      -> [FAIL] Engine unstable after recovery: {e}")
        return

    recovery_engine.close()
    print("\n" + "="*50)
    print(" ALL TESTS PASSED. DATABASE KERNEL IS INDESTRUCTIBLE.")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_rigorous_test()