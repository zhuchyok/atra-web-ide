---
name: sandbox-first
description: When solving tasks that involve code generation, analysis, or file operations, prefer using the code sandbox (Docker-isolated execution) over speculative answers. Run code, verify outputs, and return grounded results.
version: 1.0.0
---

# Sandbox-First Approach

## Why

The code sandbox (`code_sandbox.py`) executes code in an isolated Docker container (`--network=none`, `--read-only`, memory-limited). This gives you:

- **Grounded answers**: run the code, see the output, report facts
- **Safety**: isolated from the host system
- **Verification**: test your proposed solution before delivering it

## When to use

- Any task that says "check", "audit", "scan", "find", "parse"
- Code generation tasks — run the generated code to verify it works
- Data analysis — process the data in sandbox, report real results
- Security audits — run the scanner in sandbox, capture output
- File operations — read/parse files in sandbox, never guess contents

## How to use

The sandbox is triggered automatically when `CODE_SANDBOX_ENABLED=true` and your response contains ` ```python ` code blocks. Each block is executed and results are appended as comments.

Best practices:

```python
# 1. Read a file to understand its contents
with open('/path/to/file.py') as f:
    content = f.read()
print(f"File length: {len(content)} chars")

# 2. Analyze what you found
import re
issues = re.findall(r'(password|secret|token)\s*=\s*["\'][^"\']+["\']', content)
print(f"Potential secrets found: {len(issues)}")

# 3. Report structured results
print(json.dumps({"issues_found": len(issues), "severity": "high" if issues else "none"}))
```

## Outcome classes

When you finish a sandbox task, include an outcome class:

- `OUTCOME_OK` — task solved, all evidence cited
- `OUTCOME_NONE_UNSUPPORTED` — task is out of scope
- `OUTCOME_ERR_INTERNAL` — sandbox/unexpected failure

Every file you read must be cited in `source_attribution`.
