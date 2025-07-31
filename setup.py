import os

ROOT = os.getcwd()
EXCLUDE_DIRS = {'.venv', '__pycache__', '.git'}

def should_include(path):
    parts = path.split(os.sep)
    return not any(part in EXCLUDE_DIRS for part in parts)

def convert_to_utf8(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        print(f"[FIXED] Non-UTF8 characters replaced: {filepath}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_all_py_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith('.py') and should_include(os.path.join(root, file)):
                convert_to_utf8(os.path.join(root, file))

if __name__ == "__main__":
    fix_all_py_files()
    print("✅ All .py files normalized to UTF-8.")
