"""PreToolUse hook: block destructive shell commands that touch protected files."""
import json
import re
import sys

PROTECTED = ("expense_tracker.db", "spendly.db", ".env", "migrations/")
DESTRUCTIVE = re.compile(r"(^|[\s;&|])(rm|unlink|truncate|del|erase)\s")

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

if DESTRUCTIVE.search(command):
    for name in PROTECTED:
        if name in command:
            print(
                f"BLOCKED: cannot run a destructive command on protected file: {name}",
                file=sys.stderr,
            )
            sys.exit(2)
