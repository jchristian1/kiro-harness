#!/usr/bin/env python3
"""
Recover a parse_failed run by re-extracting JSON with the fixed extractor.
Usage: python scripts/recover_run.py <run_id>
"""
import sys
import re
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "kiro_worker.db"

ANSI_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)

def extract_json(stdout: str) -> dict | None:
    stdout = strip_ansi(stdout).strip()
    if not stdout:
        return None
    marker = '"schema_version"'
    marker_pos = stdout.rfind(marker)
    if marker_pos == -1:
        return None
    start = stdout.rfind("{", 0, marker_pos)
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(stdout)):
        if stdout[i] == "{":
            depth += 1
        elif stdout[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        parsed = json.loads(stdout[start:end + 1])
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None

def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "run_01KNPD1TMD9316C5FSHENRMQDG"
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT raw_output, task_id, mode FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if not row:
        print(f"Run {run_id} not found")
        return
    raw_output, task_id, mode = row
    parsed = extract_json(raw_output or "")
    if parsed:
        print(f"✓ JSON extracted successfully")
        print(f"  mode: {parsed.get('mode')}")
        print(f"  headline: {parsed.get('headline', '')[:100]}")
        print(f"  recommended_next_step: {parsed.get('recommended_next_step')}")
        files = parsed.get('files_changed', [])
        print(f"  files_changed: {len(files)}")
        for f in files:
            print(f"    {f.get('action')} {f.get('path')}")
    else:
        print("✗ No JSON found even with fixed extractor")

if __name__ == "__main__":
    main()
