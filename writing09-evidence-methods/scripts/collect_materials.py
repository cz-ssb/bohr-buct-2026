#!/usr/bin/env python3
"""Snapshot a materials directory into line-addressable evidence blocks.

Why this exists: a methods chapter may only contain what the materials say, so
every value must be walkable back to `path:line`. Free-form reading of a project
loses that address. This pass makes the address the unit of work.

Usage:
  python scripts/collect_materials.py --materials <dir> --out work/evidence_blocks.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

TEXT_EXT = {
    ".yaml": "config", ".yml": "config", ".json": "config", ".toml": "config",
    ".ini": "config", ".cfg": "config", ".conf": "config", ".env": "config",
    ".py": "code", ".sh": "code", ".bash": "code", ".r": "code", ".jl": "code",
    ".c": "code", ".cpp": "code", ".h": "code", ".java": "code", ".go": "code",
    ".log": "log", ".out": "log", ".err": "log", ".txt": "log",
    ".md": "doc", ".rst": "doc", ".tex": "doc",
    ".csv": "data", ".tsv": "data", ".jsonl": "data",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", "site-packages", ".ipynb_checkpoints"}
MAX_BYTES = 4 * 1024 * 1024
BLOCK_LINES = 20


def classify(path: Path) -> str:
    return TEXT_EXT.get(path.suffix.lower(), "unknown")


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if len(raw) > MAX_BYTES:
        return None, f"too_large: {len(raw)} bytes"
    if b"\x00" in raw[:4096]:
        return None, "binary_or_utf16"
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, "decode_failed"


def blocks_of(lines: list[str], path_str: str, kind: str, block_lines: int) -> list[dict]:
    """Cut a file into line-ranged blocks, preferring blank-line boundaries."""
    out: list[dict] = []
    start = 0
    idx = 0
    n = len(lines)
    while idx < n:
        hard_end = min(idx + block_lines, n)
        cut = hard_end
        for probe in range(idx + 1, hard_end):
            if not lines[probe - 1].strip() and lines[probe - 1] != "":
                cut = probe
                break
        chunk = lines[idx:cut]
        if not any(l.strip() for l in chunk):
            idx = cut
            start = cut
            continue
        text = "\n".join(chunk)
        out.append({
            "block_id": f"{path_str}#L{idx + 1}-L{cut}",
            "path": path_str,
            "line_start": idx + 1,
            "line_end": cut,
            "kind": kind,
            "chars": len(text),
            "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
            "text": text,
        })
        idx = cut
        start = cut
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--block-lines", type=int, default=BLOCK_LINES)
    ap.add_argument("--max-blocks", type=int, default=4000)
    args = ap.parse_args()

    root = Path(args.materials).expanduser().resolve()
    if not root.is_dir():
        print(json.dumps({"status": "unable", "reason": "materials_dir_missing",
                          "path": str(root)}), file=sys.stderr)
        return 2

    blocks: list[dict] = []
    files: list[dict] = []
    skipped: list[dict] = []
    total_lines = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            kind = classify(path)
            if kind == "unknown":
                skipped.append({"path": rel, "reason": "unsupported_type"})
                continue
            text, err = read_text(path)
            if text is None:
                skipped.append({"path": rel, "reason": err})
                continue
            lines = text.splitlines()
            total_lines += len(lines)
            got = blocks_of(lines, rel, kind, args.block_lines)
            blocks.extend(got)
            files.append({"path": rel, "kind": kind, "lines": len(lines),
                          "blocks": len(got), "bytes": path.stat().st_size})

    truncated = False
    if len(blocks) > args.max_blocks:
        blocks = blocks[:args.max_blocks]
        truncated = True

    payload = {
        "materials_root": str(root),
        "files": files,
        "skipped": skipped,
        "blocks": blocks,
        "stats": {
            "files_read": len(files),
            "files_skipped": len(skipped),
            "blocks": len(blocks),
            "total_lines": total_lines,
            "truncated": truncated,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), **payload["stats"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
