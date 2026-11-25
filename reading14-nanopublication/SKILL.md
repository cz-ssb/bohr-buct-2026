---
name: reading14-nanopublication
description: Decompose paper text into single, auditable nanopublication-style assertions bound to minimal evidence, source metadata, identifiers, confidence rationale, and machine-readable JSON-LD. Use when claims must be independently checkable and traceable to a paper.
metadata:
  short-description: Evidence-bound nanopublication assertions
---

# Reading 14 nanopublications

Create one independently testable assertion per record. Preserve conditions, populations, direction, and scope. Do not put an entire paragraph into one assertion field.

## Workflow

1. Establish source metadata first: title, authors, year, version, DOI or explicit `not_reported` identifiers.
2. Split prose into atomic assertions. Separate conjunctions, causal links, comparisons, and qualifications when they could be judged independently.
3. Bind each assertion to the minimum sufficient evidence span. Record section, paragraph, page, figure/table, and a short quote when available. Label evidence as `direct` or `indirect`.
4. Represent subject, relation, object, conditions, and qualifiers explicitly. Use controlled relation terms from `references/relations.json` where possible.
5. Add confidence and a rationale tied to evidence coverage, source clarity, and unresolved ambiguity. Flag `evidence_insufficient`, `relation_uncertain`, `source_missing`, or `conflict` instead of guessing.
6. Export both `assertions.json` and JSON-LD. Run `scripts/validate_nanopub.py assertions.json`.

## Required record fields

Each assertion needs `id`, `assertion`, `subject`, `relation`, `object`, `qualifiers`, `evidence`, `source`, `confidence`, `confidence_rationale`, and `quality_flags`. Evidence needs a location and type. Source needs bibliographic metadata and an identifier field, even when its value is `not_reported`.

## Calling, dependencies, and boundary

Call the skill with paper text plus page or figure markers when available. Write `assertions.json` and the JSON-LD export to a user-chosen output directory, then run the validator with Python 3. The validator uses only the standard library. This skill records claims and provenance from supplied material. It does not identify unsupported claims as true, resolve contradictory sources silently, or submit a contest attempt.

Scanning, cross-figure evidence, missing text, and contradiction are first-class states. Keep the assertion, mark the quality flag, and explain what cannot be established.

The files in `examples/` are illustrative only and contain no contest case claims. `examples/assertions-20.json` is a synthetic format fixture with 20 records, not claims from a real paper.
