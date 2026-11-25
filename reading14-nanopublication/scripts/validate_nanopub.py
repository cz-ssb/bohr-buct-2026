#!/usr/bin/env python3
"""Validate assertion records for Reading 14."""
import json
import sys
from pathlib import Path

REQ = {"id", "assertion", "subject", "relation", "object", "qualifiers", "evidence", "source", "confidence", "confidence_rationale", "quality_flags"}

def main(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read JSON: {exc}")
        return 1
    records = d.get("assertions") if isinstance(d, dict) else None
    if not isinstance(records, list):
        print("ERROR: top-level assertions array is required")
        return 1
    ids = set()
    for i, a in enumerate(records):
        miss = REQ - set(a)
        if miss:
            print(f"ERROR: assertions[{i}] missing {sorted(miss)}")
            return 1
        if a["id"] in ids:
            print(f"ERROR: duplicate id {a['id']}")
            return 1
        ids.add(a["id"])
        ev = a["evidence"]
        if not isinstance(ev, dict) or not ev.get("location") or ev.get("type") not in {"direct", "indirect"}:
            print(f"ERROR: assertions[{i}] evidence needs location and direct/indirect type")
            return 1
        src = a["source"]
        if not isinstance(src, dict) or "title" not in src or "identifier" not in src:
            print(f"ERROR: assertions[{i}] source needs title and identifier")
            return 1
        if not 0 <= float(a["confidence"]) <= 1:
            print(f"ERROR: assertions[{i}] confidence must be between 0 and 1")
            return 1
    if len(sys.argv) == 3:
        output = {
            "@context": {
                "np": "http://www.nanopub.org/nschema#",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dct": "http://purl.org/dc/terms/",
                "prov": "http://www.w3.org/ns/prov#",
                "schema": "https://schema.org/"
            },
            "@graph": [
                {
                    "@id": a["id"],
                    "@type": "np:Assertion",
                    "schema:text": a["assertion"],
                    "schema:about": a["subject"],
                    "schema:relation": a["relation"],
                    "schema:object": a["object"],
                    "schema:qualifiers": a["qualifiers"],
                    "prov:wasDerivedFrom": a["source"],
                    "schema:citation": a["evidence"],
                    "schema:confidence": a["confidence"],
                    "schema:confidenceRationale": a["confidence_rationale"],
                    "schema:qualityFlags": a["quality_flags"]
                }
                for a in records
            ]
        }
        Path(sys.argv[2]).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif len(sys.argv) != 2:
        print("Usage: validate_nanopub.py assertions.json [output.jsonld]")
        return 2
    print(f"OK: {len(records)} assertions")
    return 0

if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        print("Usage: validate_nanopub.py assertions.json [output.jsonld]")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
