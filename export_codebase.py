"""
export_codebase.py

Dumps every source file in the project into codebase_snapshot.txt,
with the relative file path as a header before each file's contents.

Excluded:
  - .venv/, venv/
  - __pycache__/
  - .git/
  - .env, .env.*
  - *.pyc, *.pyo, *.pyd
  - the snapshot output file itself
"""

import os

OUTPUT_FILE = "codebase_snapshot.txt"

INCLUDE_DIRS = ["app", "tests", os.path.join("migrations", "versions")]

EXCLUDE_DIRS = {"__pycache__"}


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    collected = []

    for include_dir in INCLUDE_DIRS:
        base = os.path.join(root, include_dir)
        if not os.path.exists(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, root)
                collected.append((rel_path, abs_path))

    collected.sort(key=lambda x: x[0])

    with open(os.path.join(root, OUTPUT_FILE), "w", encoding="utf-8") as out:
        for rel_path, abs_path in collected:
            out.write(f"{'=' * 72}\n")
            out.write(f"FILE: {rel_path}\n")
            out.write(f"{'=' * 72}\n")
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    out.write(f.read())
            except (UnicodeDecodeError, PermissionError) as e:
                out.write(f"[Could not read file: {e}]\n")
            out.write("\n\n")

    print(f"Snapshot written to {OUTPUT_FILE} ({len(collected)} files)")


if __name__ == "__main__":
    main()
