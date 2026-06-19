import os

SKIP_DIRS = {'.git', 'node_modules', '.next', '__pycache__'}
EXTENSIONS = {'.tsx', '.ts'}
ROOT = os.path.join('frontend', 'src')
OUTPUT_FILE = os.path.join('frontend', 'frontend_snapshot.txt')


def write_file(out, filepath):
    out.write(f'# {"=" * 60}\n')
    out.write(f'# FILE: {filepath}\n')
    out.write(f'# {"=" * 60}\n\n')
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        out.write(f.read())
    out.write('\n\n')


with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            if not any(filename.endswith(ext) for ext in EXTENSIONS):
                continue
            filepath = os.path.join(dirpath, filename)
            write_file(out, filepath)

print(f'Snapshot written to {OUTPUT_FILE}')
