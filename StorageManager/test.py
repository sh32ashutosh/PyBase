import os
import sys
import shutil

# --- Helper Function ---
def check(condition, ok_msg, fail_msg):
    """
    Simple pass/fail test printer.
    Returns True on success, False on failure.
    """
    if condition:
        print(f"[  OK  ] {ok_msg}")
        return True
    else:
        print(f"[ FAIL ] {fail_msg}")
        return False

# --- Main Test Function ---
def run_smoke_test():
    print("--- Pytabase C++/Python Smoke Test ---")
    
    # Import the wrapper module. This is our first test.
    try:
        from pytabase import Pytabase
        print("[  OK  ] Imported 'pytabase.py' module successfully.")
        # Access the internal _lib to print the loaded DLL path
        print(f"[ INFO ] DLL was loaded from: {_lib._name}") 
    except Exception as e:
        print(f"[ FAIL ] Could not import 'pytabase.py'.")
        print(f"         Error: {e}")
        return False

    # Define test constants
    TEST_DIR = "temp_test_db"
    TEST_DB_PATH = os.path.join(TEST_DIR, "test.db")
    TEST_KEY = b'\x01\x02\x03\x04' * 8  # 32 bytes
    TEST_SALT = b'\x0A\x0B' * 8       # 16 bytes
    
    # Cleanup before we start
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    db = None
    all_tests_passed = True
    try:
        # --- Test 1: Open/Close ---
        print("\n--- Test 1: pytabase_open() & pytabase_close() ---")
        db = Pytabase(TEST_DB_PATH, TEST_KEY, TEST_SALT)
        if not check(db._handle is not None, "Database opened, handle created.", "Failed to open database."):
            all_tests_passed = False
        else:
            db.close()
            if not check(db._handle is None, "Database closed, handle released.", "Failed to close database."):
                all_tests_passed = False

        # --- Test 2: 'with' statement ---
        print("\n--- Test 2: Context Manager ('with' statement) ---")
        with Pytabase(TEST_DB_PATH, TEST_KEY, TEST_SALT) as db_with:
            pass
        if not check(db_with._handle is None, "Exited 'with' block, auto-close worked.", "Auto-close failed."):
            all_tests_passed = False

        # --- Test 3: Get Stats ---
        print("\n--- Test 3: pytabase_get_stats() ---")
        with Pytabase(TEST_DB_PATH, TEST_KEY, TEST_SALT) as db:
            stats = db.get_stats()
            print(f"         Stats reported: '{stats}'")
            if not check("BlockSize: 4096" in stats, "Stats contain correct BlockSize.", "Stats mismatch."):
                all_tests_passed = False

        # --- Test 4: Modify Setting ---
        print("\n--- Test 4: pytabase_modify_setting() ---")
        with Pytabase(TEST_DB_PATH, TEST_KEY, TEST_SALT) as db:
            db.modify_setting("cache_size", "2048")
            new_stats = db.get_stats()
            print(f"         New Stats: '{new_stats}'")
            if not check("CacheCapacity: 2048" in new_stats, "Setting was modified.", "Setting change not reflected."):
                all_tests_passed = False

        # --- Test 5: Invalid Setting ---
        print("\n--- Test 5: Error handling (invalid setting) ---")
        with Pytabase(TEST_DB_PATH, TEST_KEY, TEST_SALT) as db:
            try:
                db.modify_setting("this_is_not_a_real_key", "123")
                check(False, "", "API did not fail on invalid key 'this_is_not_a_real_key'.")
                all_tests_passed = False
            except KeyError:
                check(True, "API correctly raised KeyError for invalid key.", "")
            except Exception as e:
                check(False, "", f"API raised wrong error for invalid key: {e}")
                all_tests_passed = False

    except Exception as e:
        print(f"\n[ FATAL ] Test suite crashed with unexpected error: {e}")
        all_tests_passed = False

    finally:
        # Cleanup
        print("\n--- Cleanup ---")
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
            print(f"[  OK  ] Cleaned up test directory: {TEST_DIR}")
    
    if all_tests_passed:
        print("\n[ SUCCESS ] All smoke tests passed.")
    else:
        print("\n[ FAILURE ] One or more tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_smoke_test()