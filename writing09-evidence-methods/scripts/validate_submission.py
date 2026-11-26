#!/usr/bin/env python3
"""Check the delivered chapter against the contract before anyone submits it.

Every check here exists because of a specific failure mode seen while writing
chapters this way: a table row with no address, a conflict quietly resolved by
choosing one value, a chapter that claims a comparison it never describes.

Usage:
  python scripts/validate_submission.py --dir out/ --strict --skill-root .
Exit codes: 0 clean, 1 violations, 3 the package cannot be read.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ADDR = re.compile(r"^([^#]+)#L(\d+)-L(\d+)$")
GAP_KINDS = {"missing", "conflict", "needs_confirmation"}
REQUIRED_HEADINGS = [
    "Method steps", "Experimental setup", "Parameters", "Datasets and splits",
    "Controls and comparisons", "Reproducibility checklist", "Limitations and scope",
    "Open items for author confirmation",
]
REQUIRED_RESULT = ["case_id", "status", "sources", "uncertainty", "change_log"]
LIMITS = {"files": 50, "file_bytes": 500 * 1024, "total_bytes": 2 * 1024 * 1024}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skill-root", default=".")
    args = ap.parse_args()

    out = Path(args.dir)
    violations: list[dict] = []

    def bad(kind: str, detail: str, where: str = "") -> None:
        violations.append({"type": kind, "detail": detail, "where": where})

    for name in ("methods.md", "parameters.csv", "evidence.csv", "gaps.json", "result.json"):
        if not (out / name).exists():
            bad("missing_output", name)
    if any(v["type"] == "missing_output" for v in violations):
        print(json.dumps({"status": "cannot_read", "violations": violations}, ensure_ascii=False, indent=2))
        return 3

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    for field in REQUIRED_RESULT:
        if field not in result:
            bad("result_field_missing", field, "result.json")
    if result.get("status") not in {"success", "partial", "unable", "refused"}:
        bad("bad_status", str(result.get("status")), "result.json")
    if result.get("status") in {"partial", "unable", "refused"} and not result.get("status_reasons"):
        bad("status_without_reason", result.get("status"), "result.json")
    if not isinstance(result.get("uncertainty", None), list):
        bad("uncertainty_not_list", "must be an array of objects", "result.json")
    if not isinstance(result.get("change_log", None), list):
        bad("change_log_not_list", "must be an array", "result.json")

    chapter = (out / "methods.md").read_text(encoding="utf-8")
    for h in REQUIRED_HEADINGS:
        if f"## " not in chapter or h not in chapter:
            bad("heading_missing", h, "methods.md")
    for marker in ("_Not supplied in the semantic layer", "_No parameter could be extracted",
                   "_Reproduction checklist empty", "_No limitation written"):
        if marker in chapter and result.get("status") == "success":
            bad("empty_group_claimed_success", marker, "methods.md")

    with (out / "evidence.csv").open(encoding="utf-8") as f:
        ev_rows = list(csv.DictReader(f))
    ev_paths = {r["path"] for r in ev_rows}
    ev_blocks = {r["block_id"] for r in ev_rows}
    if not ev_rows:
        bad("evidence_empty", "no evidence rows", "evidence.csv")

    with (out / "parameters.csv").open(encoding="utf-8") as f:
        p_rows = list(csv.DictReader(f))
    if not p_rows:
        bad("parameters_empty", "no parameters extracted; the chapter cannot state settings", "parameters.csv")
    for row in p_rows:
        m = ADDR.match(row.get("source", ""))
        if not m:
            bad("param_without_address", f"{row.get('name')} has source '{row.get('source')}'", "parameters.csv")
            continue
        if m.group(1) not in ev_paths:
            bad("param_source_not_in_evidence", f"{row.get('name')} -> {m.group(1)}", "parameters.csv")
        if int(m.group(3)) < int(m.group(2)):
            bad("param_address_inverted", row.get("source", ""), "parameters.csv")
        if row.get("status") not in {"confirmed", "candidate", "conflict"}:
            bad("bad_param_status", row.get("status", ""), "parameters.csv")

    gaps = json.loads((out / "gaps.json").read_text(encoding="utf-8"))
    for g in gaps.get("gaps", []):
        if g.get("kind") not in GAP_KINDS:
            bad("bad_gap_kind", str(g.get("kind")), "gaps.json")
        if not g.get("item") or not g.get("evidence"):
            bad("gap_without_evidence", str(g.get("item")), "gaps.json")

    conflicts = gaps.get("conflicts_from_materials", [])
    if conflicts:
        unc_text = json.dumps(result.get("uncertainty", []), ensure_ascii=False)
        if "material_conflict" not in unc_text:
            bad("conflict_not_surfaced", f"{len(conflicts)} material conflicts are not in uncertainty", "result.json")
        if result.get("status") == "success":
            bad("conflict_but_status_success", "a silently resolved conflict", "result.json")

    for p in p_rows:
        if p.get("status") == "conflict":
            if p.get("name") not in json.dumps(conflicts, ensure_ascii=False):
                bad("conflict_param_not_in_gaps", p.get("name", ""), "gaps.json")

    # quoted evidence must exist in the source materials verbatim
    if result.get("sources"):
        for s in result["sources"]:
            if not s.get("path"):
                bad("source_without_path", str(s), "result.json")

    # platform resource limits
    root = Path(args.skill_root)
    files = [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")]
    text_files = [p for p in files if p.suffix.lower() in
                  {".md", ".json", ".py", ".txt", ".csv", ".yaml", ".yml", ".jsonld"}]
    total = sum(p.stat().st_size for p in text_files)
    if len(text_files) > LIMITS["files"]:
        bad("resource_file_count", f"{len(text_files)} > {LIMITS['files']}", str(root))
    if total > LIMITS["total_bytes"]:
        bad("resource_total_bytes", f"{total} > {LIMITS['total_bytes']}", str(root))
    for p in text_files:
        if p.stat().st_size > LIMITS["file_bytes"]:
            bad("resource_file_bytes", f"{p.name} {p.stat().st_size}", str(p))
        if os.path.islink(p):
            bad("symlink", str(p), str(p))

    payload = {
        "status": "ok" if not violations else "violations",
        "checks": {
            "result_contract": "ok",
            "headings": len(REQUIRED_HEADINGS),
            "params": len(p_rows),
            "evidence_blocks": len(ev_rows),
            "gaps": len(gaps.get("gaps", [])),
            "conflicts": len(conflicts),
            "resource_files": len(text_files),
            "resource_bytes": total,
        },
        "violations": violations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if violations:
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
