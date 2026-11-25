#!/usr/bin/env python3
"""Validate the stable schema for Reading 10 JSON notes."""
import json
import sys
from pathlib import Path

REQUIRED_TOP = {"metadata", "chapters", "notes", "uncertainties"}
REQUIRED_NOTE = {"id", "chapter", "claim", "research_question", "data", "method_conditions", "finding", "limitations", "anchor", "status"}

def fail(message):
    print(f"ERROR: {message}")
    return 1

def main(path):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return fail(f"cannot read JSON: {exc}")
    missing = REQUIRED_TOP - set(doc) if isinstance(doc, dict) else REQUIRED_TOP
    if missing:
        return fail(f"missing top-level fields: {sorted(missing)}")
    if not isinstance(doc["notes"], list):
        return fail("notes must be an array")
    ids = set()
    for i, note in enumerate(doc["notes"]):
        if not isinstance(note, dict):
            return fail(f"notes[{i}] must be an object")
        missing = REQUIRED_NOTE - set(note)
        if missing:
            return fail(f"notes[{i}] missing: {sorted(missing)}")
        if note["id"] in ids:
            return fail(f"duplicate note id: {note['id']}")
        ids.add(note["id"])
        anchor = note["anchor"]
        if not isinstance(anchor, dict) or not anchor.get("section") or anchor.get("paragraph") in (None, ""):
            return fail(f"notes[{i}].anchor needs section and paragraph")
        if note["status"] not in {"supported", "uncertain", "conflict", "not_reported"}:
            return fail(f"notes[{i}].status is invalid")
    print(f"OK: {len(doc['notes'])} notes, {len(doc['chapters'])} chapters")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_notes.py notes.json")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
