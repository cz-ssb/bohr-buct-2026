#!/usr/bin/env python3
"""Bind each candidate to the minimal evidence span that supports it.

"Minimal" is operational here, not rhetorical: a candidate carrying a number
needs a quote wide enough to contain that number and its subject, and nothing
wider. Every quote is checked to occur in the source sentence character for
character, because a paraphrase presented as evidence is the most common way a
nanopublication silently becomes unverifiable.

Usage:
  python scripts/bind_evidence.py --sentences work/sentences.json \
      --candidates work/candidates.json --out work/bound.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

MAX_QUOTE = 200
MIN_QUOTE = 30
NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*%?")
SENT_END = re.compile(r"(?<=[.!?])\s+")


def trim_to_numbers(text: str) -> str:
    """Keep the quote as wide as the numbers it has to support, then stop."""
    if len(text) <= MAX_QUOTE:
        return text
    nums = list(NUMBER.finditer(text))
    if not nums:
        cut = text.rfind(", ", 0, MAX_QUOTE)
        return text[:cut if cut > MIN_QUOTE else MAX_QUOTE].rstrip(", ") + ""
    lo = max(0, nums[0].start() - 60)
    hi = min(len(text), nums[-1].end() + 60)
    if hi - lo < MIN_QUOTE:
        hi = min(len(text), lo + MIN_QUOTE)
    if hi - lo > MAX_QUOTE:
        hi = lo + MAX_QUOTE
    return text[lo:hi].strip()


def evidence_type(text: str) -> str:
    if NUMBER.search(text) or re.search(r"(?i)\b(because|due to|therefore|than|compared)\b", text):
        return "direct"
    return "indirect"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--evidence-csv")
    args = ap.parse_args()

    sdoc = json.loads(Path(args.sentences).read_text(encoding="utf-8"))
    cdoc = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    by_sid = {s["sid"]: s for s in sdoc.get("sentences", [])}
    candidates = cdoc.get("candidates", [])
    if not candidates:
        print(json.dumps({"status": "unable", "reason": "no_candidates"}, ensure_ascii=False), file=sys.stderr)
        return 2

    claims: list[dict] = []
    failures: list[dict] = []

    for c in candidates:
        sen = by_sid.get(c["sid"])
        if not sen:
            failures.append({"cid": c["cid"], "reason": "sentence_missing", "sid": c["sid"]})
            continue
        quote = trim_to_numbers(c["text"])
        # a quote must be a verbatim slice of the source sentence
        if quote not in sen["text"]:
            failures.append({"cid": c["cid"], "reason": "quote_not_verbatim", "quote": quote[:80]})
            continue
        if len(quote) < MIN_QUOTE and len(sen["text"]) >= MIN_QUOTE:
            failures.append({"cid": c["cid"], "reason": "quote_too_short_to_support", "quote": quote})
            continue
        claims.append({
            "cid": c["cid"],
            "assertion_text": c["text"],
            "section": c["section"],
            "grounding": c.get("grounding", {}),
            "atomicity_flags": c.get("atomicity_flags", []),
            "evidence": {
                "quote": quote,
                "page": sen["page"],
                "para": sen["para"],
                "sid": sen["sid"],
                "span_in_sentence": {"start": sen["text"].find(quote),
                                     "end": sen["text"].find(quote) + len(quote)},
                "type": evidence_type(quote),
                "chars": len(quote),
            },
            "status": "bound",
        })

    payload = {
        "paper": sdoc.get("paper", {}),
        "sections": sdoc.get("sections", []),
        "claims": claims,
        "failures": failures,
        "stats": {
            "candidates_in": len(candidates),
            "bound": len(claims),
            "failed": len(failures),
            "direct": sum(1 for c in claims if c["evidence"]["type"] == "direct"),
            "indirect": sum(1 for c in claims if c["evidence"]["type"] == "indirect"),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.evidence_csv:
        p = Path(args.evidence_csv)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["cid", "section", "page", "para", "sid", "evidence_type", "quote"])
            for c in claims:
                w.writerow([c["cid"], c["section"], c["evidence"]["page"], c["evidence"]["para"],
                            c["evidence"]["sid"], c["evidence"]["type"], c["evidence"]["quote"]])

    print(json.dumps({"status": "ok" if claims else "unable", "out": str(out),
                      **payload["stats"]}, ensure_ascii=False))
    return 0 if claims else 3


if __name__ == "__main__":
    sys.exit(main())
