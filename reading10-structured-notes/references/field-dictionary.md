# Reading 10 field dictionary

| Field | Type | Meaning |
|---|---|---|
| `metadata` | object | Title, authors, year, version, DOI or explicit `not_reported` values |
| `chapters` | array | Paper headings in source order, with source labels preserved |
| `notes[].claim` | string | One auditable claim, without combining unrelated findings |
| `notes[].data` | object/string | Dataset, population, sample, split, or `not_reported` |
| `notes[].method_conditions` | object/string | Method, parameters, comparison conditions, and assumptions |
| `notes[].anchor` | object | `section`, `paragraph`, optional `page`, `figure_table`, and optional quote |
| `notes[].status` | enum | `supported`, `uncertain`, `conflict`, or `not_reported` |

All examples are illustrative only. Never turn a missing value into a plausible value.
