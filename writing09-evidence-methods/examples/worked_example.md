# Worked example — a synthetic project

**This is an example, not a case result.** The project below is fabricated so the pipeline can be walked through end to end. Nothing here is a real experiment, and no number should be quoted as one.

## Input

A directory of a small vision project:

```
materials/
├── configs/train.yaml      model, lr, batch size, epochs, seed, splits
├── configs/eval.yaml       eval batch size, precision, device
├── logs/train.log          run header, per-epoch lines, final accuracy
├── code/train.py           optimiser construction, arg parsing
├── code/model.py           depth / hidden / heads / top_k defaults
├── data/README.md          dataset revision, scale, preprocessing, split files
├── env/requirements.txt    pinned versions
├── run.sh                  the command that was actually executed
└── paper_log/attention.pdf a binary stub, deliberately unreadable
```

The material contains one deliberate contradiction: `train_split: 0.8` in `train.yaml` while the log records `train_split=0.9`. It also never states how many runs back the reported accuracy.

## Run

```bash
python scripts/collect_materials.py --materials materials --out work/blocks.json
# {"status":"ok","files_read":8,"files_skipped":1,"blocks":9}

python scripts/extract_params.py --blocks work/blocks.json --out work/params.json
# {"status":"ok","candidates":41,"params":27,"conflicts":1,"confirmed":26}

python scripts/build_methods.py --blocks work/blocks.json --params work/params.json \
    --out out --case-json case.json --fill out/semantic_fill.json
# {"status":"partial","params":27,"unsupported_numbers":0,"conflicts":1,
#  "reasons":["material_conflicts: 1"]}

python scripts/validate_submission.py --dir out --strict --skill-root .
# {"status":"ok","checks":{...}}
```

## Excerpt of the parameter register (`parameters.csv`)

| param_id | name | value | unit | target | source | status |
|---|---|---|---|---|---|---|
| P001 | seed | 42 | - | run control | `run.sh#L2-L2` | confirmed |
| P002 | batch_size | 64 | samples | data loader | `run.sh#L2-L2` | confirmed |
| P008 | learning_rate | 0.0003 | - | optimizer | `code/train.py#L23-L23` | confirmed |
| P014 | epochs | 40 | epochs | training loop | `configs/train.yaml#L4-L4` | confirmed |
| P022 | train_split | 0.8 | ratio | data split | `configs/train.yaml#L14-L14` | **conflict** |

`batch_size` appears twice in the full table — 64 for training, 32 for evaluation. They are different stages, so they are two rows, not a contradiction. `train_split` appears once and is flagged, because the config and the log disagree inside the same stage.

## Excerpt of the chapter (`methods.md`)

```markdown
**2. Train the sparse router** [P008 code/train.py#L23-L23] [P014 configs/train.yaml#L4-L4] ...
- Input: configs/train.yaml, seed, batch size
- Operation: build the 12-block router with two of six experts active per token, ...
- Output: checkpoints/best.ckpt chosen by validation accuracy
- Decision condition: stop after the configured epoch budget or when the
  early-stopping patience elapses
```

```markdown
## 8. Open items for author confirmation

| Kind | Item | Question for the author | Evidence |
|---|---|---|---|
| missing | repetition count of the reported runs | How many seeds back the reported accuracy? | logs/train.log holds one run |
| conflict | training split ratio | config says 0.8, log records 0.9 — which produced the number? | configs/train.yaml#L14 vs logs/train.log |
| needs_confirmation | GPU model of the 4-GPU node | The count is stated, the model is not | configs/train.yaml |
```

## Result (`result.json`, abridged)

```json
{
  "case_id": "selftest-writing09",
  "status": "partial",
  "status_reasons": ["material_conflicts: 1"],
  "uncertainty": [
    {"kind": "material_conflict", "detail": "train_split = 0.8 / 0.9",
     "evidence": "configs/train.yaml#L14-L14, logs/train.log#L3-L3"},
    {"kind": "material_gap", "detail": "repetition count of the reported runs", ...},
    {"kind": "absent_parameter", "detail": "num_runs", "evidence": "not found in materials"}
  ]
}
```

Two outcomes worth noting. The chapter is `partial` even though it is perfectly usable, because a conflict is unresolved — that is the honest status, and the reader sees exactly what to fix. And the binary PDF is listed as skipped rather than described: a material that could not be read is a fact about the run, not something to smooth over.

## What this example is meant to show

1. The tables and addresses come from scripts; only step wording and dataset narrative come from the model.
2. A conflict surfaces twice — in the parameter register and in the author questions — and never as a silently chosen value.
3. `not reported` and `derived` are legitimate cell contents. An invented number is not.
