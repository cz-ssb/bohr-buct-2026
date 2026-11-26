---
name: structured-reading-notes
description: Turn one scientific paper (PDF, DOCX or plain text) into chapter-aligned, field-structured reading notes whose every claim carries a verifiable anchor (page + section + paragraph + quoted snippet), and export a machine-readable result.json. Use when someone asks for structured notes, a paper card, section summaries, knowledge items, or evidence-linked summaries of a paper, and needs the notes to be checkable rather than a compressed abstract.
metadata:
  short-description: Chapter-aligned paper notes with verifiable anchors
---

# Structured Reading Notes

A paper is a narrative; notes that survive review are a *structure*: the paper's own sections in the paper's own order, a fixed field card, knowledge items, and — for every claim — an anchor that a second reader can walk back to the page.

This skill does not write a summary. It builds the skeleton by parsing, then fills only what the paper actually supports, and refuses the rest explicitly.

## Contract of this skill

- **Input**: one paper file (`/input/`-style case dir usually holds `case.json` + `task.md`; the paper itself may be `paper.pdf`, `*.docx` or `*.txt`).
- **Outputs** (write to your output dir, default `/app/output`): `paper_card.json`, `notes.json`, `notes.md`, `evidence.csv`, `anchors.json`, and `result.json` that merges every field of `case.json → output_contract` plus `case_id`, `status`, `sources`, `uncertainty`, `change_log`.
- **Determinism**: structure, anchors and evidence tables come from scripts, not from prose. The model only writes short semantic fields, and every such field must cite an anchor id that already exists in `anchors.json`.

## Pipeline (3 commands + 1 self-check)

```bash
# 1. read the case, then extract page-indexed text with layout blocks
python scripts/pdf_to_pages.py --input <paper.pdf> --out work/pages.json --ocr auto

# 2. build sections, anchors, card, knowledge items (deterministic, no model)
python scripts/build_notes.py --pages work/pages.json --out app/output \
    --case-json <case.json> --paper <paper.pdf>

# 3. the model writes semantic fields ONLY, into app/output/semantic_fill.json:
#    {"fields": {field: {value, anchor_id, status}},
#     "sections": {"S4": {"method": {text, anchor_id}}},
#     "knowledge_items": [{term, definition, kind, anchor_id}],
#     "result": {contract field: value}}
#    then merge — an anchor that does not exist is rejected with exit 4
python scripts/build_notes.py --pages work/pages.json --out app/output \
    --case-json <case.json> --fill app/output/semantic_fill.json

# 4. self-check; a violation means fix, not ship
python scripts/validate_notes.py --dir app/output --pages work/pages.json --strict --skill-root .
```

`validate_notes.py` exits non-zero when an anchor is invented, a quote does not occur on that page, a required card field has no evidence but claims `reported`, `result.json` misses an `output_contract` field, or the resource set breaks the platform limits.

`selftest/run_selftest.py` runs the whole pipeline on a synthetic paper and injects two deliberate faults (an invented anchor, a fabricated quote) to prove both checks fire.

## What the outputs contain

- `paper_card.json` — research question, data, method conditions, main findings, limitations, each with `{value, evidence:[anchor_id], status: reported|not_reported|uncertain|conflict}`. `not_reported` is a first-class answer; never fabricate a value to fill it.
- `notes.json` — per section `{section, title, role, pages, purpose, method, result, conclusion}`, plus `knowledge_items` (`term`, `definition`, `kind: concept|variable|metric|method|abbreviation|lexicon`, `anchor_id`). Every filled field is `{text, anchor_id}`.
- `notes.md` — the same structure for humans, every bullet ending with its anchor as `[p.12 | a-s6-3]`.
- `evidence.csv` — `anchor_id,page,section,paragraph,quote,kind`, sortable and diffable. `kind=section` rows make the section cut itself auditable, not just the paragraphs.
- `result.json` — the delivery contract: `output_contract` fields from `case.json`, `case_id`, `status` (`success|partial|unable|refused` + reason), `sources`, `uncertainty[]`, `change_log[]`.

`S0 Front matter` holds the title block. It keeps its anchors for verification but is not scored as a chapter, and the purpose/method/result/conclusion quartet is not forced onto a title and an author line.

## Failure handling (must be explicit, never silent)

| Situation | Action |
|---|---|
| No text layer (scanned PDF) | try OCR pass (`--ocr auto`); if unavailable, set `status: partial`, mark every affected page in `uncertainty`, do not pretend to have read it |
| Encrypted / permission-limited PDF | `status: unable`, reason `encrypted_pdf`, stop after writing the honest result |
| Two-column text in wrong order | flag pages in `uncertainty` (`column_order_suspect`), keep anchors page-level so a reader can verify |
| Formulas / figures only as images | the extractor skips image blocks, so this content is absent by construction: say so in `uncertainty` instead of implying it was read |
| Paper longer than the model budget | process by sections, keep `status: partial` until every section has at least an anchor-bearing skeleton |
| Non-English paper | keep headings in the original language, add `title_zh` translation only as a labelled derived field |

## Rules

1. No pre-made answers, no invented numbers, no invented section titles. A heading that cannot be recognised leaves its block in `S0 Front matter` and the uncertainty says so.
2. Anchors must be page-level resolvable: `{page, section, paragraph, quote}` where `quote` is a verbatim substring of that page's extracted text (≤120 chars).
3. Anchor granularity follows the claim: a section-level claim may cite a section anchor, a numeric claim must cite the sentence that carries the number.
4. Everything a human must confirm goes into `uncertainty[]`, not into a footnote nobody reads.
5. Resources stay inside the platform limits: ≤50 UTF-8 text files, ≤500 KB each, ≤2 MB total, no symlinks.

## Files

- `scripts/pdf_to_pages.py` — extractor: pymupdf → pdfplumber → pypdf → `pdftotext`, optional OCR. Keeps layout blocks so paragraph boundaries survive.
- `scripts/build_notes.py` — outline, anchors, card, knowledge items, all outputs, and the `--fill` merge.
- `scripts/validate_notes.py` — anchor whitelist + quote-on-page + contract + resource-limit validator.
- `schema/note_schema.json` — field dictionary; `schema/anchor_format.md` — anchor spec.
- `lexicon/sections.json` — heading vocabulary (EN/ZH); `lexicon/abbreviations.json` — starter abbreviation table.
- `templates/paper_card.json` — empty card with all fields.
- `examples/minimal_example.md` — one worked example on a synthetic paper, explicitly labelled 示例 / example.
- `selftest/run_selftest.py` — one-command end-to-end run plus two injected faults; `selftest/README.md` — what it covers and why.

Requires Python 3.9+; `pymupdf` (or `pdfplumber`/`pypdf`, or the `pdftotext` CLI) is optional — without any of them the run reports itself as degraded and names the extractor that ran in `sources.extractor`.
