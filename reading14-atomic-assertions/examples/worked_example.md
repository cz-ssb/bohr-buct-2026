# Worked example — three pages to twenty records

**This is an example, not a case result.** The paper is the synthetic fixture in `examples/synthetic_paper.txt`: three pages, six sections, no real experiments behind it. No claim here should be cited as a finding.

## Input

A three-page paper with headings glued to their first sentence (`3. Results. The sparse model reaches 71.8% ...`), numbers, one comparison, one causal sentence, one hedged sentence, and one sentence that must not be split.

## Run

```bash
python scripts/paper_to_sentences.py --input examples/synthetic_paper.txt --out work/sentences.json
# {"status":"ok","extractor":"plain_text","sentences":18,"sections":8}

python scripts/split_claims.py --sentences work/sentences.json --out work/candidates.json
# {"status":"ok","sentences_in":18,"candidates":20,"split_sentences":8,"flagged":2}

python scripts/bind_evidence.py --sentences work/sentences.json \
    --candidates work/candidates.json --out work/bound.json --evidence-csv work/evidence.csv
# {"status":"ok","candidates_in":20,"bound":20,"failed":0,"direct":13,"indirect":7}

python scripts/build_nanopub.py --sentences work/sentences.json --bound work/bound.json \
    --out out --case-json case.json --fill out/semantic_fill.json
# {"status":"success","records":20}
```

## Where the split helped, and where it did not

The comparison sentence became two records, which is the point of the whole exercise:

```
The sparse model reaches 71.8% test accuracy        (p.2, direct, 0.96)
the dense baseline reaches 68.4%.                   (p.2, direct, 0.96)
```

`... reduces inference cost while preserving accuracy ...` stayed **whole**, because splitting at `while` yields `preserving accuracy in large language models` — a fragment with no subject, which nobody can judge. The splitter tests each piece for a subject and a finite verb and falls back to the full sentence when the test fails. A wide claim is a lesser defect than an unjudgeable fragment.

## One record in full

```json
{
  "id": "np-selftest-reading14-013",
  "assertion": "it disappears at 96 pixels, where both models converge to roughly 61%.",
  "subject": "the accuracy gain",
  "relation": "decreases",
  "object": "at 96 pixels, both models near 61%",
  "qualifiers": {"image_size": "96 px", "value": "roughly 61%"},
  "evidence": {"quote": "it disappears at 96 pixels, where both models converge to roughly 61%.",
               "page": 2, "para": 1, "sid": "s0013", "type": "direct", "chars": 74},
  "source": {"title": "… (synthetic fixture)", "authors": ["Fixture Author"], "year": 2026,
             "doi": "10.0000/fixture.synthetic", "identifier": "10.0000/fixture.synthetic"},
  "confidence": 0.87,
  "confidence_rationale": "the failure boundary is the useful part of the result; 'roughly' is preserved rather than tightened",
  "quality_flags": ["approximate_value"]
}
```

Three decisions are visible in that record. The hedge `roughly` survives into both the object and the confidence. The direction is the failure boundary, not an accuracy claim. And the quote is the sentence itself, because the number and its condition sit in the same clause — a shorter quote would have dropped `96 pixels`.

## What the gate catches

`selftest/run_selftest.py` breaks the export four ways and checks that each is caught:

| Injected fault | Violation |
|---|---|
| assertion rewritten into a claim the paper never makes | `assertion_not_in_source` |
| relation set to `somewhat_relates_to` without a flag | `relation_not_controlled` |
| one character changed inside a quote (`71.8` → `71.9`) | `quote_not_on_page` |
| a record exported twice | `duplicate_assertion` |

The same run confirms a stub PDF with no text layer is reported `unable` instead of yielding invented text.

## What this example deliberately does not show

- Real bibliographic metadata. The DOI is marked synthetic; on a real paper a missing DOI stays `not_reported` and lands in `source_metadata_missing`.
- Figure-only evidence. The extractor cannot see it, so it becomes `bind_failure`, not a caption paraphrase.
- Cross-paper contradiction. That needs two sources and a `contradicts` relation; one paper alone cannot conflict with itself.
