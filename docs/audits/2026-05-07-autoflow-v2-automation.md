# AutoFlow v2 Automation Baseline

## Objective

Enable deterministic process discipline so the agent follows the right workflow at the right time without manual reminders.

## Implemented Controls

- `beforeSubmitPrompt` command hook routes prompts by intent:
  - creative/change requests -> design-first flow (`brainstorming` then planning),
  - bug/regression requests -> root-cause-first (`systematic-debugging`),
  - finalize/ship requests -> evidence-first (`verification-before-completion`).
- Escalation logic: repeated requests of the same category return stricter next-step guidance.
- `beforeShellExecution` safety gate blocks destructive shell patterns and asks confirmation for force-push.
- Always-apply rule enforces AutoFlow execution discipline across sessions.

## Files

- `.cursor/hooks.json`
- `.cursor/hooks/autoflow_prompt_gate.py`
- `.cursor/hooks/shell_safety_gate.py`
- `.cursor/rules/89_autoflow_execution_discipline.mdc`

## Validation

- JSON config parsed successfully.
- Hook scripts are executable.
- Prompt gate returned expected `allow/ask` responses for neutral, creative, bugfix, and finalize prompts.
- Shell safety gate returned expected `allow/deny/ask` for safe, destructive, and force-push commands.
