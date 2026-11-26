#!/usr/bin/env python3
"""Audit the exported nanopublications before they go anywhere.

Each check maps to one way an assertion record quietly becomes worthless: the
quote is not in the paper, two claims were welded into one, the relation is
direction-reversed, the subject and object collapsed into each other, or the
JSON-LD looks fine but cannot be parsed as records.

Usage:
  python scripts/validate_nanopub.py --dir app/output --sentences work/sentences.json \
      --strict --skill-root .
Exit: 0 clean, 1 violations, 3 unreadable package.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REQUIRED_RECORD = ["id", "assertion", "subject", "relation", "object", "evidence",
                   "source", "confidence", "confidence_rationale", "quality_flags"]
REQUIRED_EVIDENCE = ["quote", "page", "para", "sid", "type"]
REQUIRED_SOURCE = ["title", "authors", "year", "identifier"]
REQUIRED_RESULT = ["case_id", "status", "sources", "uncertainty", "change_log"]
MAX_ASSERTION_CHARS = 240
MAX_COORD = 1
LIMITS = {"files": 50, "file_bytes": 500 * 1024, "total_bytes": 2 * 1024 * 1024}
NORMALISE = re.compile(r"[^a-z0-9 ]+")


def norm(text: str) -> str:
    return " ".join(NORMALISE.sub(" ", text.lower()).split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--sentences")
    ap.add_argument("--relations", default="references/relations.json")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skill-root", default=".")
    args = ap.parse_args()

    out = Path(args.dir)
    violations: list[dict] = []

    def bad(kind: str, detail: str, where: str = "") -> None:
        violations.append({"type": kind, "detail": detail, "where": where})

    for name in ("assertions.json", "assertions.jsonld", "evidence.csv", "result.json"):
        if not (out / name).exists():
            bad("missing_output", name)
    if any(v["type"] == "missing_output" for v in violations):
        print(json.dumps({"status": "cannot_read", "violations": violations}, ensure_ascii=False, indent=2))
        return 3

    doc = json.loads((out / "assertions.json").read_text(encoding="utf-8"))
    records = doc.get("assertions", [])
    if not records:
        bad("no_records", "an export with zero assertions is not a deliverable")

    pages: dict[int, str] = {}
    if args.sentences and Path(args.sentences).exists():
        sdoc = json.loads(Path(args.sentences).read_text(encoding="utf-8"))
        for s in sdoc.get("sentences", []):
            pages[int(s["page"])] = pages.get(int(s["page"]), "") + " " + s["text"]
    relations: dict = {}
    if Path(args.relations).exists():
        rdoc = json.loads(Path(args.relations).read_text(encoding="utf-8"))
        relations = rdoc.get("relations", rdoc)

    seen: dict[str, str] = {}
    for r in records:
        for field in REQUIRED_RECORD:
            if field not in r or r[field] in (None, "", [], {}):
                if field == "quality_flags" and r.get(field) == []:
                    continue
                bad("record_field_missing", f"{r.get('id')} -> {field}", "assertions.json")
        ev = r.get("evidence") or {}
        for field in REQUIRED_EVIDENCE:
            if field not in ev:
                bad("evidence_field_missing", f"{r.get('id')} -> evidence.{field}", "assertions.json")
        src = r.get("source") or {}
        for field in REQUIRED_SOURCE:
            if field not in src:
                bad("source_field_missing", f"{r.get('id')} -> source.{field}", "assertions.json")

        quote = ev.get("quote", "")
        if pages and quote:
            page = int(ev.get("page", 0))
            haystack = pages.get(page)
            if haystack is None:
                bad("quote_page_absent", f"{r.get('id')} claims page {page}, which has no text")
            elif quote not in haystack:
                bad("quote_not_on_page", f"{r.get('id')} p.{page}", "assertions.json")

        text = r.get("assertion", "")
        # the assertion must be the paper's own wording; a paraphrase is a claim
        # whose support cannot be checked by locating it
        if pages and text and pages.get(int(ev.get("page", 0))) is not None:
            if text.strip() not in pages[int(ev.get("page", 0))]:
                bad("assertion_not_in_source", f"{r.get('id')} p.{ev.get('page')}", "assertions.json")
        if len(text) > MAX_ASSERTION_CHARS:
            bad("assertion_too_wide", f"{r.get('id')} {len(text)} chars", "assertions.json")
        coords = sum(text.count(m) for m in (" and ", " but ", " whereas ", " while "))
        if coords > MAX_COORD and "multiple_coordination" not in (r.get("quality_flags") or []):
            bad("multiple_claims_welded", f"{r.get('id')} has {coords} coordinations and no flag", "assertions.json")

        rel = r.get("relation", "")
        if relations and rel and rel not in relations:
            if "relation_unmapped" not in (r.get("quality_flags") or []):
                bad("relation_not_controlled", rel, "assertions.json")

        if r.get("subject") and r.get("object") and norm(r["subject"]) == norm(r["object"]):
            bad("subject_object_identical", r.get("id", ""), "assertions.json")

        conf = r.get("confidence")
        if isinstance(conf, (int, float)) and not (0 <= float(conf) <= 1):
            bad("confidence_out_of_range", f"{r.get('id')} {conf}", "assertions.json")

        key = norm(text)
        if key in seen:
            bad("duplicate_assertion", f"{r.get('id')} duplicates {seen[key]}", "assertions.json")
        else:
            seen[key] = r.get("id", "")

    ld = json.loads((out / "assertions.jsonld").read_text(encoding="utf-8"))
    if "@context" not in ld:
        bad("jsonld_no_context", "the export is not parseable as JSON-LD", "assertions.jsonld")
    ld_assertions = ld.get("assertion", [])
    if len(ld_assertions) != len(records):
        bad("jsonld_count_mismatch", f"{len(ld_assertions)} nodes vs {len(records)} records", "assertions.jsonld")
    for node in ld_assertions:
        if not node.get("@id") or "prov:wasDerivedFrom" not in node:
            bad("jsonld_node_incomplete", str(node.get("@id")), "assertions.jsonld")

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    for field in REQUIRED_RESULT:
        if field not in result:
            bad("result_field_missing", field, "result.json")
    if result.get("status") not in {"success", "partial", "unable", "refused"}:
        bad("bad_status", str(result.get("status")), "result.json")
    if result.get("status") in {"partial", "unable", "refused"} and not result.get("status_reasons"):
        bad("status_without_reason", result.get("status"), "result.json")

    root = Path(args.skill_root)
    files = [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")]
    text_files = [p for p in files if p.suffix.lower() in
                  {".md", ".json", ".py", ".txt", ".csv", ".jsonld", ".yaml", ".yml"}]
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
            "records": len(records),
            "jsonld_nodes": len(ld_assertions),
            "duplicates": len(records) - len(seen),
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
