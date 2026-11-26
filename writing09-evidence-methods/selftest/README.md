# Self-test — what it covers and why

`python selftest/run_selftest.py` builds a synthetic project, runs the whole
pipeline, then breaks four things on purpose. Sixteen checks; the run prints
`16/16 checks behaved as expected` and exits 0 when everything is as intended.

## The fixture

`make_fixture.py` writes a small vision project: a training config, an evaluation
config, a training log, two Python files, a dataset README, pinned requirements,
a run script, and one binary PDF stub.

Two properties are planted on purpose, because they are the two situations a
methods chapter actually has to survive:

- a **conflict** — `train_split: 0.8` in the config, `train_split=0.9` in the log
- an **absence** — the number of runs that back the reported accuracy is never stated

## Checks

| # | Check | Why it exists |
|---|---|---|
| 1 | fixture built | the test itself must be reproducible |
| 2 | collect: ok (≥5 files) | a materials walk that finds nothing is a silent failure |
| 3 | binary PDF skipped, not faked | unreadable material must be reported, never summarised |
| 4 | extract: ≥8 parameters | a table with three rows is not a methods section |
| 5 | extract: conflict detected | the planted contradiction must not disappear |
| 6 | every parameter carries `path#L` | a value without an address is an assertion without evidence |
| 7 | build ran | render path works with a realistic fill |
| 8 | six element groups covered | the coverage criterion is the scoring criterion |
| 9 | conflict forces `partial` | a conflict must not sit behind `status: success` |
| 10 | chapter table carries addresses | the prose must show where values came from |
| 11 | clean run has zero violations | the validator must not cry wolf on a good package |
| 12 | **fault A** invented `P999` → exit 4 | citations must resolve against the register |
| 13 | **fault B** `0.0009` near a parameter name is caught | a number the table cannot support must not pass |
| 14 | fault B surfaced in `uncertainty` | catching it silently is the same as missing it |
| 15 | **fault C** address pointing at a missing file → violation | a plausible-looking address is not a real one |
| 16 | **fault D** illegal gap kind → violation | `kind` is an enum, not free text |

## What it does not cover

- Real-world config dialects (Hydra composition, argparse groups, `wandb` config dumps). The vocabulary in `extract_params.py` is the extension point.
- Papers whose methods live in a PDF rather than in code. That is the reading skill's territory, not this one.
- Any claim about contest scoring. The platform runs the fixed cases; this test only proves the machinery and its tripwires work.
