#!/usr/bin/env python3
"""One command that proves the pipeline works and that its checks actually fire.

A validator nobody has seen fail is a validator nobody should trust, so this
script runs the happy path and then breaks things on purpose: an invented
parameter reference, a number with no table entry, a parameter whose address
points at nothing, and a gap with an illegal kind.

Usage:  python selftest/run_selftest.py
Exit:   0 all checks behaved as expected, 1 at least one expectation failed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Everything the test writes lives outside the skill directory, so a run never
# leaves artefacts that would then be packaged as resources.
WORK = Path(tempfile.mkdtemp(prefix="methods-chapter-selftest-"))


def run(script: str, *args: str) -> tuple[int, str, str]:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_fill(blocks_doc: dict, params_doc: dict) -> dict:
    pid = {p["name"]: p["param_id"] for p in params_doc["params"]}
    blocks_by_path: dict[str, str] = {}
    for b in blocks_doc["blocks"]:
        blocks_by_path.setdefault(b["path"], b["block_id"])

    def refs(*names: str) -> list[str]:
        return [pid[n] for n in names if n in pid]

    def ev(*paths: str) -> list[str]:
        return [blocks_by_path[p] for p in paths if p in blocks_by_path]

    return {
        "steps": [
            {"name": "Preprocess CIFAR-10 v2 into fixed index splits",
             "input": "raw CIFAR-10 archive and the stored split index files",
             "operation": "random crop to 224 with 16 px padding, horizontal flip, "
                          "per-channel normalisation, then read the split from the index file instead of re-splitting",
             "output": "model-ready shards for the training, validation and test partitions",
             "decision": "if the index file is missing, abort rather than re-splitting, because a fresh split "
                         "changes the partitions and invalidates the comparison",
             "param_refs": refs("image_size", "train_split", "val_split", "test_split"),
             "evidence": ev("data/README.md", "configs/train.yaml")},
            {"name": "Train the sparse router",
             "input": "configs/train.yaml, seed, batch size",
             "operation": "build the 12-block router with two of six experts active per token, optimise with the "
                          "configured optimiser and schedule",
             "output": "checkpoints/best.ckpt chosen by validation accuracy",
             "decision": "stop after the configured epoch budget or when the early-stopping patience elapses",
             "param_refs": refs("learning_rate", "batch_size", "epochs", "optimizer", "scheduler",
                                "warmup_steps", "dropout", "num_gpus", "precision", "seed", "weight_decay"),
             "evidence": ev("configs/train.yaml", "code/train.py", "code/model.py", "logs/train.log")},
            {"name": "Select the checkpoint and report the test number once",
             "input": "validation accuracy per epoch from the training log",
             "operation": "keep the best validation checkpoint, evaluate it a single time on the test partition",
             "output": "the reported test accuracy",
             "decision": "the test partition is never used for selection; if it is needed twice, treat the second "
                         "number as invalid",
             "param_refs": refs("batch_size"),
             "evidence": ev("configs/eval.yaml", "logs/train.log", "data/README.md")},
        ],
        "settings": [
            {"aspect": "hardware", "text": "4 GPUs in one node, fp16 mixed precision",
             "source": "configs/train.yaml", "param_refs": refs("num_gpus", "precision")},
            {"aspect": "software", "text": "torch 2.1.0, torchvision 0.16.0, numpy 1.26.2",
             "source": "env/requirements.txt"},
            {"aspect": "seeds", "text": "python/torch seed fixed at 42, split index files generated with the same seed",
             "source": "configs/train.yaml, run.sh", "param_refs": refs("seed")},
            {"aspect": "repetitions", "text": "not reported — the log contains a single run",
             "source": "logs/train.log"},
        ],
        "datasets": [
            {"name": "CIFAR-10", "version": "cifar10-v2 (second revision of this project's preprocessing)",
             "scale": "50,000 train / 10,000 test, 32x32 upsampled to 224",
             "preprocess": "random crop 224 with padding 16, horizontal flip, mean/std normalisation",
             "split": "training 0.8/0.9 (conflicting between config and log), validation 0.1, test 0.1, "
                      "drawn once with seed 42 and stored as index files",
             "uses": "train partition fits parameters; validation partition selects the checkpoint; "
                     "test partition is evaluated once",
             "param_refs": refs("dataset_version", "train_split", "val_split", "test_split", "seed"),
             "evidence": ev("data/README.md", "configs/train.yaml", "logs/train.log")},
        ],
        "controls": [
            {"baseline": "no external baseline is reported in the materials",
             "baseline_version": "not reported",
             "budget_parity": "not applicable — there is no second condition to compare against",
             "metric": "top-1 accuracy on the test partition, single evaluation",
             "statistics": "single run, so no variance or significance statement is possible",
             "evidence": ev("logs/train.log")},
        ],
        "repro": [
            {"item": "code version", "value": "not reported (no commit hash in the materials)", "evidence": "derived"},
            {"item": "environment", "value": "torch 2.1.0 / torchvision 0.16.0 / numpy 1.26.2", "evidence": "env/requirements.txt"},
            {"item": "command", "value": "python train.py --config configs/train.yaml --seed 42 --batch-size 64",
             "evidence": "run.sh"},
            {"item": "data access", "value": "CIFAR-10 with the stored cifar10-v2 split index files", "evidence": "data/README.md"},
            {"item": "seed", "value": "42 for torch seeding and for the split index generation", "evidence": "configs/train.yaml"},
        ],
        "limitations": [
            {"claim": "the accuracy number describes this single run",
             "failure_scenario": "a second run with a different seed can move the number by more than one point, "
                                 "so any comparison against published numbers is unsafe",
             "scope": "one seed, one run, no repetition count in the materials",
             "evidence": "logs/train.log"},
            {"claim": "the split is reproducible only if the index files survive",
             "failure_scenario": "re-splitting from the raw archive produces different partitions and silently "
                                 "changes the evaluation",
             "scope": "anything that regenerates the split instead of reading the index files",
             "evidence": ["data/README.md", "configs/train.yaml"]},
            {"claim": "the router's expert activation is fixed at two per token",
             "failure_scenario": "changing top_k changes the compute budget, so throughput or accuracy claims "
                                 "from a different top_k do not transfer",
             "scope": "top_k = 2 as set in the model code",
             "evidence": "code/model.py"},
        ],
        "gaps": [
            {"kind": "missing", "item": "repetition count of the reported runs",
             "question": "How many seeds or runs back the reported accuracy, and should the chapter report mean ± sd?",
             "evidence": "logs/train.log holds one run"},
            {"kind": "conflict", "item": "training split ratio",
             "question": "config/train.yaml says 0.8 while the training log records 0.9 — which one produced the "
                         "reported number?",
             "evidence": "configs/train.yaml#L14 vs logs/train.log"},
            {"kind": "missing", "item": "code commit or release tag",
             "question": "Which commit produced best.ckpt? Without it the chapter cannot be reproduced exactly.",
             "evidence": "no version file in materials"},
            {"kind": "needs_confirmation", "item": "GPU model of the 4-GPU node",
             "question": "The materials say 4 GPUs but not which model — confirm before stating hardware.",
             "evidence": "configs/train.yaml"},
        ],
        "result": {"chapter": "methods.md", "parameter_table": "parameters.csv",
                   "evidence_table": "evidence.csv", "gaps": "gaps.json", "status": "see result.json"},
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    # 0. fixture
    fixture = WORK / "fixture"
    p = subprocess.run([sys.executable, str(ROOT / "selftest" / "make_fixture.py"),
                        "--root", str(fixture)],
                       capture_output=True, text=True, encoding="utf-8")
    check("fixture built", p.returncode == 0, p.stderr.strip()[:200])
    blocks = WORK / "blocks.json"
    params = WORK / "params.json"

    # 1. collect
    rc, so, se = run("collect_materials.py", "--materials", str(fixture / "materials"), "--out", str(blocks))
    doc = load(blocks) if blocks.exists() else {}
    stats = doc.get("stats", {})
    check("collect: ok", rc == 0 and stats.get("files_read", 0) >= 5,
          f"rc={rc} files={stats.get('files_read')} blocks={stats.get('blocks')}")
    skipped = [s["path"] for s in doc.get("skipped", [])]
    check("collect: binary PDF skipped not faked", any(s.endswith(".pdf") for s in skipped), str(skipped))

    # 2. extract
    rc, so, se = run("extract_params.py", "--blocks", str(blocks), "--out", str(params))
    pdoc = load(params) if params.exists() else {}
    pstats = pdoc.get("stats", {})
    check("extract: ok", rc == 0 and pstats.get("params", 0) >= 8,
          f"rc={rc} params={pstats.get('params')} confirmed={pstats.get('confirmed')}")
    check("extract: conflict detected", pstats.get("conflicts", 0) >= 1,
          json.dumps([c["name"] for c in pdoc.get("conflicts", [])], ensure_ascii=False))
    srcs = {p["source"] for p in pdoc.get("params", [])}
    check("extract: every param carries an address", all("#L" in s for s in srcs) and bool(srcs), f"{len(srcs)} sources")

    # 3. build with the good fill
    fill_good = WORK / "fill_good.json"
    fill_good.write_text(json.dumps(build_fill(doc, pdoc), ensure_ascii=False, indent=2), encoding="utf-8")
    out_good = WORK / "out_good"
    rc, so, se = run("build_methods.py", "--blocks", str(blocks), "--params", str(params),
                     "--out", str(out_good), "--case-json", str(fixture / "case.json"),
                     "--fill", str(fill_good))
    summary = json.loads(so) if so.strip().startswith("{") else {}
    check("build: ran", rc == 0, se.strip()[:200])
    check("build: six element groups covered",
          all(summary.get("coverage", {}).get(k, 0) > 0 for k in
              ("steps", "settings", "datasets", "controls", "repro", "limitations")),
          json.dumps(summary.get("coverage", {}), ensure_ascii=False))
    check("build: conflict forces partial, not silent success",
          summary.get("status") == "partial" and any("material_conflicts" in r for r in summary.get("reasons", [])),
          f"status={summary.get('status')} reasons={summary.get('reasons')}")
    check("build: chapter table carries addresses",
          "#L" in (out_good / "methods.md").read_text(encoding="utf-8"),
          "source column present")

    # 4. validate the good run
    rc, so, se = run("validate_submission.py", "--dir", str(out_good), "--strict", "--skill-root", str(ROOT))
    v = json.loads(so) if so.strip().startswith("{") else {}
    check("validate: clean run has no violations", rc == 0 and v.get("status") == "ok",
          json.dumps(v.get("violations", [])[:3], ensure_ascii=False))

    # 5. injected fault A: invented parameter reference
    bad = json.loads(fill_good.read_text(encoding="utf-8"))
    bad["steps"][1]["param_refs"].append("P999")
    fill_bad = WORK / "fill_bad_ref.json"
    fill_bad.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, so, se = run("build_methods.py", "--blocks", str(blocks), "--params", str(params),
                     "--out", str(WORK / "out_bad_ref"), "--case-json", str(fixture / "case.json"),
                     "--fill", str(fill_bad))
    check("fault A: invented param ref rejected with exit 4", rc == 4, f"rc={rc} {se.strip()[:120]}")

    # 6. injected fault B: a number the table cannot support
    num = json.loads(fill_good.read_text(encoding="utf-8"))
    num["limitations"].append({
        "claim": "converges quickly",
        "failure_scenario": "with learning rate 0.0009 the run diverges within 3 epochs",
        "scope": "untested variants",
        "evidence": "logs/train.log",
    })
    fill_num = WORK / "fill_bad_number.json"
    fill_num.write_text(json.dumps(num, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, so, se = run("build_methods.py", "--blocks", str(blocks), "--params", str(params),
                     "--out", str(WORK / "out_bad_number"), "--case-json", str(fixture / "case.json"),
                     "--fill", str(fill_num))
    s2 = json.loads(so) if so.strip().startswith("{") else {}
    check("fault B: unsourced number caught", rc == 0 and s2.get("unsupported_numbers", 0) >= 1,
          f"unsupported={s2.get('unsupported_numbers')} status={s2.get('status')}")
    r2 = load(WORK / "out_bad_number" / "result.json")
    check("fault B: surfaced in uncertainty",
          any(u.get("kind") == "unsupported_number" for u in r2.get("uncertainty", [])),
          json.dumps(r2.get("uncertainty", [])[:2], ensure_ascii=False)[:160])

    # 7. injected fault C: parameter address that points nowhere
    tamper = WORK / "out_tamper_src"
    shutil.copytree(out_good, tamper)
    rows = (tamper / "parameters.csv").read_text(encoding="utf-8").splitlines()
    for i in range(1, len(rows)):
        if "configs/train.yaml" in rows[i]:
            rows[i] = rows[i].replace("configs/train.yaml", "nonexistent/file.yaml")
            break
    (tamper / "parameters.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    rc, so, se = run("validate_submission.py", "--dir", str(tamper), "--strict", "--skill-root", str(ROOT))
    v3 = json.loads(so) if so.strip().startswith("{") else {}
    types3 = {x["type"] for x in v3.get("violations", [])}
    check("fault C: dangling parameter address rejected",
          rc == 1 and "param_source_not_in_evidence" in types3,
          str(sorted(types3)))

    # 8. injected fault D: illegal gap kind
    tamper2 = WORK / "out_tamper_gap"
    shutil.copytree(out_good, tamper2)
    g = load(tamper2 / "gaps.json")
    g["gaps"][0]["kind"] = "probably_fine"
    (tamper2 / "gaps.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, so, se = run("validate_submission.py", "--dir", str(tamper2), "--strict", "--skill-root", str(ROOT))
    v4 = json.loads(so) if so.strip().startswith("{") else {}
    types4 = {x["type"] for x in v4.get("violations", [])}
    check("fault D: illegal gap kind rejected", rc == 1 and "bad_gap_kind" in types4, str(sorted(types4)))

    width = max(len(c[0]) for c in checks)
    passed = 0
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail if not ok else ''}")
        passed += 1 if ok else 0
    print(f"\n{passed}/{len(checks)} checks behaved as expected")
    print(f"artefacts kept for inspection: {WORK}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
