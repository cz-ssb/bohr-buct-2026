#!/usr/bin/env python3
"""Render the chapter from structured evidence, and refuse unsupported numbers.

The model writes only the semantic layer (`semantic_fill.json`): step wording,
dataset narrative, control reasoning, limitations. Every number it wants to
mention must already exist in `params_raw.json` with a source address; anything
else is rejected rather than smoothed into prose.

Usage:
  python scripts/build_methods.py --blocks work/evidence_blocks.json \
      --params work/params_raw.json --out out/ --case-json case.json
  python scripts/build_methods.py ... --fill out/semantic_fill.json   # merge pass
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SECTIONS = [
    ("steps", "1. Method steps", "ordered, each with input / operation / output / decision"),
    ("settings", "2. Experimental setup", "hardware, software, environment, seeds, repetitions"),
    ("params", "3. Parameters", "name, value, unit, target, and the source address"),
    ("datasets", "4. Datasets and splits", "name, version, scale, preprocessing, split, use of each subset"),
    ("controls", "5. Controls and comparisons", "baseline identity, budget parity, metric, statistics"),
    ("repro", "6. Reproducibility checklist", "code version, environment, commands, data access, seeds"),
    ("limitations", "7. Limitations and scope", "each limitation tied to a concrete failure scenario"),
    ("gaps", "8. Open items for author confirmation", "missing, conflicting, or unconfirmed material"),
]

REQUIRED_BLOCKS = ("steps", "settings", "datasets", "controls", "repro", "limitations")

ALIAS_RE = re.compile(
    r"(?i)(learning rate|lr|batch size|batch_size|epochs?|max steps|seed|weight decay|weight_decay|"
    r"momentum|optimizer|scheduler|warmup|train split|val split|test split|train ratio|gpus?|device|"
    r"precision|fp16|image size|resolution|max length|max_len|layers|hidden size|heads|dropout|"
    r"grad clip|patience|temperature|top_k|repeats|runs|dataset version|python|torch|cuda)"
)
NUM_RE = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?")
SENT_SPLIT = re.compile(r"[。；;!?！？]|\n")


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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


def fmt_num(v) -> str:
    if v is None:
        return "not reported"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def as_list(value) -> list:
    """A single reference written as a bare string is still a single reference."""
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def check_numbers(text: str, params: list[dict]) -> list[dict]:
    """Flag a number that sits next to a parameter name but is not that param's value."""
    known = set()
    for p in params:
        if p.get("value_raw"):
            known.add(str(p["value_raw"]).strip())
        if p.get("value_num") is not None:
            n = p["value_num"]
            known.add(fmt_num(n))
            known.add(str(n))
    problems = []
    for raw_sentence in SENT_SPLIT.split(text):
        s = raw_sentence.strip()
        if not s or not ALIAS_RE.search(s):
            continue
        for m in NUM_RE.finditer(s):
            tok = m.group(0)
            if tok in known:
                continue
            # structural numerals that carry no measured value
            if re.fullmatch(r"(19|20)\d{2}", tok):
                continue
            if len(tok) <= 2 and tok.isdigit() and int(tok) <= 12:
                continue
            problems.append({
                "value": tok,
                "context": s[:160],
                "reason": "number_near_parameter_name_without_table_entry",
            })
    return problems


