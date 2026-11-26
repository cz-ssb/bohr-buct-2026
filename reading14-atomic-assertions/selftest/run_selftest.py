#!/usr/bin/env python3
"""One command that runs the reading pipeline and proves its checks fire.

The happy path shows that a paper becomes records with addresses. Four injected
faults then show that the validator notices a rewritten assertion, an unmapped
relation, an altered quote, and a duplicate record — because a check nobody has
seen fail is a check nobody should trust.

Usage:  python selftest/run_selftest.py
Exit:   0 all expectations held, 1 at least one did not.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix="nanopub-selftest-"))

VERB = set("""
is are was were has have had does do did can may might will would could should
shows show reported reports reaches reach improved improves improve reduces
reduce reduced increases increase decreased decreases achieves achieve
outperforms requires require uses use enables enable causes caused remains
remain converges converge disappears disappear holds hold fails fail stops stop
trains train describes describe tests test matters matter suggests suggest
measured measure evaluated evaluate provides provide gives give yields yield
exceeds exceed drops drop rises rise keeps keep preserves preserve maintains
""".split())

REL_BY_TEXT = [
    ("outperform", "outperforms"), ("better", "outperforms"), ("improv", "increases"),
    ("increase", "increases"), ("reduce", "decreases"), ("decrease", "decreases"),
    ("lower", "decreases"), ("higher", "increases"), ("disappear", "decreases"),
    ("because", "causes"), ("therefore", "causes"), ("require", "requires"),
    ("use", "uses"), ("suggest", "supports"),
]


def run(script: str, *args: str) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def guess_relation(text: str) -> str:
    low = text.lower()
    for needle, relation in REL_BY_TEXT:
        if needle in low:
            return relation
    return "supports"


def split_subject_object(text: str) -> tuple[str, str]:
    words = text.split()
    idx = None
    for i, w in enumerate(words):
        if w.strip(",.;:").lower() in VERB:
            idx = i
            break
    if idx is None or idx == 0:
        return " ".join(words[:5]).strip(",."), "not_stated"
    subject = " ".join(words[:idx]).strip(",.") or " ".join(words[:3])
    obj = " ".join(words[idx + 1:]) or "not_stated"
    return subject[:90], obj[:110].strip(",.")


def build_fill(bound: dict) -> dict:
    assertions = []
    for c in bound["claims"]:
        ev = c["evidence"]
        text = c["assertion_text"]
        subject, obj = split_subject_object(text)
        relation = guess_relation(text)
        hedged = c["grounding"].get("hedged")
        numbers = c["grounding"].get("numbers") or []
        conf = 0.85 if ev["type"] == "direct" else 0.6
        if hedged:
            conf -= 0.15
        if len(numbers) >= 2:
            conf -= 0.05
        rationale = ("the quote carries the reported quantity itself"
                     if ev["type"] == "direct" else
                     "the quote supports the claim only together with its surrounding sentence")
        if hedged:
            rationale += "; the source hedges the claim, so confidence follows the hedge rather than the text"
        flags = list(c.get("atomicity_flags") or [])
        if hedged:
            flags.append("claim_hedged_in_source")
        assertions.append({
            "cid": c["cid"],
            "subject": subject,
            "relation": relation,
            "object": obj,
            "direction": "subject_to_object",
            "qualifiers": {
                "section": c.get("section", ""),
                "page": ev["page"],
                "scope": "as stated in the quoted sentence",
            },
            "confidence": round(max(0.2, min(0.98, conf)), 2),
            "confidence_rationale": rationale,
            "quality_flags": flags,
        })
    return {
        "source": {
            "title": "Sparse Expert Routing Under a Fixed Compute Budget (synthetic fixture)",
            "authors": ["Fixture Author"],
            "year": 2026,
            "venue": "synthetic fixture, not a real publication",
            "doi": "10.0000/fixture.synthetic",
            "version": "v1",
            "identifier": "10.0000/fixture.synthetic",
        },
        "assertions": assertions,
        "result": {"assertions": "assertions.json", "jsonld": "assertions.jsonld",
                   "evidence": "evidence.csv", "status": "see result.json"},
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    fixture = WORK / "fixture"
    p = subprocess.run([sys.executable, str(ROOT / "selftest" / "make_fixture.py"),
                        "--root", str(fixture)], capture_output=True, text=True, encoding="utf-8")
    check("fixture built", p.returncode == 0, p.stderr.strip()[:200])
    paper = fixture / "paper.txt"

    sdoc_path = WORK / "sentences.json"
    rc, so, se = run("paper_to_sentences.py", "--input", str(paper), "--out", str(sdoc_path))
    sdoc = load(sdoc_path) if sdoc_path.exists() else {}
    stats = sdoc.get("stats", {})
    check("sentences: ok", rc == 0 and stats.get("sentences", 0) >= 15, str(stats))
    check("sentences: sections found", stats.get("sections", 0) >= 5, str(stats.get("sections")))
    check("sentences: three pages kept", sdoc.get("paper", {}).get("pages") == 3,
          str(sdoc.get("paper", {}).get("pages")))

    sec_page = {s["title"]: s["start_page"] for s in sdoc.get("sections", [])}
    method_page = next((v for k, v in sec_page.items() if "Method" in k and "Methodolog" not in k
                        and "Materials" not in k), None)
    results_page = next((v for k, v in sec_page.items() if "Result" in k), None)
    check("sentences: section pages are right", method_page == 1 and results_page == 2,
          f"method p.{method_page} results p.{results_page}")

    cdoc_path = WORK / "candidates.json"
    rc, so, se = run("split_claims.py", "--sentences", str(sdoc_path), "--out", str(cdoc_path))
    cdoc = load(cdoc_path) if cdoc_path.exists() else {}
    cstats = cdoc.get("stats", {})
    check("claims: candidates produced", rc == 0 and cstats.get("candidates", 0) >= 15, str(cstats))
    check("claims: sentences actually split", cstats.get("split_sentences", 0) >= 4,
          str(cstats.get("split_sentences")))

    dangling = [c["text"] for c in cdoc.get("candidates", [])
                if c["text"].rstrip().endswith((" and", " but", " whereas", " while", ",", ";"))]
    check("claims: no dangling conjunction left", not dangling, str(dangling[:2])[:160])

    fragments = [c["text"] for c in cdoc.get("candidates", [])
                 if c["text"][:1].islower() and not re.match(r"(we|it|they|this|these|the|a|an|our|their)\b",
                                                             c["text"], re.I)]
    check("claims: no verbless lowercase fragment", not fragments, str(fragments[:2])[:160])

    bdoc_path = WORK / "bound.json"
    rc, so, se = run("bind_evidence.py", "--sentences", str(sdoc_path),
                     "--candidates", str(cdoc_path), "--out", str(bdoc_path),
                     "--evidence-csv", str(WORK / "evidence.csv"))
    bdoc = load(bdoc_path) if bdoc_path.exists() else {}
    bstats = bdoc.get("stats", {})
    check("evidence: everything bound", rc == 0 and bstats.get("failed", 1) == 0
          and bstats.get("bound") == bstats.get("candidates_in"), str(bstats))
    check("evidence: direct majority for numeric claims", bstats.get("direct", 0) >= 8,
          str(bstats.get("direct")))

    pages_text = {}
    for s in sdoc.get("sentences", []):
        pages_text[int(s["page"])] = pages_text.get(int(s["page"]), "") + " " + s["text"]
    bad_quotes = [c["cid"] for c in bdoc.get("claims", [])
                  if c["evidence"]["quote"] not in pages_text.get(int(c["evidence"]["page"]), "")]
    check("evidence: every quote occurs on its page", not bad_quotes, str(bad_quotes[:3]))

    fill = WORK / "fill.json"
    fill.write_text(json.dumps(build_fill(bdoc), ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "out"
    rc, so, se = run("build_nanopub.py", "--sentences", str(sdoc_path), "--bound", str(bdoc_path),
                     "--out", str(out), "--case-json", str(fixture / "case.json"), "--fill", str(fill),
                     "--relations", str(ROOT / "references" / "relations.json"))
    b = json.loads(so) if so.strip().startswith("{") else {}
    check("export: ran", rc == 0 and b.get("records", 0) >= 15, f"{b} {se.strip()[:120]}")
    rdoc = load(out / "assertions.json")
    ld = load(out / "assertions.jsonld")
    check("export: jsonld mirrors records", len(ld.get("assertion", [])) == len(rdoc.get("assertions", [])),
          f"{len(ld.get('assertion', []))} vs {len(rdoc.get('assertions', []))}")

    rc, so, se = run("validate_nanopub.py", "--dir", str(out), "--sentences", str(sdoc_path),
                     "--relations", str(ROOT / "references" / "relations.json"),
                     "--strict", "--skill-root", str(ROOT))
    v = json.loads(so) if so.strip().startswith("{") else {}
    check("validate: clean export has no violations", rc == 0 and v.get("status") == "ok",
          json.dumps(v.get("violations", [])[:3], ensure_ascii=False))

    def tampered(name: str, mutate) -> tuple[int, set[str]]:
        copy = WORK / name
        if copy.exists():
            shutil.rmtree(copy)
        shutil.copytree(out, copy)
        doc = load(copy / "assertions.json")
        mutate(doc)
        (copy / "assertions.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rc, so, se = run("validate_nanopub.py", "--dir", str(copy), "--sentences", str(sdoc_path),
                         "--relations", str(ROOT / "references" / "relations.json"),
                         "--strict", "--skill-root", str(ROOT))
        vv = json.loads(so) if so.strip().startswith("{") else {}
        return rc, {x["type"] for x in vv.get("violations", [])}

    # fault A: assertion rewritten into a claim the paper never makes
    def rewrite(doc):
        doc["assertions"][0]["assertion"] = "Sparse routing doubles inference cost on every dataset tested."
    rc, types = tampered("out_rewrite", rewrite)
    check("fault A: rewritten assertion rejected", rc == 1 and "assertion_not_in_source" in types, str(sorted(types)))

    # fault B: free-text relation with no flag
    def unmap(doc):
        doc["assertions"][1]["relation"] = "somewhat_relates_to"
        doc["assertions"][1]["quality_flags"] = []
    rc, types = tampered("out_relation", unmap)
    check("fault B: unmapped relation rejected", rc == 1 and "relation_not_controlled" in types, str(sorted(types)))

    # fault C: one character changed inside the quote
    def alter_quote(doc):
        ev = doc["assertions"][2]["evidence"]
        ev["quote"] = ev["quote"].replace("71.8", "71.9") if "71.8" in ev["quote"] else ev["quote"] + " x"
    rc, types = tampered("out_quote", alter_quote)
    check("fault C: altered quote rejected", rc == 1 and "quote_not_on_page" in types, str(sorted(types)))

    # fault D: the same assertion exported twice
    def duplicate(doc):
        doc["assertions"].append(dict(doc["assertions"][3]))
    rc, types = tampered("out_duplicate", duplicate)
    check("fault D: duplicate assertion rejected", rc == 1 and "duplicate_assertion" in types, str(sorted(types)))

    # a stub PDF has no text layer: extraction must say so instead of inventing text
    rc, so, se = run("paper_to_sentences.py", "--input", str(fixture / "paper_scan.pdf"),
                     "--out", str(WORK / "scan.json"))
    check("scanned pdf: reported unable, not faked", rc != 0 and "unable" in (so + se),
          (so + se).strip()[:140])

    width = max(len(c[0]) for c in checks)
    passed = 0
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail if not ok else ''}")
        passed += 1 if ok else 0
    print(f"\n{passed}/{len(checks)} checks behaved as expected")
    print(f"artefacts kept for inspection: {WORK}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
