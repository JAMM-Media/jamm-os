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

def write_listing(out, directory):
    out.write(f'# {"=" * 60}\n')
    out.write(f'# FILES IN: {directory.replace(os.sep, "/")}/\n')
    out.write(f'# {"=" * 60}\n\n')
    for filename in sorted(os.listdir(directory)):
        if os.path.isfile(os.path.join(directory, filename)):
            out.write(f'{filename}\n')
    out.write('\n\n')

with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
    # Root-level main.py
    if os.path.exists('main.py'):
        write_file(out, 'main.py')

    # Everything inside app/
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            write_file(out, filepath)

    # Migration and test filenames only, no contents
    write_listing(out, os.path.join('migrations', 'versions'))
    write_listing(out, 'tests')

print(f'Snapshot written to {OUTPUT_FILE}')