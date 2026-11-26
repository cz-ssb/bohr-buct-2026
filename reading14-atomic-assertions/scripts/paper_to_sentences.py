#!/usr/bin/env python3
"""Turn a paper into page- and paragraph-addressed sentences.

An assertion is only checkable if its evidence has an address, and the address
has to survive extraction. So this pass keeps three things other extractors drop:
the page the text came from, the paragraph it belonged to, and the section it sat
under. Sentences are the finest unit handed to the model.

Usage:
  python scripts/paper_to_sentences.py --input paper.pdf --out work/sentences.json
  python scripts/paper_to_sentences.py --input paper.txt --out work/sentences.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ABBREV = {
    "e.g", "i.e", "et al", "fig", "figs", "eq", "eqs", "sec", "ref", "refs", "tab",
    "no", "vol", "pp", "dr", "prof", "vs", "approx", "resp", "cf", "al",
}
SENT_END = re.compile(r"(?<=[.!?。！？])\s+")
HEADING_NUM = re.compile(r"^\s*(\d+(\.\d+)*\.?|[IVX]+\.)\s+[A-Z]")
HEADING_WORDS = {
    "abstract", "introduction", "related work", "background", "method", "methods",
    "methodology", "experiments", "experimental setup", "results", "discussion",
    "conclusion", "conclusions", "limitations", "appendix", "references",
    "materials and methods", "results and discussion", "data availability",
}


def page_text_pymupdf(path: Path) -> list[str] | None:
    try:
        import fitz  # type: ignore
    except Exception:
        return None
    try:
        doc = fitz.open(path)
        return [page.get_text("text") for page in doc]
    except Exception:
        return None


def page_text_pdfplumber(path: Path) -> list[str] | None:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return None
    try:
        with pdfplumber.open(path) as pdf:
            return [(p.extract_text() or "") for p in pdf.pages]
    except Exception:
        return None


def page_text_pypdf(path: Path) -> list[str] | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None
    try:
        reader = PdfReader(str(path))
        return [(p.extract_text() or "") for p in reader.pages]
    except Exception:
        return None


def page_text_pdftotext(path: Path) -> list[str] | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True,
                             text=True, encoding="utf-8", timeout=120)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return out.stdout.split("\f")
    except Exception:
        return None


def load_pages(path: Path) -> tuple[list[str], str]:
    if path.suffix.lower() in {".txt", ".md", ".text"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        pages = re.split(r"\n\s*\n\s*\[?page\s+\d+[^\n]*\]?\s*\n", text, flags=re.I)
        if len(pages) == 1:
            # no page markers: cut on form feed, otherwise treat the whole file as one page
            pages = text.split("\f") if "\f" in text else [text]
        return pages, "plain_text"
    if path.suffix.lower() != ".pdf":
        raise SystemExit(f"unsupported input type: {path.suffix}")
    for name, fn in (("pymupdf", page_text_pymupdf), ("pdfplumber", page_text_pdfplumber),
                     ("pypdf", page_text_pypdf), ("pdftotext", page_text_pdftotext)):
        pages = fn(path)
        if pages and any(p.strip() for p in pages):
            return pages, name
    raise SystemExit("no_pdf_extractor: install pymupdf, pdfplumber or pypdf, or provide the text layer")


SECTION_PREFIX = re.compile(
    r"^(?:(\d+(?:\.\d+)*)\.?\s+)?"
    r"(Abstract|Introduction|Related Work|Background|Materials and Methods|Methods?|Methodology|"
    r"Experiments?|Experimental Setup|Results?|Discussion|Conclusions?|Limitations|Appendix|References)"
    r"\.?\s+", re.I)


def split_section_prefix(para: str) -> tuple[str | None, str]:
    """Many papers put the heading and the first sentence in one paragraph."""
    m = SECTION_PREFIX.match(para)
    if not m:
        return None, para
    num = m.group(1)
    name = m.group(2)
    heading = f"{num}. {name}" if num else name
    return heading, para[m.end():].strip()


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 90:
        return False
    if s.lower().rstrip(":").strip() in HEADING_WORDS:
        return True
    if HEADING_NUM.match(s) and not s.rstrip().endswith((".", "。")):
        return True
    words = s.split()
    if 1 <= len(words) <= 8 and s == s.upper() and not any(ch.isdigit() for ch in s):
        return True
    return False


def split_paragraphs(page: str) -> list[str]:
    lines = page.splitlines()
    paras: list[str] = []
    buf: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        buf.append(s)
    if buf:
        paras.append(" ".join(buf))
    return paras


def split_sentences(para: str) -> list[str]:
    out: list[str] = []
    for piece in SENT_END.split(para):
        p = piece.strip()
        if not p:
            continue
        # a sentence ending in a known abbreviation is glued back to the next one
        tail = p.rsplit(" ", 1)[-1].lower().rstrip(".")
        if tail in ABBREV and out is not None:
            if out:
                out[-1] = out[-1] + " " + p
            else:
                out.append(p)
            continue
        out.append(p)
    # merge stray fragments left by decimal points or initials
    merged: list[str] = []
    for s in out:
        if merged and len(s.split()) <= 2 and not s[0].isupper():
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-sentences", type=int, default=2000)
    args = ap.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(json.dumps({"status": "unable", "reason": "input_missing", "path": str(path)}), file=sys.stderr)
        return 2

    try:
        pages, extractor = load_pages(path)
    except SystemExit as exc:
        print(json.dumps({"status": "unable", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    sentences: list[dict] = []
    section = "S0 Front matter"
    sections: list[dict] = [{"section": section, "title": "Front matter", "start_page": 1}]
    empty_pages: list[int] = []

    for page_no, page in enumerate(pages, 1):
        if not page.strip():
            empty_pages.append(page_no)
            continue
        for para_no, para in enumerate(split_paragraphs(page), 1):
            prefix, rest = split_section_prefix(para)
            if prefix:
                section = f"S{len(sections)} {prefix[:70]}"
                sections.append({"section": section, "title": prefix[:70], "start_page": page_no})
                para = rest
                if not para:
                    continue
            if is_heading(para):
                section = f"S{len(sections)} {para.strip()[:70]}"
                sections.append({"section": section, "title": para.strip()[:70], "start_page": page_no})
                continue
            for sent in split_sentences(para):
                if len(sent) < 12:
                    continue
                sentences.append({
                    "sid": f"s{len(sentences) + 1:04d}",
                    "page": page_no,
                    "para": para_no,
                    "section": section,
                    "text": sent,
                    "chars": len(sent),
                })
                if len(sentences) >= args.max_sentences:
                    break
            if len(sentences) >= args.max_sentences:
                break
        if len(sentences) >= args.max_sentences:
            break

    payload = {
        "paper": {
            "path": str(path),
            "extractor": extractor,
            "pages": len(pages),
            "empty_pages": empty_pages,
            "title_guess": sentences[0]["text"][:120] if sentences else "",
        },
        "sections": sections,
        "sentences": sentences,
        "stats": {
            "sentences": len(sentences),
            "sections": len(sections),
            "truncated": len(sentences) >= args.max_sentences,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok" if sentences else "partial",
                      "reason": "" if sentences else "no_text_layer",
                      "extractor": extractor, **payload["stats"], "out": str(out)}, ensure_ascii=False))
    return 0 if sentences else 3


if __name__ == "__main__":
    sys.exit(main())
