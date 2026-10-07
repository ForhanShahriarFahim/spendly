"""PostToolUse hook: run black on any Python file Claude just wrote or edited."""
import json
import subprocess
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
if path.endswith(".py"):
    # Best effort: a missing black or an unparsable file must not break the turn.
    subprocess.run(
        [sys.executable, "-m", "black", "--quiet", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
