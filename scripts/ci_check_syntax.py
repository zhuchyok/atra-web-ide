"""CI syntax check — validates all Python files parse correctly."""
import ast
import glob
import sys

files = glob.glob("knowledge_os/app/*.py") + glob.glob("knowledge_os/app/**/*.py", recursive=True) + glob.glob("src/**/*.py", recursive=True)
errors = []
for f in files:
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        errors.append(f"{f}: {e}")

if errors:
    for e in errors:
        print(f"FAIL: {e}")
    sys.exit(1)
print(f"{len(files)} files syntax OK")
