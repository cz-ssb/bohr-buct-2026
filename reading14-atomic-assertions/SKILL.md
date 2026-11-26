---
name: atomic-assertion-nanopublication
description: Decompose a paper into single, independently judgeable assertions, bind each one to a minimal verbatim evidence span with a page and paragraph address, attach bibliographic source metadata, and export machine-readable assertions.json plus JSON-LD. Use when claims must be individually checkable and traceable back to the paper, including when someone asks for a nanopublication, a claim-evidence table, or an assertion-level export.
metadata:
  short-description: Atomic, evidence-bound assertion export
---

# Atomic Assertion Nanopublication

A summary compresses a paper. A nanopublication does the opposite: it splits the paper into claims small enough that each one can be judged true or false on its own, and gives every claim the shortest piece of text that proves it and the address where that text lives.

The three things that destroy this kind of export, in order of frequency: a paragraph inside one `assertion` field, an evidence quote that was paraphrased instead of copied, and a relation whose direction was reversed. The pipeline is arranged to block those three.

## Contract of this skill

- **Input**: `case.json` and `task.md` from the case dir, plus the paper — a PDF with a text layer, a `.txt`/`.md` rendering, or page-marked text. A scanned PDF without a text layer is a legitimate but different input: it must report itself unable rather than produce invented text.
- **Outputs** (to the output dir, default `/app/output`): `assertions.json`, `assertions.jsonld`, `evidence.csv`, `gaps.json`, `result.json` carrying every `output_contract` field plus `case_id`, `status`, `sources`, `uncertainty`, `change_log`.
- **Division of labour**: pages, sentences, splits, quotes and addresses come from scripts. The model writes only `subject`, `relation`, `object`, `qualifiers`, `confidence`, `confidence_rationale` and `quality_flags` per candidate.

## Pipeline (4 commands + 1 gate)

```bash
# 1. paper -> page / paragraph / sentence structure
python scripts/paper_to_sentences.py --input <paper.pdf|paper.txt> --out work/sentences.json

# 2. sentences -> claim candidates; splitting is opt-in and a fragment falls back to the whole sentence
python scripts/split_claims.py --sentences work/sentences.json --out work/candidates.json

# 3. candidates -> minimal verbatim evidence spans, each verified against the page text
python scripts/bind_evidence.py --sentences work/sentences.json \
    --candidates work/candidates.json --out work/bound.json --evidence-csv work/evidence.csv

# 4. bound evidence + semantic layer -> assertions.json and JSON-LD
python scripts/build_nanopub.py --sentences work/sentences.json --bound work/bound.json \
    --out app/output --case-json <case.json> --fill app/output/semantic_fill.json

# 5. gate: a violation means fix, not ship
python scripts/validate_nanopub.py --dir app/output --sentences work/sentences.json --strict --skill-root .
```

`semantic_fill.json`:

```json
{
  "source": {"title","authors":[],"year","venue","doi","version","identifier"},
  "assertions": [
    {"cid":"c0009","subject":"sparse model","relation":"achieves","object":"71.8% test accuracy",
     "direction":"subject_to_object",
     "qualifiers":{"metric":"test accuracy","value":"71.8%"},
     "confidence":0.96,"confidence_rationale":"number and metric both inside the quote",
     "quality_flags":[]}
  ],
  "result": {"<output_contract field>": "value"}
}
```

A `cid` that does not exist in `bound.json` is rejected with exit 4: the model may annotate candidates, never invent them.

## What the output contains

- `assertions.json` — one record per claim: `id`, `assertion` (verbatim from the paper), `subject`, `relation`, `object`, `direction`, `qualifiers`, `evidence {quote, page, para, sid, type, chars}`, `source`, `confidence`, `confidence_rationale`, `quality_flags`, `section`.
- `assertions.jsonld` — the same records as a nanopublication manifest: `np:hasAssertion` nodes, each with `prov:wasDerivedFrom` pointing at quote, page, section and evidence type. Node count must equal record count.
- `evidence.csv` — `record_id, cid, section, page, para, sid, evidence_type, quote`, so evidence can be sorted, diffed and spot-checked without opening the JSON.
- `gaps.json` — unannotated claims, bind failures, and which source metadata the paper does not carry.
- `result.json` — the contract, with `partial` whenever a candidate stayed unannotated, a quote failed binding, or metadata is missing.

## Failure handling (explicit, never silent)

| Situation | Action |
|---|---|
| Scanned PDF, no text layer | exit non-zero from the extractor with `no_pdf_extractor`; write `status: unable`, reason `no_text_layer`; never produce text from a label |
| Encrypted or permission-limited PDF | `status: unable`, reason `encrypted_pdf`, stop after the honest result |
| Two-column text out of order | keep page-level addresses so a reader can still locate the quote; note `column_order_suspect` in `uncertainty` |
| Evidence only in a figure or table | the extractor sees no such text: record `bind_failure` with reason `evidence_in_figure_only` rather than paraphrasing a caption into a claim |
| A candidate has no sentence to bind to | `bind_failure`, and the claim is listed in `uncertainty`, not dropped silently |
| A sentence cannot be split without producing a fragment | keep it whole; a wide claim is better than an unjudgeable fragment |
| More claims than the model budget | annotate in passes; `status: partial` until every candidate is either annotated or listed as unannotated |

## Rules

1. `assertion` must occur in the paper character for character. A paraphrase is a violation (`assertion_not_in_source`), not a style choice.
2. The quote must be the smallest span that still supports the claim: wide enough to contain the number and its subject, no wider.
3. `increases` / `decreases` name the quantity as the object. `outperforms` names the better system as the subject. Swapping them changes the truth value.
4. A hedged source claim keeps its hedge: `may not transfer` never becomes `does not transfer`, and its confidence stays below the direct-evidence band.
5. Negation is preserved. "not statistically significant" must not be exported as "significant".
6. A relation outside `references/relations.json` is allowed only with the `relation_unmapped` flag, so the vocabulary gap is visible.
7. Resources stay inside the platform limits: ≤50 UTF-8 text files, ≤500 KB each, ≤2 MB total, no symlinks.

## Files

- `scripts/paper_to_sentences.py` — page-aware extractor (pymupdf → pdfplumber → pypdf → pdftotext, or plain text), section detection including headings glued to the first sentence, sentence splitting with abbreviation handling.
- `scripts/split_claims.py` — coordination-marker splitting with a subject+finite-verb test, so fragments fall back to the whole sentence; atomicity hints per candidate.
- `scripts/bind_evidence.py` — minimal-span trimming around numbers, verbatim verification, direct vs indirect evidence labelling.
- `scripts/build_nanopub.py` — record assembly, JSON-LD manifest, evidence CSV, gap and status computation.
- `scripts/validate_nanopub.py` — assertion-in-source, quote-on-page, atomicity, relation vocabulary, subject/object confusion, duplicates, JSON-LD integrity, resource limits.
- `schema/assertion_schema.json` — field dictionary and atomicity rule; `schema/result_schema.json` — deliverable contract.
- `references/relations.json` — 19 controlled relations with inverse pairs and direction rules.
- `examples/synthetic_paper.txt` — the fixture paper; `examples/assertions-20.json` — 20 format records on it, explicitly a fixture; `examples/worked_example.md` — the pipeline walked through.
- `selftest/run_selftest.py` — one command, 20 checks, four injected faults; `selftest/README.md` — what it covers.

Requires Python 3.9+. A PDF extractor is optional: without one the run reports `no_pdf_extractor` and says which extractors it tried.
