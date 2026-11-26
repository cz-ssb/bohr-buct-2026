---
name: methods-experiment-chapter
description: Turn a research project's code, configuration files, training logs and dataset notes into a reproducible Methods and Experiments chapter, where every numeric value carries a `path#line` source, every parameter is aligned between table and prose, and missing or conflicting material is handed back to the author as explicit questions instead of being filled in. Use when writing, rewriting or auditing a methods section from raw experimental material.
metadata:
  short-description: Evidence-addressed methods chapters from code, configs and logs
---

# Methods and Experiments Chapter

A methods chapter is not prose about an experiment; it is a claim that someone else can repeat the experiment. That claim fails for a small number of very specific reasons — a learning rate with no source, a batch size that disagrees between the config and the log, a split ratio nobody wrote down, a "baseline" that was never described — and this skill is organised around blocking those reasons rather than around writing smoothly.

Extract first. Draft second. Invent nothing.

## Contract of this skill

- **Input**: a case directory with `case.json` and `task.md`, plus the project material — configuration files (`*.yaml`, `*.json`, `*.toml`, `*.ini`), training and evaluation logs, source code, dataset documentation, environment files and the commands actually used.
- **Outputs** (write to the output dir, default `/app/output`): `methods.md`, `parameters.csv`, `evidence.csv`, `gaps.json`, `result.json` carrying every field of `case.json → output_contract` plus `case_id`, `status`, `sources`, `uncertainty`, `change_log`.
- **Division of labour**: addresses, values, tables and checks come from scripts. The model writes only the semantic layer — step wording, dataset narrative, control reasoning, limitation scope — and may only cite parameter ids and evidence blocks that already exist.

## Pipeline (3 commands + 1 self-check)

```bash
# 1. snapshot the material into line-addressable blocks
python scripts/collect_materials.py --materials <project_dir> --out work/blocks.json

# 2. pull every parameter out with its address; conflicts are reported, not resolved
python scripts/extract_params.py --blocks work/blocks.json --out work/params.json

# 3. render the chapter and check prose against the parameter register
python scripts/build_methods.py --blocks work/blocks.json --params work/params.json \
    --out app/output --case-json <case.json> --fill app/output/semantic_fill.json

# 4. gate: a violation is something to fix, not something to ship
python scripts/validate_submission.py --dir app/output --strict --skill-root .
```

The model writes `semantic_fill.json` between steps 2 and 3:

```json
{
  "steps":      [{"name","input","operation","output","decision","param_refs":["P008"],"evidence":["logs/train.log#L1-L9"]}],
  "settings":   [{"aspect","text","source","param_refs":[]}],
  "datasets":   [{"name","version","scale","preprocess","split","uses","param_refs":[],"evidence":[]}],
  "controls":   [{"baseline","baseline_version","budget_parity","metric","statistics","evidence":[]}],
  "repro":      [{"item","value","evidence"}],
  "limitations":[{"claim","failure_scenario","scope","evidence":[]}],
  "gaps":       [{"kind":"missing|conflict|needs_confirmation","item","question","evidence"}],
  "result":     {"<output_contract field>": "value"}
}
```

A `param_refs` id that does not exist is rejected with exit 4; so is an `evidence` reference that is neither a block id, a file path, nor the literal `derived`.

## What the output contains

- `methods.md` — eight numbered sections: steps, setup, parameters, datasets, controls, reproducibility, limitations, open items. Each step states input, operation, output and decision condition; step and dataset lines end with `[P0xx path#Lstart-Lend]`.
- `parameters.csv` — `param_id, name, value, unit, target, source, status`. `status` is `confirmed` (found under a known name), `candidate` (numeric-looking key outside the vocabulary) or `conflict` (same name, same stage, different values). `scope` separates training from evaluation, because `batch_size 64` for training and `batch_size 32` for evaluation is not a contradiction.
- `evidence.csv` — every material block with `block_id, path, line_start, line_end, kind, chars, cited_in_chapter`. Rows marked `cited_in_chapter = no` say which material went unused, which is itself reviewable information.
- `gaps.json` — the questions, plus `conflicts_from_materials` and `schema_names_absent` (`num_runs`, code version, GPU model and the like were simply never recorded).
- `result.json` — the delivery contract, with `status` downgraded to `partial` whenever a required element group is empty, a conflict exists, or an unsupported number slipped into the prose.

## Failure handling (explicit, never silent)

| Situation | Action |
|---|---|
| No configuration file at all | still emit the chapter, leave the parameter table empty, and say in `gaps.json` that settings are unverifiable; never transcribe typical defaults |
| Config and log disagree | keep both values, mark the parameter `conflict`, mark the chapter `partial`, ask the author which one produced the reported number |
| Value only in code as a variable (`lr=lr`) | skipped by design; the effective value must come from config or log, otherwise it is a gap |
| Binary or unreadable material (`attention.pdf`, `.ckpt`) | listed in `sources.skipped`, not pretended to be read |
| Materials exceed the block budget | `stats.truncated = true` and `status: partial`; state which files were covered |
| Multi-stage project (train / eval / inference) | parameters are kept per stage; a cross-stage comparison is written only when both stages are documented |
| A number the table cannot support | flagged as `unsupported_number` in `uncertainty`, never silently rewritten |

## Rules

1. A value in the chapter that is not in `parameters.csv` is a defect. The checker scans prose for numbers adjacent to parameter names and reports the ones the register cannot support.
2. A conflict is never resolved by choosing the more plausible value. It goes to section 8 as a question with both sources.
3. `not reported` is a legitimate value in a table cell; an invented number is not.
4. Limitations must name a failure scenario and a scope: "may not generalise" is rejected, "a second seed can move accuracy by more than one point" is accepted.
5. A comparison may only be described if the materials describe a baseline. No baseline in the materials means section 5 says so.
6. Resources stay inside the platform limits: ≤50 UTF-8 text files, ≤500 KB each, ≤2 MB total, no symlinks.

## Files

- `scripts/collect_materials.py` — text material → line-ranged evidence blocks; unreadable and binary files are skipped with a reason.
- `scripts/extract_params.py` — parameter vocabulary (≈30 names), four syntaxes (YAML/JSON/CLI/log), conflict detection per stage.
- `scripts/build_methods.py` — eight-section render, parameter/evidence CSV export, prose-vs-register check, `result.json`.
- `scripts/validate_submission.py` — contract fields, section coverage, dangling addresses, illegal gap kinds, resource limits.
- `schema/param_schema.json` — parameter vocabulary and field dictionary; `schema/result_schema.json` — `result.json` contract.
- `references/checklist.md` — the six element groups as a checklist, plus the author question bank.
- `templates/gaps.json` — empty gap file to fill in when starting from scratch.
- `examples/worked_example.md` — one worked example on a synthetic project, explicitly labelled example.
- `selftest/run_selftest.py` — one command, 16 checks, four deliberately injected faults; `selftest/README.md` — what it covers.

Requires Python 3.9+ and the standard library only. No network, no model calls, deterministic output for the same materials.
