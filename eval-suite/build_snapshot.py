#!/usr/bin/env python3
"""
Build ground_truth_snapshot.json from all ground-truth script outputs.

Run all ground_truth_*.py scripts, capture their output, and generate
a JSON snapshot with answers, sources, and timestamp.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent / "scripts"
SCRIPT_PATTERN = "ground_truth_*.py"


def extract_question_id(script_name: str) -> str:
    """Extract question ID from script name (e.g., ground_truth_feit_01.py → feit-01)."""
    # ground_truth_feit_01.py → feit_01 → feit-01
    base = script_name.replace("ground_truth_", "").replace(".py", "")
    parts = base.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return f"{parts[0]}-{parts[1]}"
    return base


def run_ground_truth_script(script_path: Path) -> str:
    """Run a ground-truth script and return its output."""
    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"WARNING: {script_path.name} failed: {result.stderr}", file=sys.stderr)
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"WARNING: {script_path.name} timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: {script_path.name}: {e}", file=sys.stderr)
        return None


def build_snapshot() -> dict:
    """Build snapshot from all ground-truth scripts."""
    scripts = sorted(SCRIPTS_DIR.glob(SCRIPT_PATTERN))
    if not scripts:
        print(f"ERROR: No ground-truth scripts found in {SCRIPTS_DIR}", file=sys.stderr)
        sys.exit(1)

    snapshot = {
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "script_count": len(scripts),
        "answers": {},
    }

    for script in scripts:
        q_id = extract_question_id(script.name)
        output = run_ground_truth_script(script)
        if output is not None:
            snapshot["answers"][q_id] = output
            print(f"✓ {q_id}: {output[:60]}")
        else:
            print(f"✗ {q_id}: FAILED")

    return snapshot


def main():
    snapshot = build_snapshot()
    output_file = SCRIPTS_DIR.parent / "ground_truth_snapshot.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    print(f"\nSnapshot written to {output_file}")
    print(f"Timestamp: {snapshot['captured_at']}")
    print(f"Answers: {len(snapshot['answers'])}/{snapshot['script_count']} successful")


if __name__ == "__main__":
    main()
