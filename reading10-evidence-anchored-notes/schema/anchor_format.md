# Anchor format

An anchor is the smallest unit a second reader needs in order to check a note by hand.
Every note claim carries one; nothing in `paper_card.json` or `notes.json` may cite an
anchor id that is not present in `anchors.json` (the validator enforces this).

```json
{
  "anchor_id": "a-s3-2",
  "page": 7,
  "section": "S3",
  "section_title": "3 Method",
  "paragraph": 2,
  "quote": "Each layer has two sub-layers. The first is a multi-head ..."
}
```

Rules

1. `page` is the 1-based page of the physical file, not the paper's printed page number.
2. `quote` is a verbatim substring of the extracted text of that page (≤120 chars, whitespace normalized). If a claim cannot be pinned to a single page, split the claim.
3. `section` + `paragraph` are the local coordinates inside the extracted outline; paragraph counting restarts in every section.
4. Granularity follows the claim: a numeric claim cites the sentence that carries the number; a section-level claim may cite that section's first paragraph.
5. When the outline is not detectable, the section id stays `S0` and the run records `outline_not_detected` in `uncertainty`.
6. Anchor ids are stable across re-runs of the same file; a changed page break changes them, so record the paper version in `sources`.

Human-readable form: `[p.7 | S3 | ¶2]`.
