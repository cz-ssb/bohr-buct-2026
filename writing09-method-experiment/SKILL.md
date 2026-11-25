---
name: writing09-method-experiment
description: Turn code, configuration, logs, and data descriptions into a reproducible Methods and Experiments chapter with aligned parameters, ordered steps, explicit gaps, controls, and concrete limitations. Use when writing or auditing research methods from source materials.
metadata:
  short-description: Evidence-grounded methods and experiment chapters
---

# Writing 09 methods and experiments

Treat source materials as evidence. Extract before drafting. Never invent a value, dataset version, repetition count, or control merely to make prose smooth.

## Workflow

1. Inventory code, configs, logs, dataset documentation, environment files, and commands. Record each source path and line or log location.
2. Extract method steps, experiment settings, parameters, datasets and splits, controls, repetitions, evaluation metrics, software versions, seeds, and data acquisition.
3. Normalize parameters into `parameters.json` with `name`, `value`, `unit`, `target`, `source`, and `status`. The prose must use the same values.
4. Write ordered steps. Every step states input, operation, output, and decision condition where applicable.
5. Emit a `gaps.json` list for absent, conflicting, or author-confirmation items. Use `missing`, `conflict`, or `needs_confirmation` and include evidence.
6. Explain limitations as concrete failure scenarios tied to an assumption, range, dataset, or implementation choice. Add a reproduction checklist.
7. Run `scripts/validate_materials.py <materials.json>`. Do not deliver if parameter values disagree or a required field is silently omitted.

## Deliverables

- `methods.md`: the chapter, with ordered steps and tables derived from the JSON.
- `materials.json`: extracted evidence, steps, parameters, datasets, controls, repetitions, and reproduction checklist.
- `parameters.json`: normalized parameter table.
- `gaps.json`: explicit gaps and conflicts.
- `checklist.md`: field checklist and author questions.

The files in `examples/` are examples only. They must never be presented as actual experiment results.

## Calling, dependencies, and boundary

Call the skill with a directory of code, configuration, logs, and data documentation. Write the five deliverables to a user-chosen output directory, then run the validator with Python 3. The validator uses only the standard library. This skill documents supplied experiments and exposes gaps. It does not execute experiments, recover unavailable data, or invent author confirmations.
