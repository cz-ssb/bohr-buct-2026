#!/usr/bin/env python3
"""Split sentences into independently judgeable claim candidates.

The failure this pass prevents is the whole paragraph inside one `assertion`
field: a claim that cannot be true or false on its own cannot be checked. Splits
happen only at explicit coordination and contrast markers, and every candidate
stays a verbatim slice of the sentence it came from, so nothing is paraphrased
into existence.

Usage:
  python scripts/split_claims.py --sentences work/sentences.json --out work/candidates.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# markers that reliably separate two judgeable statements
SPLIT_MARKERS = [
    "; however, ", "; whereas ", "; ", ", but ", ", whereas ", ", while ",
    ", and ", ", yet ", " but ", " whereas ", " while ", " however, ",
]
CAUSAL = re.compile(r"(?i)\b(because|due to|as a result|therefore|thus|hence|so that|"
                    r"leads? to|results? in|caused by|attributable to)\b")
COMPARATIVE = re.compile(r"(?i)\b(higher|lower|more|fewer|greater|smaller|increase[sd]?|"
                         r"decrease[sd]?|outperform[s]?|improve[sd]?|reduce[sd]?|drop[s]?|"
                         r"rise[s]?|exceed[s]?|better|worse|faster|slower|than)\b")
NUMBER = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*%?")
HEDGE = re.compile(r"(?i)\b(may|might|could|suggest|suggests|appears?|likely|possibly|"
                   r"we hypothesi[sz]e|it is unclear)\b")
SELF_REFERENCE = re.compile(r"(?i)^(figure|fig\.|table|tab\.|eq\.|equation|algorithm|appendix|see )")
QUESTION = re.compile(r"[?？]$")
REFERENCE_ONLY = re.compile(r"(?i)(et al\.|\[\d+(,\s*\d+)*\]|doi:|https?://)")


def is_judgeable(text: str) -> tuple[bool, str]:
    if len(text) < 40:
        return False, "too_short_to_carry_a_claim"
    if QUESTION.search(text.strip()):
        return False, "question_not_assertion"
    if SELF_REFERENCE.match(text.strip()):
        return False, "caption_or_pointer"
    words = text.split()
    if REFERENCE_ONLY.search(text) and len([w for w in words if w.lower() in
                                            ("show", "shows", "found", "report", "observe", "achieved",
                                             "reported", "demonstrate", "indicate", "is", "are")]) == 0:
        return False, "reference_entry_not_claim"
    return True, ""


# A clause can only stand as its own assertion if it has a subject and a finite verb.
# Without this, splitting `... reduces cost while preserving accuracy` produces the
# fragment `preserving accuracy`, which nobody can judge true or false.
SUBJECT_START = re.compile(r"^(we|our|it|its|they|their|this|these|those|the|a|an|both|each|such)\b", re.I)
FINITE_VERB = set("""
is are was were has have had does do did can may might will would could should
shows show shown reported reports reaches reach improved improves improve
reduces reduce reduced increases increase decreased decreases achieves achieve
outperforms outperformed requires require required uses use used enables enable
causes caused remains remain converged converges converge disappears disappear
holds hold held fails fail failed stops stop stopped trains trained train
describes describe tests tested test matters matter suggests suggest suggested
measured measure evaluated evaluate applied apply provides provide provides
gives give yields yield exceeds exceed drops drop rises rise keeps keep preserves
preserve maintains maintain found finds points point agrees agree differs differ
""".split())
PARTICIPLE = re.compile(r"^([a-z]+ing|[a-z]+ed)\b")


def can_stand_alone(piece: str) -> bool:
    words = piece.split()
    if len(words) < 5:
        return False
    first = words[0]
    if PARTICIPLE.match(first.lower()) and not SUBJECT_START.match(first):
        return False
    if not (first[0].isupper() or SUBJECT_START.match(first)):
        return False
    return any(w.strip(",.;:").lower() in FINITE_VERB for w in words)


def split_sentence(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of verbatim pieces; falls back to the whole sentence.

    Splitting is opt-in per piece: if any piece cannot stand alone as a judgeable
    statement, the sentence stays whole, because a fragment is worse than a wide claim.
    """
    pieces: list[tuple[int, int]] = []
    pos = 0
    while pos < len(text):
        best: tuple[int, str] | None = None
        for marker in SPLIT_MARKERS:
            i = text.find(marker, pos)
            if i != -1 and (best is None or i < best[0]):
                best = (i, marker)
        if best is None:
            break
        i, marker = best
        if i - pos < 30:
            pos = i + len(marker)
            continue
        # the marker belongs to neither side: the left piece ends before it,
        # the right piece starts after it, so no piece ends in a dangling `and`
        pieces.append((pos, i))
        pos = i + len(marker)
    pieces.append((pos, len(text)))
    if len(pieces) < 2:
        return [(0, len(text))]
    for a, b in pieces:
        if not can_stand_alone(text[a:b].strip()):
            return [(0, len(text))]
    return pieces


def atomicity_flags(text: str) -> list[str]:
    flags: list[str] = []
    if len(text) > 220:
        flags.append("long_span")
    joins = sum(text.count(m) for m in (" and ", " but ", " whereas ", " while "))
    if joins >= 2:
        flags.append("multiple_coordination")
    if len(NUMBER.findall(text)) >= 3:
        flags.append("multi_number")
    if CAUSAL.search(text) and COMPARATIVE.search(text):
        flags.append("causal_plus_comparison")
    return flags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-claims", type=int, default=0)
    args = ap.parse_args()

    doc = json.loads(Path(args.sentences).read_text(encoding="utf-8"))
    sentences = doc.get("sentences", [])
    if not sentences:
        print(json.dumps({"status": "unable", "reason": "no_sentences"}, ensure_ascii=False), file=sys.stderr)
        return 2

    candidates: list[dict] = []
    skipped: list[dict] = []

    for s in sentences:
        ok, why = is_judgeable(s["text"])
        if not ok:
            skipped.append({"sid": s["sid"], "reason": why, "text": s["text"][:120]})
            continue
        spans = split_sentence(s["text"])
        for k, (a, b) in enumerate(spans):
            text = s["text"][a:b].strip()
            if len(text) < 25:
                continue
            candidates.append({
                "cid": f"c{len(candidates) + 1:04d}",
                "sid": s["sid"],
                "page": s["page"],
                "para": s["para"],
                "section": s["section"],
                "text": text,
                "span": {"start": a, "end": b},
                "split_part": k if len(spans) > 1 else None,
                "grounding": {
                    "causal": bool(CAUSAL.search(text)),
                    "comparative": bool(COMPARATIVE.search(text)),
                    "numbers": NUMBER.findall(text),
                    "hedged": bool(HEDGE.search(text)),
                },
                "atomicity_flags": atomicity_flags(text),
            })

    if len(candidates) < args.min_claims:
        print(json.dumps({"status": "partial", "reason": "too_few_claims",
                          "candidates": len(candidates)}, ensure_ascii=False), file=sys.stderr)

    payload = {
        "candidates": candidates,
        "skipped": skipped,
        "stats": {
            "sentences_in": len(sentences),
            "candidates": len(candidates),
            "skipped": len(skipped),
            "split_sentences": sum(1 for c in candidates if c["split_part"] is not None),
            "flagged": sum(1 for c in candidates if c["atomicity_flags"]),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), **payload["stats"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
