import os

INCLUDE_DIRS = ["src"]
EXTENSIONS = {".ts", ".tsx", ".css"}
EXCLUDE_DIRS = {"node_modules", ".next", ".git", "public", "__pycache__"}
OUTPUT_FILE = "frontend_snapshot.txt"

with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for root, dirs, files in os.walk("frontend"):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in sorted(files):
            if any(file.endswith(ext) for ext in EXTENSIONS):
                path = os.path.join(root, file)
                out.write("=" * 80 + "\n")
                out.write(f"FILE: {path}\n")
                out.write("=" * 80 + "\n")
                try:
                    with open(path, encoding="utf-8") as f:
                        out.write(f.read())
                except Exception as e:
                    out.write(f"[Could not read: {e}]\n")
                out.write("\n\n")

print(f"Snapshot written to {OUTPUT_FILE}")
