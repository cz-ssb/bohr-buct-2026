# Review checklist and author question bank

Run this before the second pass. Anything that cannot be answered from the
materials becomes a row in `gaps.json`, not a sentence in the chapter.

## Six element groups — a chapter is complete only when all six are answerable

| Group | The chapter must say | Source it comes from | If absent |
|---|---|---|---|
| Steps | each step's input, operation, output, decision condition | code, run scripts | a step with no decision condition is usually two steps compressed |
| Setup | hardware, software versions, environment, seed, repetition count | config, log header, requirements | repetition count is the most commonly missing item |
| Parameters | name, value, unit, target, source for every setting | config, CLI, log | a parameter without an address does not belong in the prose |
| Datasets | name, version, scale, preprocessing, split, use of each subset | dataset README, loader code | version ambiguity is the main cause of irreproducible splits |
| Controls | baseline identity and version, budget parity, metric, statistics | log, results tables | no baseline means no comparison may be claimed |
| Repro & limits | code version, environment, command, data access, seed; limitation tied to a failure scenario | repo state, run script | "may not generalise" is not a limitation |

## Question bank for `needs_confirmation`

Ask only what the chapter cannot proceed without; each question names the
material that made it necessary.

1. Which config actually produced the reported run — the one in the repository or the one on the cluster?
2. Was the reported number taken from a single run, or a mean over several seeds? If several, how many?
3. Which commit or release produced the checkpoint that was evaluated?
4. For every split ratio that disagrees between config and log: which value was in force?
5. Which GPU model and interconnect was used — the count alone does not let a reader budget the run?
6. Was early stopping applied, and with what patience, in the run that is reported?
7. Are the evaluation and training preprocessing identical? Padding, resize and normalisation constants are easy to drift apart.
8. Which metric definition was used — top-1, top-5, macro-averaged, or micro-averaged?
9. Was the test partition touched during development, for example for debugging or hyper-parameter choice?
10. Is any figure or table in the chapter produced from a different run than the text?

## Self-check the reviewer will perform

- Pick three numbers in the prose at random. Follow each `[P0xx]` to `parameters.csv`, then to `path#line`, then open that line. It must contain the same value.
- Check that every conflict listed in `gaps.json` appears in section 8 with both sources.
- Check that section 5 does not describe a comparison the materials do not support.
- Check that each limitation names a scenario that could actually happen.
- Check that `result.json.status` is honest: a chapter with an empty group is `partial`, not `success`.