def render(params: list[dict], fill: dict, case_id: str, contract: list[str]) -> tuple[str, dict]:
    p_by_id = {p["param_id"]: p for p in params}

    def cite(refs) -> str:
        refs = as_list(refs)
        if not refs:
            return ""
        bits = []
        for r in refs:
            p = p_by_id.get(r)
            if p:
                bits.append(f"[{p['param_id']} {p['source']}]")
            else:
                bits.append(f"[{r} UNRESOLVED]")
        return " " + " ".join(bits)

    def ev(items) -> str:
        items = as_list(items)
        return (" ^" + ",".join(str(i) for i in items)) if items else ""

    lines: list[str] = []
    lines.append(f"# Methods and experiments — {case_id}")
    lines.append("")
    lines.append("This chapter states only what the materials support. Every numeric value names its source;")
    lines.append("anything the materials do not settle is listed in section 8 instead of being filled in.")
    lines.append("")

    gaps = fill.get("gaps") or []

    # 1 steps
    lines.append(f"## {SECTIONS[0][1]}")
    lines.append("")
    steps = fill.get("steps") or []
    if steps:
        for i, st in enumerate(steps, 1):
            head = st.get("name") or f"Step {i}"
            lines.append(f"**{i}. {head}**" + cite(st.get("param_refs")) + ev(st.get("evidence")))
            for key, label in (("input", "Input"), ("operation", "Operation"),
                               ("output", "Output"), ("decision", "Decision condition")):
                if st.get(key):
                    lines.append(f"- {label}: {st[key]}")
            if st.get("note"):
                lines.append(f"- Note: {st['note']}")
            lines.append("")
    else:
        lines.append("_Not supplied in the semantic layer; see section 8._")
        lines.append("")

    # 2 settings
    lines.append(f"## {SECTIONS[1][1]}")
    lines.append("")
    settings = fill.get("settings") or []
    if settings:
        lines.append("| Aspect | Condition | Source |")
        lines.append("|---|---|---|")
        for s in settings:
            lines.append(f"| {s.get('aspect','-')} | {s.get('text','-')} | {s.get('source','see section 3')} |")
    else:
        lines.append("_Not supplied in the semantic layer; see section 8._")
    lines.append("")

    # 3 params
    lines.append(f"## {SECTIONS[2][1]}")
    lines.append("")
    if params:
        lines.append("| ID | Name | Value | Unit | Target | Source | Status |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in params:
            lines.append(
                f"| {p['param_id']} | {p['name']} | {fmt_num(p['value_num']) if p['value_num'] is not None else p['value_raw']} "
                f"| {p['unit'] or '-'} | {p['target']} | `{p['source']}` | {p['status']} |")
    else:
        lines.append("_No parameter could be extracted. That is a gap, not a licence to invent values._")
    lines.append("")

    # 4 datasets
    lines.append(f"## {SECTIONS[3][1]}")
    lines.append("")
    datasets = fill.get("datasets") or []
    if datasets:
        for d in datasets:
            lines.append(f"- **{d.get('name','dataset')}** — version: {d.get('version','not reported')}; "
                         f"scale: {d.get('scale','not reported')}; preprocessing: {d.get('preprocess','not reported')}"
                         + cite(d.get("param_refs")) + ev(d.get("evidence")))
            if d.get("split"):
                lines.append(f"  - split: {d['split']}")
            if d.get("uses"):
                lines.append(f"  - subsets used for: {d['uses']}")
        lines.append("")
    else:
        lines.append("_Not supplied in the semantic layer; see section 8._")
        lines.append("")

    # 5 controls
    lines.append(f"## {SECTIONS[4][1]}")
    lines.append("")
    controls = fill.get("controls") or []
    if controls:
        for c in controls:
            lines.append(f"- baseline **{c.get('baseline','not reported')}** "
                         f"(version: {c.get('baseline_version','not reported')}); "
                         f"budget parity: {c.get('budget_parity','not reported')}; "
                         f"metric: {c.get('metric','not reported')}; statistics: {c.get('statistics','not reported')}"
                         + cite(c.get("param_refs")) + ev(c.get("evidence")))
        lines.append("")
    else:
        lines.append("_No comparison is claimed, so no comparison is written._")
        lines.append("")

    # 6 repro
    lines.append(f"## {SECTIONS[5][1]}")
    lines.append("")
    repro = fill.get("repro") or []
    if repro:
        lines.append("| Item | Value | Evidence |")
        lines.append("|---|---|---|")
        for r in repro:
            lines.append(f"| {r.get('item','-')} | {r.get('value','not reported')} | {r.get('evidence','-')} |")
    else:
        lines.append("_Reproduction checklist empty — treat the chapter as non-reproducible until section 8 is resolved._")
    lines.append("")

    # 7 limitations
    lines.append(f"## {SECTIONS[6][1]}")
    lines.append("")
    limitations = fill.get("limitations") or []
    if limitations:
        for l in limitations:
            lines.append(f"- **{l.get('claim','effect asserted')}** — fails when: {l.get('failure_scenario','not stated')}; "
                         f"scope: {l.get('scope','not stated')}" + ev(l.get("evidence")))
    else:
        lines.append("_No limitation written. A chapter without limitations overstates its scope._")
    lines.append("")

    # 8 gaps
    lines.append(f"## {SECTIONS[7][1]}")
    lines.append("")
    if gaps:
        lines.append("| Kind | Item | Question for the author | Evidence |")
        lines.append("|---|---|---|---|")
        for g in gaps:
            lines.append(f"| {g.get('kind','missing')} | {g.get('item','-')} | {g.get('question','please confirm')} "
                         f"| {g.get('evidence','-')} |")
    else:
        lines.append("_No gap recorded. This is only defensible if every one of the six element groups was answered from the materials._")
    lines.append("")

    coverage = {k: len(fill.get(k) or []) for k in REQUIRED_BLOCKS}
    coverage["gaps"] = len(gaps)
    return "\n".join(lines) + "\n", coverage


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--case-json")
    ap.add_argument("--fill")
    ap.add_argument("--case-id")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    blocks_doc = json.loads(Path(args.blocks).read_text(encoding="utf-8"))
    params_doc = json.loads(Path(args.params).read_text(encoding="utf-8"))
    params = params_doc.get("params", [])
    conflicts = params_doc.get("conflicts", [])
    blocks = blocks_doc.get("blocks", [])
    block_ids = {b["block_id"] for b in blocks}

    case = load_json(args.case_json)
    case_id = args.case_id or case.get("case_id") or case.get("id") or "case"
    contract = contract_fields(case)

    fill = load_json(args.fill)
    fill_errors: list[dict] = []

    # validate references before rendering anything
    valid_param_ids = {p["param_id"] for p in params}
    path_set = {b["path"] for b in blocks}


    for group in ("steps", "settings", "datasets", "controls", "limitations", "repro"):
        for item in fill.get(group) or []:
            for ref in as_list(item.get("param_refs")):
                if ref not in valid_param_ids:
                    fill_errors.append({"type": "unknown_param_ref", "field": group,
                                        "ref": ref, "item": item.get("name") or item.get("item") or item.get("aspect")})
            for e in as_list(item.get("evidence")):
                if str(e) not in block_ids and str(e) not in path_set and str(e) != "derived":
                    fill_errors.append({"type": "unknown_evidence_block", "field": group, "ref": str(e)})

    if fill_errors:
        print(json.dumps({"status": "rejected", "errors": fill_errors},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 4

    text, coverage = render(params, fill, case_id, contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "methods.md").write_text(text, encoding="utf-8")

    write_csv(out / "parameters.csv",
              ["param_id", "name", "value_raw", "value_num", "unit", "target", "source", "status", "occurrences"],
              [[p["param_id"], p["name"], p["value_raw"], "" if p["value_num"] is None else p["value_num"],
                p["unit"], p["target"], p["source"], p["status"], p["occurrences"]] for p in params])

    used = set()
    for g in ("steps", "settings", "datasets", "controls", "limitations", "repro"):
        for item in fill.get(g) or []:
            for e in item.get("evidence") or []:
                used.add(str(e))
    write_csv(out / "evidence.csv",
              ["block_id", "path", "line_start", "line_end", "kind", "chars", "cited_in_chapter"],
              [[b["block_id"], b["path"], b["line_start"], b["line_end"], b["kind"], b["chars"],
                "yes" if b["block_id"] in used else "no"] for b in blocks])

    gaps = {
        "gaps": fill.get("gaps") or [],
        "conflicts_from_materials": conflicts,
        "schema_names_absent": params_doc.get("coverage", {}).get("schema_names_absent", []),
        "note": "kind is one of missing | conflict | needs_confirmation; a gap is never resolved by prose",
    }
    (out / "gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    # The parameter table is the register of truth; prose is what gets checked
    # against it, so table rows themselves are excluded from the number scan.
    body_only = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("|"))
    num_problems = check_numbers(body_only, params)

    status = "success"
    reasons = []
    if coverage and any(coverage.get(k, 0) == 0 for k in REQUIRED_BLOCKS):
        status = "partial"
        reasons.append("required_element_group_empty: " +
                       ",".join(k for k in REQUIRED_BLOCKS if coverage.get(k, 0) == 0))
    if gaps["conflicts_from_materials"]:
        status = "partial"
        reasons.append(f"material_conflicts: {len(gaps['conflicts_from_materials'])}")
    if num_problems:
        status = "partial"
        reasons.append(f"unsupported_numbers: {len(num_problems)}")

    result = {
        "case_id": case_id,
        "output_contract": {k: (fill.get("result") or {}).get(k, None) for k in contract} if contract else
                           (fill.get("result") or {}),
        "status": status,
        "status_reasons": reasons,
        "sources": [
            {"path": f["path"], "kind": f["kind"], "lines": f["lines"]} for f in blocks_doc.get("files", [])
        ],
        "uncertainty": (
            [{"kind": "material_gap", "detail": f"{g['item']}: {g.get('question','confirm with author')}",
              "evidence": g.get("evidence", "n/a")} for g in gaps["gaps"]]
            + [{"kind": "material_conflict", "detail": f"{c['name']} = {' / '.join(c['values'])}",
                "evidence": ", ".join(c["sources"])} for c in gaps["conflicts_from_materials"]]
            + [{"kind": "unsupported_number", "detail": p["value"], "evidence": p["context"]} for p in num_problems]
            + [{"kind": "absent_parameter", "detail": n, "evidence": "not found in materials"}
               for n in gaps["schema_names_absent"]]
        ),
        "change_log": [
            {"step": "collect_materials", "detail": f"{blocks_doc.get('stats',{}).get('files_read',0)} files, "
                                                    f"{len(blocks)} blocks"},
            {"step": "extract_params", "detail": f"{len(params)} parameters, {len(conflicts)} conflicts"},
            {"step": "build_methods", "detail": f"coverage {coverage}"},
        ],
        "files": {"chapter": "methods.md", "parameters": "parameters.csv",
                  "evidence": "evidence.csv", "gaps": "gaps.json"},
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {"status": status, "out": str(out), "params": len(params),
               "coverage": coverage, "unsupported_numbers": len(num_problems),
               "conflicts": len(conflicts), "reasons": reasons}
    print(json.dumps(summary, ensure_ascii=False))
    if args.strict and (num_problems or fill_errors):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
