import os

# Root directory to search from
ROOT_DIR = '.'

# File extensions to check
PY_EXTENSIONS = ['.py']

# Report of cleaned files
cleaned_files = []

def clean_null_bytes_from_py_files():
    print('started')
    for root, _, files in os.walk(ROOT_DIR):
        for filename in files:
            print(f'cleaning {filename}')
            if any(filename.endswith(ext) for ext in PY_EXTENSIONS):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'rb') as f:
                        content = f.read()

                    if b'\x00' in content:
                        # Remove null bytes
                        cleaned = content.replace(b'\x00', b'')
                        with open(filepath, 'wb') as f:
                            f.write(cleaned)
                        cleaned_files.append(filepath)
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

clean_null_bytes_from_py_files()

print(cleaned_files)  # return the list of cleaned files for review

