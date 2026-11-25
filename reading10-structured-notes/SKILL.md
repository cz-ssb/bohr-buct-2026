---
name: reading10-structured-notes
description: Convert a research paper into chapter-aligned, evidence-anchored Markdown and JSON notes. Use when the user needs auditable literature notes with chapter structure, paragraph/page/figure anchors, explicit uncertainty, and machine-readable fields.
metadata:
  short-description: Chapter-aligned literature notes with verifiable anchors
---

# Reading 10 structured notes

Use this skill for one paper or a clearly delimited paper set. Preserve the paper's own section order and argument flow. Do not force an abstract-style template onto a paper whose structure differs.

## Workflow

1. Inspect available text, page markers, headings, captions, tables, and metadata. If the source is scanned, two-column, image-only, multilingual, or unusually long, record the extraction condition before interpreting content.
2. Build a chapter map using the paper's headings. For each substantive note, extract only claims supported by the source and record the smallest independently checkable anchor: section, paragraph index within section, and page or figure/table identifier when available.
3. Record research question, data, method and conditions, main finding, limitations, and the conditions under which a conclusion holds. Use `not_reported`, `uncertain`, or `conflict` instead of filling gaps.
4. Produce all three outputs: Markdown notes, JSON records, and a field dictionary. Keep Markdown and JSON values consistent.
5. Run `scripts/validate_notes.py <notes.json>`. Fix schema and anchor errors before delivery.

## Required output shape

- `notes.md`: paper metadata, chapter map, one section per paper chapter, and evidence-linked note cards.
- `notes.json`: an object with `metadata`, `chapters`, `notes`, and `uncertainties`.
- `field-dictionary.md`: field name, type, meaning, allowed uncertainty values, and an example marked as example.
- Use [references/chapter-anchor-map.template.json](references/chapter-anchor-map.template.json) when extracting a stable paragraph map from a source document.

Each note record must include `id`, `chapter`, `claim`, `research_question`, `data`, `method_conditions`, `finding`, `limitations`, `anchor`, and `status`. `anchor` must include `section` and `paragraph`, with `page` or `figure_table` when known.

## Calling, dependencies, and boundary

Call the skill with a paper file or an extracted-text directory, then write the three deliverables to a user-chosen output directory. The validator uses Python 3 and only the standard library. This skill structures and audits supplied evidence. It does not retrieve paywalled papers, infer unreadable values, or submit to the Playground.

## Exception handling

- No text layer: OCR or manual inspection may be used, but mark `extraction_mode: ocr` and lower confidence where OCR is ambiguous.
- Two columns or reading-order errors: reconstruct by heading and paragraph continuity, and mark unresolved ordering as `uncertain`.
- Formula, image, or table evidence: cite the formula/table/figure identifier and do not transcribe unreadable values.
- Long paper: process chapter by chapter and retain a compact chapter map. Do not reread the entire paper for every note.
- Non-Chinese paper: preserve original terms and add Chinese explanations only when supported by the source.

## Example boundary

Files under `examples/` are illustrative fixtures only. They are not contest answers, test scores, or claims about a real paper.
