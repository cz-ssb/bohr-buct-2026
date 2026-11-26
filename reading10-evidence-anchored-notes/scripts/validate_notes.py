#!/usr/bin/env python3
"""Self-check for the structured-reading-notes skill.

Fails loudly on the things that cost review points: an anchor that does not exist,
a quote that is not on its page, a claimed field with no evidence, a missing
result.json contract field, or resource files outside the platform limits.

Usage:
  python validate_notes.py --dir app/output --pages work/pages.json [--strict]
Exit codes: 0 clean, 1 violations (with --strict), 2 inputs unusable.
"""
import argparse, json, sys
from pathlib import Path

FIELD_ORDER = ["research_question", "data", "method_conditions", "main_findings", "limitations"]
STATUSES = {"reported", "not_reported", "uncertain", "conflict"}
RUN_STATUSES = {"success", "partial", "unable", "refused"}
MAX_FILES, MAX_EACH, MAX_TOTAL = 50, 500 * 1024, 2 * 1024 * 1024


def norm(s):
    return " ".join(str(s or "").split())


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def collect_ids(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "anchor_id" and isinstance(v, str):
                out.add(v)
            elif k == "evidence" and isinstance(v, list):
                out.update(x for x in v if isinstance(x, str))
            collect_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids(v, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skill-root", default="")
    a = ap.parse_args()

    outdir, v = Path(a.dir), []
    anchors_path, card_path, notes_path, result_path = (outdir / "anchors.json", outdir / "paper_card.json",
                                                        outdir / "notes.json", outdir / "result.json")
    missing = [p.name for p in (anchors_path, card_path, notes_path, result_path) if not p.exists()]
    if missing:
        print(json.dumps({"ok": False, "violations": [{"code": "missing_output", "detail": ",".join(missing)}]},
                         ensure_ascii=False))
        return 2

    pages = {p["page"]: norm(p["text"]) for p in load(a.pages)["pages"]}
    anchors = load(anchors_path)["anchors"]
    ids = {x["anchor_id"] for x in anchors}
    if len(ids) != len(anchors):
        v.append({"code": "duplicate_anchor_id", "detail": f"{len(anchors) - len(ids)} duplicated"})
    if not anchors:
        v.append({"code": "no_anchors", "detail": "the paper produced zero anchors"})

    for x in anchors:
        page_text = pages.get(x["page"])
        if page_text is None:
            v.append({"code": "anchor_page_missing", "detail": x["anchor_id"]})
        elif norm(x["quote"]) not in page_text:
            v.append({"code": "quote_not_on_page", "detail": f"{x['anchor_id']} p.{x['page']}"})

    used = set()
    collect_ids(load(card_path), used)
    collect_ids(load(notes_path), used)
    for aid in sorted(used - ids):
        v.append({"code": "anchor_not_in_whitelist", "detail": aid})

    # a semantic fill kept next to the outputs is checked too, so an invented
    # anchor cannot survive by hiding in the fill file
    fill_path = outdir / "semantic_fill.json"
    if fill_path.exists():
        try:
            fill_used = set()
            collect_ids(load(fill_path), fill_used)
            for aid in sorted(fill_used - ids):
                v.append({"code": "fill_anchor_not_in_whitelist", "detail": aid})
        except Exception as e:
            v.append({"code": "fill_unreadable", "detail": type(e).__name__})

    card = load(card_path)["fields"]
    for f in FIELD_ORDER:
        if f not in card:
            v.append({"code": "card_field_missing", "detail": f})
            continue
        entry = card[f]
        if entry.get("status") not in STATUSES:
            v.append({"code": "card_status_invalid", "detail": f"{f}={entry.get('status')}"})
        if entry.get("status") == "reported" and not entry.get("evidence"):
            v.append({"code": "claimed_without_evidence", "detail": f})
        if entry.get("status") == "reported" and not entry.get("value"):
            v.append({"code": "claimed_without_value", "detail": f})

    res = load(result_path)
    if not res.get("case_id"):
        v.append({"code": "result_case_id_missing", "detail": "case_id is null"})
    if res.get("status") not in RUN_STATUSES:
        v.append({"code": "result_status_invalid", "detail": str(res.get("status"))})
    for k in ("sources", "uncertainty", "change_log"):
        if k not in res:
            v.append({"code": "result_key_missing", "detail": k})
    if res.get("status") != "success" and not res.get("status_reason"):
        v.append({"code": "status_reason_missing", "detail": "non-success run must say why"})
    for k, val in res.items():
        if val is None and k not in ("case_id", "status_reason"):
            v.append({"code": "contract_field_empty", "detail": k})

    root = Path(a.skill_root) if a.skill_root else outdir
    text_files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                  (".md", ".txt", ".json", ".py", ".csv", ".yaml", ".yml", ".toml", ".jsonl")]
    if len(text_files) > MAX_FILES:
        v.append({"code": "too_many_files", "detail": str(len(text_files))})
    big = [str(p) for p in text_files if p.stat().st_size > MAX_EACH]
    if big:
        v.append({"code": "file_too_large", "detail": ",".join(big[:3])})
    total = sum(p.stat().st_size for p in text_files)
    if total > MAX_TOTAL:
        v.append({"code": "total_too_large", "detail": str(total)})
    if any(p.is_symlink() for p in root.rglob("*")):
        v.append({"code": "symlink_present", "detail": str(root)})

    ok = not v
    print(json.dumps({"ok": ok, "checked": {"anchors": len(anchors), "referenced": len(used),
                                            "text_files": len(text_files), "total_bytes": total},
                      "violations": v}, ensure_ascii=False, indent=2))
    if not ok and a.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
