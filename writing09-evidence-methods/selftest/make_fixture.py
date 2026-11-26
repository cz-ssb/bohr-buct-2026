#!/usr/bin/env python3
"""Build a synthetic research project so the pipeline can be tested without a case.

The fixture deliberately contains one material conflict (the training split is
0.8 in the YAML and 0.9 in the log) and one absence (no repetition count anywhere),
because those are the two situations the chapter has to survive.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TRAIN_YAML = """\
model: sparse_router
learning_rate: 0.0003
batch_size: 64
epochs: 40
seed: 42
weight_decay: 0.01
optimizer: adamw
scheduler: cosine
warmup_steps: 500
dropout: 0.1
num_gpus: 4
precision: fp16
image_size: 224
train_split: 0.8
val_split: 0.1
test_split: 0.1
"""

EVAL_YAML = """\
checkpoint: checkpoints/best.ckpt
batch_size: 32
image_size: 224
precision: fp16
device: cuda:0
"""

TRAIN_LOG = """\
2026-03-02 09:11:03 start run seed=42 gpu_count=4
2026-03-02 09:11:04 lr=0.0003 batch_size=64 image_size=224
2026-03-02 09:11:40 dataset_version=cifar10-v2 train_split=0.9 val_split=0.1
2026-03-02 09:12:10 epoch=1 loss=3.412
2026-03-02 09:58:22 epoch=1 loss=2.980
2026-03-02 10:41:05 epoch=2 loss=2.115
2026-03-02 11:20:00 eval epoch=2 acc=0.712
2026-03-02 11:21:02 early stop not triggered patience=10
2026-03-02 11:22:00 finished total_epochs=40 best_acc=0.812
"""

TRAIN_PY = '''\
import argparse

import torch

from model import SparseRouter


def build_optimizer(model, lr, weight_decay):
    return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/train.yaml")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    model = SparseRouter(depth=12, hidden=384, heads=6)
    # the router keeps two of six experts active per token
    model.router.top_k = 2
    optim = build_optimizer(model, lr=3e-4, weight_decay=0.01)
    return model, optim, args


if __name__ == "__main__":
    main()
'''

MODEL_PY = '''\
import torch
import torch.nn as nn


class SparseRouter(nn.Module):
    def __init__(self, depth=12, hidden=384, heads=6, experts=6, top_k=2):
        super().__init__()
        self.depth = depth
        self.hidden = hidden
        self.heads = heads
        self.experts = experts
        self.top_k = top_k
        self.blocks = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(depth)])

    def forward(self, x):
        for block in self.blocks:
            x = block(x)
        return x
'''

DATA_README = """\
# Dataset notes

CIFAR-10, second revision of our preprocessing (cifar10-v2).

- 50,000 training images, 10,000 test images, 32x32 RGB upsampled to 224.
- Preprocessing: random crop 224 with 16 px padding, horizontal flip, normalization
  with mean (0.4914, 0.4822, 0.4465) and std (0.2470, 0.2435, 0.2616).
- Splits are drawn once with seed 42 and stored as index files; the loader reads the
  index files rather than re-splitting at runtime.
- The test partition is used only for the final number, never for model selection.

Note from the author: the exact repetition count of the reported runs was not
recorded for this project; the log holds a single run.
"""

REQUIREMENTS = """\
torch==2.1.0
torchvision==0.16.0
numpy==1.26.2
"""

RUN_SH = """\
#!/usr/bin/env bash
python train.py --config configs/train.yaml --seed 42 --batch-size 64
"""

CASE = {
    "case_id": "selftest-writing09",
    "output_contract": {
        "chapter": "methods.md",
        "parameter_table": "parameters.csv",
        "evidence_table": "evidence.csv",
        "gaps": "gaps.json",
        "status": "status",
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="where to write the fixture; defaults next to this file")
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else Path(__file__).resolve().parent / "fixture"
    materials = root / "materials"
    (materials / "configs").mkdir(parents=True, exist_ok=True)
    (materials / "logs").mkdir(parents=True, exist_ok=True)
    (materials / "code").mkdir(parents=True, exist_ok=True)
    (materials / "data").mkdir(parents=True, exist_ok=True)
    (materials / "env").mkdir(parents=True, exist_ok=True)

    (materials / "configs" / "train.yaml").write_text(TRAIN_YAML, encoding="utf-8")
    (materials / "configs" / "eval.yaml").write_text(EVAL_YAML, encoding="utf-8")
    (materials / "logs" / "train.log").write_text(TRAIN_LOG, encoding="utf-8")
    (materials / "code" / "train.py").write_text(TRAIN_PY, encoding="utf-8")
    (materials / "code" / "model.py").write_text(MODEL_PY, encoding="utf-8")
    (materials / "data" / "README.md").write_text(DATA_README, encoding="utf-8")
    (materials / "env" / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (materials / "run.sh").write_text(RUN_SH, encoding="utf-8")
    (materials / "paper_log").mkdir(exist_ok=True)
    (materials / "paper_log" / "attention.pdf").write_bytes(b"%PDF-1.4\nbinary stub\n")

    (root / "case.json").write_text(json.dumps(CASE, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "fixture": str(root)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
