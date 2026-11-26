#!/usr/bin/env python3
"""One-command self-test for the structured-reading-notes skill.

Runs the whole pipeline on a synthetic paper, then deliberately breaks things
(invented anchor, fabricated quote) to prove the checks actually fire.

Usage:
  python selftest/run_selftest.py [--work /tmp/reading10-selftest]

Exit codes: 0 all checks behaved as expected, 1 something did not.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"

CASE = {
    "case_id": "ST-READING10-01",
    "output_contract": {
        "notes_markdown": "notes.md",
        "paper_card": "paper_card.json",
        "evidence_table": "evidence.csv",
        "anchors": "anchors.json",
    },
}

# semantic fill used by the self-test; every anchor_id must exist in anchors.json
FILL = {
    "fields": {
        "research_question": {"value": "稀疏注意力预算是否保住长文检索精度，损失集中在哪类问题",
                              "anchor_id": "a-s1-1", "status": "reported"},
        "data": {"value": "三个长文基准各 500 题，共 1500 题", "anchor_id": "a-s5-2",
                 "status": "reported"},
        "method_conditions": {"value": "冻结权重、仅换推理期掩码；每层预算为序列长度 12.5%",
                              "anchor_id": "a-s4-2", "status": "reported"},
        "main_findings": {"value": "全注意力 71.8%，12.5% 预算 68.4%，降 3.4 点；多跳题降 6.1 点",
                          "anchor_id": "a-s6-3", "status": "reported"},
        "limitations": {"value": "路由器在合成文档上训练，领域迁移未测",
                        "anchor_id": "a-s7-3", "status": "reported"},
    },
    "sections": {
        "S1": {"purpose": {"text": "界定研究问题：稀疏预算在哪种题型上真正丢失信息",
                           "anchor_id": "a-s1-1"}},
        "S6": {"result": {"text": "12.5% 预算 68.4%，比全注意力低 3.4 点",
                          "anchor_id": "a-s6-2"}},
    },
    "result": CASE["output_contract"],
}

BAD_FILL = {"fields": {"main_findings": {"value": "编造的数字 99.9%",
                                         "anchor_id": "a-s9-99"}}}


def run(args, expect=0, label=""):
    proc = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    ok = proc.returncode == expect
    out = (proc.stdout or "").strip().splitlines()
    tail = out[-1] if out else (proc.stderr or "").strip().splitlines()[-1:] or ""
    print(f"  [{'OK' if ok else 'FAIL'}] {label}: exit={proc.returncode} (expected {expect}) "
          f"{(str(tail)[:150])}")
    return ok, proc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="reading10-selftest-"))
    work.mkdir(parents=True, exist_ok=True)

    results = []
    print(f"work dir: {work}")

    pdf = work / "test_paper.pdf"
    results.append(run([str(HERE / "gen_test_paper.py"), str(pdf)], 0, "generate synthetic paper")[0])

    pages = work / "pages.json"
    results.append(run([str(SCRIPTS / "pdf_to_pages.py"), "--input", str(pdf),
                        "--out", str(pages), "--ocr", "off"], 0, "extract page text")[0])

    cj = work / "case.json"
    cj.write_text(json.dumps(CASE, ensure_ascii=False, indent=2), encoding="utf-8")

    outdir = work / "out"
    ok, proc = run([str(SCRIPTS / "build_notes.py"), "--pages", str(pages), "--out", str(outdir),
                    "--paper", str(pdf), "--case-json", str(cj)], 0, "build structure")
    results.append(ok)
    if ok:
        stats = json.loads(proc.stdout.strip().splitlines()[-1])
        # section alignment is the point of the skill: a flat extract once collapsed
        # every section into one, so fewer than 5 sections means the cut is broken
        sec_ok = stats.get("sections", 0) >= 5
        print(f"  [{'OK' if sec_ok else 'FAIL'}] sections detected: {stats.get('sections')} (>=5)")
        results.append(sec_ok)

    fill = work / "semantic_fill.json"
    fill.write_text(json.dumps(FILL, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run([str(SCRIPTS / "build_notes.py"), "--pages", str(pages), "--out", str(outdir),
                        "--paper", str(pdf), "--case-json", str(cj), "--fill", str(fill)],
                       0, "build + merge semantic fill")[0])

    results.append(run([str(SCRIPTS / "validate_notes.py"), "--dir", str(outdir), "--pages", str(pages),
                        "--strict", "--skill-root", str(ROOT)], 0, "self-check clean run")[0])

    bad = work / "bad_fill.json"
    bad.write_text(json.dumps(BAD_FILL, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, proc = run([str(SCRIPTS / "build_notes.py"), "--pages", str(pages), "--out", str(outdir),
                    "--paper", str(pdf), "--case-json", str(cj), "--fill", str(bad)],
                   4, "invented anchor rejected")
    results.append(ok and "fill_anchor_invalid" in (proc.stdout or ""))

    adoc = json.loads((outdir / "anchors.json").read_text(encoding="utf-8"))
    adoc["anchors"][4]["quote"] = "这句话在原文里根本不存在 fabricated sentence"
    (outdir / "anchors.json").write_text(json.dumps(adoc, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, proc = run([str(SCRIPTS / "validate_notes.py"), "--dir", str(outdir), "--pages", str(pages),
                    "--strict", "--skill-root", str(ROOT)], 1, "fabricated quote rejected")
    results.append(ok and "quote_not_on_page" in (proc.stdout or ""))

    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} checks behaved as expected")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
