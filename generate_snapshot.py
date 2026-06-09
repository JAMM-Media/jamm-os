import os

SKIP_DIRS = {'__pycache__', '.git', 'venv', 'migrations'}
OUTPUT_FILE = 'codebase_snapshot.txt'
ROOT = 'app'

def write_file(out, filepath):
    out.write(f'# {"=" * 60}\n')
    out.write(f'# FILE: {filepath}\n')
    out.write(f'# {"=" * 60}\n\n')
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        out.write(f.read())
    out.write('\n\n')

with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
    if os.path.exists('main.py'):
        write_file(out, 'main.py')

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            write_file(out, filepath)

print(f'Snapshot written to {OUTPUT_FILE}')
