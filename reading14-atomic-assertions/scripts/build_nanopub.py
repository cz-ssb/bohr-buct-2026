#!/usr/bin/env python3
"""Assemble nanopublication records from bound evidence plus a semantic layer.

The model fills `semantic_fill.json` with subject, relation, object, qualifiers,
confidence and rationale per candidate. It never supplies the evidence, the page
or the assertion text — those come from the deterministic passes, so the record
cannot claim support it does not have.

Usage:
  python scripts/build_nanopub.py --sentences work/sentences.json \
      --bound work/bound.json --out app/output --case-json case.json \
      --fill app/output/semantic_fill.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

CONTEXT = {
    "@context": {
        "np": "http://www.nanopub.org/nschema#",
        "prov": "http://www.w3.org/ns/prov#",
        "sio": "http://semanticscience.org/resource/",
        "dcterms": "http://purl.org/dc/terms/",
        "assertion": "np:hasAssertion",
        "provenance": "np:hasProvenance",
        "publicationinfo": "np:hasPublicationInfo",
        "subject": "sio:SIO_000233",
        "relation": "sio:SIO_000253",
        "object": "sio:SIO_000192",
        "quote": "sio:SIO_000300",
        "page": "dcterms:bibliographicCitation",
    }
}


def as_list(value) -> list:
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def contract_fields(case: dict) -> list[str]:
    oc = case.get("output_contract")
    if isinstance(oc, dict):
        return list(oc.keys())
    if isinstance(oc, list):
        out = []
        for item in oc:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                name = item.get("field") or item.get("name") or item.get("key")
                if name:
                    out.append(name)
        return out
    return []


def load_relations(path: Path) -> dict:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc.get("relations", doc) if isinstance(doc, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", required=True)
    ap.add_argument("--bound", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--case-json")
    ap.add_argument("--fill")
    ap.add_argument("--case-id")
    ap.add_argument("--relations", default="references/relations.json")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    sdoc = json.loads(Path(args.sentences).read_text(encoding="utf-8"))
    bdoc = json.loads(Path(args.bound).read_text(encoding="utf-8"))
    claims = bdoc.get("claims", [])
    if not claims:
        print(json.dumps({"status": "unable", "reason": "no_bound_claims"}, ensure_ascii=False), file=sys.stderr)
        return 2

    case = {}
    if args.case_json and Path(args.case_json).exists():
        case = json.loads(Path(args.case_json).read_text(encoding="utf-8"))
    case_id = args.case_id or case.get("case_id") or case.get("id") or "case"
    contract = contract_fields(case)

    relations = load_relations(Path(args.relations))
    fill = {}
    if args.fill and Path(args.fill).exists():
        fill = json.loads(Path(args.fill).read_text(encoding="utf-8"))

    # the model may only annotate candidates that exist
    claimed = {a.get("cid") for a in as_list(fill.get("assertions"))}
    known = {c["cid"] for c in claims}
    unknown = sorted(cid for cid in claimed if cid and cid not in known)
    if unknown:
        print(json.dumps({"status": "rejected", "errors": [
            {"type": "unknown_cid", "cid": cid} for cid in unknown]}, ensure_ascii=False, indent=2),
              file=sys.stderr)
        return 4

    annotations = {a["cid"]: a for a in as_list(fill.get("assertions")) if a.get("cid")}
    source = fill.get("source") or {}

    records: list[dict] = []
    flags_summary: list[dict] = []
    skipped = [c for c in claims if c["cid"] not in annotations]

    for c in claims:
        ann = annotations.get(c["cid"])
        if not ann:
            continue
        rel = (ann.get("relation") or "").strip()
        unmapped = bool(relations) and rel not in relations
        flags = sorted(set(as_list(ann.get("quality_flags")) +
                           (["relation_unmapped"] if unmapped else []) +
                           as_list(c.get("atomicity_flags"))))
        if flags:
            flags_summary.append({"cid": c["cid"], "flags": flags})
        records.append({
            "id": f"np-{case_id}-{len(records) + 1:03d}",
            "assertion": c["assertion_text"],
            "subject": ann.get("subject", ""),
            "relation": rel,
            "object": ann.get("object", ""),
            "direction": ann.get("direction", ""),
            "qualifiers": ann.get("qualifiers", {}) or {},
            "evidence": c["evidence"],
            "grounding": c.get("grounding", {}),
            "source": {
                "title": source.get("title", "not_reported"),
                "authors": source.get("authors", []),
                "year": source.get("year", "not_reported"),
                "venue": source.get("venue", "not_reported"),
                "doi": source.get("doi", "not_reported"),
                "version": source.get("version", "not_reported"),
                "identifier": source.get("identifier", source.get("doi", "not_reported")),
            },
            "confidence": ann.get("confidence"),
            "confidence_rationale": ann.get("confidence_rationale", ""),
            "quality_flags": flags,
            "section": c.get("section", ""),
        })

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    payload = {
        "case_id": case_id,
        "paper": bdoc.get("paper", {}),
        "assertion_count": len(records),
        "assertions": records,
        "sections": bdoc.get("sections", []),
        "generated_by": "scripts/build_nanopub.py",
    }
    (out / "assertions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    node = lambda r: {
        "@id": f"{r['id']}-assertion",
        "@type": "np:Assertion",
        "subject": {"@value": r["subject"]},
        "relation": {"@id": relations.get(r["relation"], {}).get("uri", r["relation"]),
                     "@value": r["relation"]} if r["relation"] else {"@value": ""},
        "object": {"@value": r["object"]},
        "assertionText": {"@value": r["assertion"]},
        "prov:wasDerivedFrom": {
            "@type": "np:Evidence",
            "quote": {"@value": r["evidence"]["quote"]},
            "page": {"@value": r["evidence"]["page"]},
            "section": {"@value": r["section"]},
            "evidenceType": {"@value": r["evidence"]["type"]},
        },
    }
    manifest = {
        "@context": CONTEXT["@context"],
        "@id": f"np-{case_id}-manifest",
        "@type": "np:Nanopublication",
        "assertion": [node(r) for r in records],
        "publicationinfo": {
            "case_id": case_id,
            "assertion_count": len(records),
            "source": source,
        },
    }
    (out / "assertions.jsonld").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out / "evidence.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "cid", "section", "page", "para", "sid", "evidence_type", "quote"])
        for r, c in zip(records, [c for c in claims if c["cid"] in annotations]):
            w.writerow([r["id"], c["cid"], r["section"], r["evidence"]["page"], r["evidence"]["para"],
                        r["evidence"]["sid"], r["evidence"]["type"], r["evidence"]["quote"]])

    gaps = {
        "unannotated_claims": [{"cid": c["cid"], "text": c["assertion_text"][:120]} for c in skipped],
        "bind_failures": bdoc.get("failures", []),
        "source_metadata_missing": [k for k in ("title", "authors", "year", "doi", "identifier")
                                    if source.get(k) in (None, "", "not_reported")],
        "note": "an unannotated claim stays in the paper, not in the export; saying so is better than dropping it silently",
    }
    (out / "gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    reasons: list[str] = []
    status = "success"
    if skipped:
        status = "partial"
        reasons.append(f"unannotated_claims: {len(skipped)}")
    if bdoc.get("failures"):
        status = "partial"
        reasons.append(f"bind_failures: {len(bdoc['failures'])}")
    if gaps["source_metadata_missing"]:
        if status == "success":
            status = "partial"
        reasons.append("source_metadata_missing: " + ",".join(gaps["source_metadata_missing"]))
    if not records:
        status = "unable"
        reasons.append("no_annotated_claims")

    result = {
        "case_id": case_id,
        "output_contract": {k: (fill.get("result") or {}).get(k, None) for k in contract} if contract else
                           (fill.get("result") or {}),
        "status": status,
        "status_reasons": reasons,
        "sources": [{"title": source.get("title", "not_reported"),
                     "year": source.get("year", "not_reported"),
                     "doi": source.get("doi", "not_reported"),
                     "extractor": sdoc.get("paper", {}).get("extractor", "unknown"),
                     "pages": sdoc.get("paper", {}).get("pages")}],
        "uncertainty": (
            [{"kind": "unannotated_claim", "detail": c["assertion_text"][:120],
              "evidence": f"{c['evidence']['page']}"} for c in skipped]
            + [{"kind": "bind_failure", "detail": f["reason"], "evidence": f.get("quote", "")[:100]}
               for f in bdoc.get("failures", [])]
            + [{"kind": "source_metadata_missing", "detail": k, "evidence": "not_reported"}
               for k in gaps["source_metadata_missing"]]
            + [{"kind": "quality_flag", "detail": ",".join(f["flags"]), "evidence": f["cid"]}
               for f in flags_summary]
        ),
        "change_log": [
            {"step": "paper_to_sentences", "detail": f"{sdoc.get('stats',{}).get('sentences',0)} sentences"},
            {"step": "split_claims", "detail": f"{bdoc.get('stats',{}).get('candidates_in',0)} candidates"},
            {"step": "bind_evidence", "detail": f"{bdoc.get('stats',{}).get('bound',0)} bound, "
                                               f"{bdoc.get('stats',{}).get('failed',0)} failed"},
            {"step": "build_nanopub", "detail": f"{len(records)} records"},
        ],
        "files": {"assertions": "assertions.json", "jsonld": "assertions.jsonld", "evidence": "evidence.csv"},
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"status": status, "out": str(out), "records": len(records),
                      "reasons": reasons, "flagged": len(flags_summary)}, ensure_ascii=False))
    if args.strict and not records:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
