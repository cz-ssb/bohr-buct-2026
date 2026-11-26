#!/usr/bin/env python3
"""Build a synthetic paper case so the pipeline can be exercised without a real PDF.

The fixture is a three-page text with six sections and a mixture of number-carrying
claims, comparisons, a causal claim, a hedged claim, and one deliberately wide
sentence that must not be split into fragments.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CASE = {
    "case_id": "selftest-reading14",
    "output_contract": {
        "assertions": "assertions.json",
        "jsonld": "assertions.jsonld",
        "evidence": "evidence.csv",
        "status": "status",
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="where to write the fixture; defaults next to this file")
    ap.add_argument("--paper", help="source paper text; defaults to examples/synthetic_paper.txt")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    root = Path(args.root).expanduser().resolve() if args.root else here / "fixture"
    root.mkdir(parents=True, exist_ok=True)

    paper = Path(args.paper) if args.paper else (here.parent / "examples" / "synthetic_paper.txt")
    dest = root / "paper.txt"
    dest.write_text(paper.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "case.json").write_text(json.dumps(CASE, ensure_ascii=False, indent=2), encoding="utf-8")

    # a scanned-style stub: no text layer, so extraction must report itself unable
    (root / "paper_scan.pdf").write_bytes(b"%PDF-1.4\nno text layer in this stub\n")
    print(json.dumps({"status": "ok", "fixture": str(root), "paper": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
