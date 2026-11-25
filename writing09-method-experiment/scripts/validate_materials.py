#!/usr/bin/env python3
"""Validate extracted Writing 09 materials without guessing missing values."""
import json
import sys
from pathlib import Path

def main(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read JSON: {exc}")
        return 1
    required = {"steps", "parameters", "datasets", "controls", "repetitions", "gaps", "reproduction"}
    missing = required - set(d)
    if missing:
        print(f"ERROR: missing top-level fields: {sorted(missing)}")
        return 1
    names = set()
    for i, p in enumerate(d["parameters"]):
        for field in ("name", "value", "unit", "target", "source", "status"):
            if field not in p:
                print(f"ERROR: parameters[{i}] missing {field}")
                return 1
        if p["name"] in names:
            print(f"ERROR: duplicate parameter {p['name']}")
            return 1
        names.add(p["name"])
        if p["status"] not in {"reported", "missing", "conflict", "needs_confirmation"}:
            print(f"ERROR: invalid status for {p['name']}")
            return 1
    for i, step in enumerate(d["steps"]):
        for field in ("order", "input", "operation", "output"):
            if field not in step:
                print(f"ERROR: steps[{i}] missing {field}")
                return 1
    print(f"OK: {len(d['steps'])} steps, {len(d['parameters'])} parameters, {len(d['gaps'])} gaps")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_materials.py materials.json")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
