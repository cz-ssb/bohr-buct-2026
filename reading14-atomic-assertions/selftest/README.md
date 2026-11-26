# Self-test — what it covers and why

`python selftest/run_selftest.py` walks the whole pipeline on the synthetic paper,
then breaks the export three ways and breaks one input on purpose. Twenty checks;
it prints `20/20 checks behaved as expected` and exits 0 when everything holds.

## Checks on the happy path

| Check | Why it exists |
|---|---|
| fixture built | the test itself must be reproducible |
| sentences: ok, ≥15 | an extractor that yields three sentences cannot support an export |
| sections: ≥5 | section labels are part of the structure the reader navigates |
| three pages kept | page numbers are an address; losing them loses the trail |
| section pages are right | Method on p.1, Results on p.2 — page drift is a silent address error |
| candidates ≥15 | the split pass must actually produce judgeable units |
| split_sentences ≥4 | at least some sentences must genuinely separate into two claims |
| no dangling conjunction | no candidate ends in `and`, `but`, `whereas`, `while`, or a comma |
| no verbless fragment | no candidate starts lowercase without a subject |
| everything bound, 0 failures | candidates without evidence are not records |
| direct evidence ≥8 | numeric claims must be anchored directly, not inferred |
| every quote occurs on its page | verbatim evidence is the whole point |
| export: ≥15 records | the assembled deliverable has substance |
| JSON-LD mirrors records | a manifest whose node count disagrees cannot be consumed downstream |
| clean export: 0 violations | the validator must not cry wolf on a good package |

## Injected faults

| Fault | Expected violation |
|---|---|
| assertion rewritten into a claim the paper never makes | `assertion_not_in_source` |
| relation `somewhat_relates_to` with no flag | `relation_not_controlled` |
| one character changed in a quote (`71.8` → `71.9`) | `quote_not_on_page` |
| the same record exported twice | `duplicate_assertion` |
| stub PDF with no text layer | extractor exits non-zero with `unable` |

The quote fault is deliberately tiny. A one-character change is exactly the size of error that survives eyeballing, and it must fail the gate.

## What it does not cover

- Real journals, real two-column layouts, figure-only evidence. Those become `bind_failure` or `column_order_suspect` at runtime; this test proves the reporting path, not the layout handling.
- Claims that span two sentences. The binder keeps a claim inside one source sentence by design.
- Anything about contest scoring. The platform runs the fixed cases; this proves the machinery and its tripwires work.
