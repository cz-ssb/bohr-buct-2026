#!/usr/bin/env python3
"""Extract parameter values from evidence blocks, each carrying its own address.

A methods chapter fails review for exactly one reason most of the time: a number
in the prose that no configuration file, log line, or author note supports. This
pass extracts values *with* their `path#Lstart-Lend` address so the prose can be
checked against the table instead of trusted.

Usage:
  python scripts/extract_params.py --blocks work/evidence_blocks.json --out work/params_raw.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# canonical name -> (unit, target, aliases)
SCHEMA: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "learning_rate": ("", "optimizer", ("lr", "learningrate", "learning_rate", "init_lr", "base_lr", "learning-rate")),
    "batch_size": ("samples", "data loader", ("batchsize", "batch_size", "bs", "train_batch_size", "micro_batch_size")),
    "epochs": ("epochs", "training loop", ("epochs", "num_epochs", "n_epoch", "max_epochs", "train_epochs", "total_epochs")),
    "max_steps": ("steps", "training loop", ("max_steps", "train_steps", "step_num", "total_steps")),
    "seed": ("", "run control", ("seed", "random_seed", "manual_seed", "seeds", "randomseed")),
    "weight_decay": ("", "optimizer", ("weight_decay", "wd", "l2_penalty")),
    "momentum": ("", "optimizer", ("momentum", "beta1")),
    "optimizer": ("", "optimizer", ("optimizer", "optim", "opt", "optimizer_type")),
    "scheduler": ("", "optimizer", ("scheduler", "lr_scheduler", "schedule", "lr_schedule")),
    "warmup_steps": ("steps", "optimizer", ("warmup_steps", "warmup", "warmup_ratio")),
    "train_split": ("ratio", "data split", ("train_split", "train_ratio", "train_size", "split_train")),
    "val_split": ("ratio", "data split", ("val_split", "valid_split", "val_ratio", "dev_ratio")),
    "test_split": ("ratio", "data split", ("test_split", "test_ratio")),
    "num_gpus": ("count", "hardware", ("num_gpus", "n_gpu", "gpu_num", "gpus", "world_size", "gpu_count")),
    "device": ("", "hardware", ("device", "devices", "accelerator")),
    "precision": ("", "training", ("precision", "fp16", "amp", "mixed_precision", "dtype")),
    "image_size": ("px", "preprocessing", ("image_size", "img_size", "resolution", "input_size")),
    "max_len": ("tokens", "preprocessing", ("max_len", "seq_len", "sequence_length", "max_length", "context_length")),
    "num_layers": ("layers", "model", ("num_layers", "n_layers", "depth", "num_hidden_layers")),
    "hidden_size": ("", "model", ("hidden_size", "d_model", "emb_size", "hidden_dim")),
    "num_heads": ("heads", "model", ("num_heads", "n_heads", "attention_heads", "heads")),
    "dropout": ("ratio", "model", ("dropout", "drop_prob", "p_drop")),
    "grad_clip": ("norm", "training", ("grad_clip", "clip_grad", "max_grad_norm", "grad_clip_norm")),
    "early_stopping": ("epochs", "training loop", ("early_stopping", "patience", "early_stop_patience")),
    "temperature": ("", "decoding", ("temperature", "temp")),
    "top_k": ("", "decoding", ("top_k", "topk")),
    "num_runs": ("runs", "repeat", ("num_runs", "repeats", "n_repeat", "trials", "num_seeds")),
    "dataset": ("", "data", ("dataset", "datasets", "data_name", "dataset_name", "corpus")),
    "dataset_version": ("", "data", ("dataset_version", "data_version", "version", "revision", "datasets_version")),
    "python_version": ("", "environment", ("python", "python_version", "py_version")),
    "torch_version": ("", "environment", ("torch", "pytorch", "torch_version", "tf", "tensorflow")),
    "cuda_version": ("", "environment", ("cuda", "cuda_version", "cudnn", "driver")),
}

# Keys outside the table are still collected when they look numeric-parameter-like.
FUZZY_KEY = re.compile(r"(?i)(lr|rate|batch|epoch|step|seed|size|layer|head|dim|drop|clip|patience|version|split|ratio|gpu|device|precision|optim|schedule|dataset|repeat|trial)")

NUM_LIKE = re.compile(r"^[+-]?(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?$")
VALUE_WITH_UNIT = re.compile(r"^([+-]?(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?)\s*([A-Za-z%/]+)$")

PATTERNS = [
    # yaml / ini / python kwargs:  key: 0.001   |  key = 3
    re.compile(r"^\s{0,12}([A-Za-z_][A-Za-z0-9_.\- ]{0,44})\s*[:=]\s*([^\s#;,][^#;,]*)"),
    # json:  "key": "value"  |  "key": 12
    re.compile(r'"([A-Za-z_][A-Za-z0-9_.\-]{0,44})"\s*:\s*("(?:[^"\\]|\\.)*"|[^,}\s]+)'),
    # cli:  --key value  |  --key=value
    re.compile(r"--([A-Za-z][A-Za-z0-9_\-]{0,44})(?:\s*=\s*|\s+)([^\s,]+)"),
    # log:  epoch 3 loss=0.21  |  lr=1e-4
    re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{0,44})\s*=\s*([^\s,;\]\)]+)"),
]


def norm_key(raw: str) -> str:
    return re.sub(r"[\s_\-.]", "", raw.strip().lower())


# Keys are matched after normalisation, so `image_size`, `image-size` and `imageSize`
# all land on the same alias entry instead of becoming three separate parameters.
ALIAS_TO_CANON = {norm_key(alias): canon for canon, (_, _, aliases) in SCHEMA.items() for alias in aliases}
ALIAS_TO_CANON.update({norm_key(canon): canon for canon in SCHEMA})
# A training log records the value of `epoch` once per epoch; that is an observation,
# not a setting. Counting it as a parameter manufactures a conflict out of progress lines.
LOG_OBSERVATION_KEYS = {
    "epoch", "step", "iter", "iteration", "loss", "acc", "accuracy", "valacc",
    "trainloss", "valloss", "valaccuracy", "time", "elapsed", "eta", "throughput",
    "gpuutil", "mem", "memory", "bestacc",
}

# Values that are only a bare identifier are usually variable references in code
# (`lr=lr`, `optimizer=args.opt`), not recorded settings.
SYMBOLIC_OK = {
    "adamw", "adam", "sgd", "rmsprop", "adagrad", "lamb",
    "cosine", "linear", "constant", "step", "plateau", "poly", "onecycle",
    "fp16", "fp32", "bf16", "bf16amp", "amp", "true", "false", "none", "null",
    "cuda", "cpu", "mps", "gpu", "auto",
}
IDENT_ONLY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def clean_value(raw: str) -> str:
    v = raw.strip().strip(",").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    # `torch==2.1.0` splits as key `torch`, value `=2.1.0`; the operator is not part of the value
    v = v.lstrip("=").strip()
    return v.strip()


def to_number(v: str) -> float | None:
    if NUM_LIKE.match(v):
        try:
            return float(v)
        except ValueError:
            return None
    m = VALUE_WITH_UNIT.match(v)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def unit_of(v: str, canon: str | None) -> str:
    m = VALUE_WITH_UNIT.match(v)
    if m:
        return m.group(5)
    return SCHEMA[canon][0] if canon in SCHEMA else ""


def target_of(canon: str | None) -> str:
    return SCHEMA[canon][1] if canon in SCHEMA else "unassigned"


def stage_of(path: str) -> str:
    """Training and evaluation routinely use different batch sizes; that is not a conflict.

    Same-name values are only compared inside one stage, so `batch_size 32` in
    eval.yaml does not fight with `batch_size 64` in train.yaml.
    """
    low = path.lower()
    if any(t in low for t in ("eval", "test", "valid", "dev", "infer", "predict")):
        return "evaluation"
    if "train" in low or low.rsplit("/", 1)[-1].startswith("run"):
        return "training"
    return "unspecified"


def iter_candidates(text: str, path: str, block_id: str, line_start: int, kind: str = ""):
    for offset, line in enumerate(text.splitlines()):
        lineno = line_start + offset
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        for pattern in PATTERNS:
            for m in pattern.finditer(line):
                key_raw, val_raw = m.group(1), m.group(2)
                # an attribute path such as `model.router.top_k` records top_k, not a new parameter
                if "." in key_raw:
                    key_raw = key_raw.rsplit(".", 1)[-1]
                val = clean_value(val_raw)
                if not val or len(val) > 60:
                    continue
                nk = norm_key(key_raw)
                canon = ALIAS_TO_CANON.get(nk)
                if not canon and len(nk) <= 1:
                    continue
                num = to_number(val)
                if canon is None and num is None:
                    continue
                if canon is None and not FUZZY_KEY.search(nk):
                    continue
                if kind == "log" and nk in LOG_OBSERVATION_KEYS:
                    continue
                # a bare identifier on the right-hand side is a variable reference, not a recorded setting
                if num is None and IDENT_ONLY.match(val) and val.lower() not in SYMBOLIC_OK:
                    continue
                # an expression is code, not configuration
                if any(ch in val for ch in "([{"):
                    continue
                if val.lower() == key_raw.strip().lower():
                    continue
                yield {
                    "key_raw": key_raw.strip(),
                    "name": canon or nk,
                    "in_schema": canon is not None,
                    "value_raw": val,
                    "value_num": num,
                    "unit": unit_of(val, canon),
                    "target": target_of(canon),
                    "scope": stage_of(path),
                    "source": f"{path}#L{lineno}-L{lineno}",
                    "block_id": block_id,
                    "kind": None,
                }


def merge(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    params: list[dict] = []
    conflicts: list[dict] = []
    by_key: dict[tuple[str, str], list[dict]] = {}
    for e in entries:
        by_key.setdefault((e["name"], e["scope"]), []).append(e)

    for (name, scope), group in by_key.items():
        distinct = {str(g["value_num"]) if g["value_num"] is not None else g["value_raw"] for g in group}
        status = "confirmed" if group[0]["in_schema"] else "candidate"
        if len(distinct) > 1:
            status = "conflict"
            conflicts.append({
                "name": name,
                "scope": scope,
                "values": sorted(distinct),
                "sources": sorted({g["source"] for g in group}),
                "note": "same parameter, different values in materials; the chapter must not pick one silently",
            })
        params.append({
            "param_id": f"P{len(params) + 1:03d}",
            "name": name,
            "scope": scope,
            "value_raw": group[0]["value_raw"],
            "value_num": group[0]["value_num"],
            "unit": group[0]["unit"],
            "target": group[0]["target"],
            "source": group[0]["source"],
            "all_sources": sorted({g["source"] for g in group}),
            "occurrences": len(group),
            "status": status,
            "in_schema": group[0]["in_schema"],
        })
    return params, conflicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.blocks).read_text(encoding="utf-8"))
    blocks = data.get("blocks", [])
    if not blocks:
        print(json.dumps({"status": "unable", "reason": "no_blocks"}, ensure_ascii=False), file=sys.stderr)
        return 2

    entries: list[dict] = []
    for b in blocks:
        for c in iter_candidates(b["text"], b["path"], b["block_id"], b["line_start"], b["kind"]):
            c["kind"] = b["kind"]
            entries.append(c)

    params, conflicts = merge(entries)
    covered = {p["name"] for p in params}
    expected_missing = sorted(n for n in SCHEMA if n not in covered)

    payload = {
        "params": params,
        "conflicts": conflicts,
        "coverage": {
            "found": sorted(covered),
            "schema_names_absent": expected_missing,
            "note": "absent names are gaps, not permission to invent a value",
        },
        "stats": {
            "candidates": len(entries),
            "params": len(params),
            "conflicts": len(conflicts),
            "confirmed": sum(1 for p in params if p["status"] == "confirmed"),
            "candidate_only": sum(1 for p in params if p["status"] == "candidate"),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), **payload["stats"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
