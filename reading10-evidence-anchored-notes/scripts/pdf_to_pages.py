#!/usr/bin/env python3
"""Extract page-indexed text from a paper, with an honest record of how it was read.

Order of extractors: pymupdf / fitz -> pdfplumber -> pypdf -> pdftotext CLI.
An empty text layer triggers an optional OCR pass (tesseract CLI) when available;
otherwise the page is marked empty and the run reports itself as degraded.

Usage:
  python pdf_to_pages.py --input paper.pdf --out work/pages.json [--ocr auto|off] [--dpi 200]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path


def _clean(t: str) -> str:
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip("\n")


SENT_END = re.compile(r"[.。!?！？;；]$")


def _blocks_from_text(text, max_sent=3, max_chars=320):
    """Regroup a flat line-per-sentence extract into paragraph-sized blocks.

    Extractors without layout information (pypdf, pdftotext, plain text) still
    need paragraph units, otherwise one whole section collapses into a single
    unverifiable anchor. A short line with no sentence-final punctuation reads
    as a heading and stands alone; body lines accumulate into small paragraphs.
    """
    blocks, buf, sent_in_buf = [], [], 0

    def flush():
        nonlocal buf, sent_in_buf
        if buf:
            blocks.append({"text": " ".join(buf).strip(), "bbox": None})
            buf, sent_in_buf = [], 0

    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            flush()
            continue
        if len(s) <= 70 and not SENT_END.search(s):
            flush()
            blocks.append({"text": s, "bbox": None})
            continue
        buf.append(s)
        if SENT_END.search(s):
            sent_in_buf += 1
        if sent_in_buf >= max_sent or sum(len(x) for x in buf) >= max_chars:
            flush()
    flush()
    return blocks


def _blocks_of(page):
    """Real paragraph units from the layout engine.

    A flat get_text("text") loses paragraph boundaries, which is exactly what
    section alignment and anchor granularity depend on, so keep the block boxes.
    """
    out = []
    try:
        raw = page.get_text("blocks")
    except Exception:
        return out
    for b in raw:
        # (x0, y0, x1, y1, text, block_no, block_type); type 1 is an image block
        if len(b) >= 7 and b[6] != 0:
            continue
        txt = _clean(b[4] if isinstance(b[4], str) else "")
        if not txt:
            continue
        out.append({"text": txt,
                    "bbox": [round(float(v), 1) for v in b[:4]]})
    return out


def _via_pymupdf(path):
    try:
        import pymupdf  # modern name
    except Exception:
        try:
            import fitz as pymupdf  # legacy name
        except Exception:
            return None
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        raise PermissionError("encrypted_pdf")
    pages = []
    for i, p in enumerate(doc):
        pages.append({"page": i + 1, "text": _clean(p.get_text("text")),
                      "blocks": _blocks_of(p)})
    meta = doc.metadata or {}
    return {"extractor": "pymupdf", "pages": pages, "meta": meta}


def _via_pdfplumber(path):
    try:
        import pdfplumber
    except Exception:
        return None
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for i, p in enumerate(pdf.pages):
            pages.append({"page": i + 1, "text": _clean(p.extract_text() or "")})
    return {"extractor": "pdfplumber", "pages": pages, "meta": {}}


def _via_pypdf(path):
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            return None
    reader = PdfReader(str(path))
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            raise PermissionError("encrypted_pdf")
    pages = [{"page": i + 1, "text": _clean(p.extract_text() or "")} for i, p in enumerate(reader.pages)]
    return {"extractor": "pypdf", "pages": pages, "meta": {}}


def _via_pdftotext(path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.txt"
        subprocess.run([exe, "-layout", str(path), str(out)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raw = out.read_text(encoding="utf-8", errors="ignore")
    pages = [{"page": i + 1, "text": _clean(chunk)} for i, chunk in enumerate(raw.split("\f"))]
    return {"extractor": "pdftotext", "pages": pages, "meta": {}}


def _via_docx(path):
    try:
        import docx  # python-docx
    except Exception:
        import zipfile, html
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        text = html.unescape(re.sub(r"<[^>]+>", "", xml))
        return {"extractor": "docx-xml", "pages": [{"page": 1, "text": _clean(text)}], "meta": {}}
    d = docx.Document(str(path))
    text = "\n".join(p.text for p in d.paragraphs)
    return {"extractor": "python-docx", "pages": [{"page": 1, "text": _clean(text)}], "meta": {}}


def _ocr_page(pdf_path, page_no, dpi):
    """Render one page and OCR it with tesseract; returns text or None."""
    tess = shutil.which("tesseract")
    if not tess:
        return None
    try:
        import pymupdf
    except Exception:
        try:
            import fitz as pymupdf
        except Exception:
            return None
    doc = pymupdf.open(str(pdf_path))
    pix = doc[page_no - 1].get_pixmap(dpi=dpi)
    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "p.png"
        pix.save(str(img))
        proc = subprocess.run([tess, str(img), "stdout", "-l", "eng+chi_sim"],
                              capture_output=True, text=True)
    return _clean(proc.stdout) if proc.stdout.strip() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ocr", choices=["auto", "off"], default="auto")
    ap.add_argument("--dpi", type=int, default=200)
    a = ap.parse_args()

    src = Path(a.input)
    degraded, notes = [], []
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        sys.exit(2)

    suffix = src.suffix.lower()
    result = None
    if suffix in (".pdf", ".PDF"):
        for fn in (_via_pymupdf, _via_pdfplumber, _via_pypdf, _via_pdftotext):
            try:
                result = fn(src)
            except PermissionError:
                result = {"extractor": fn.__name__, "pages": [], "meta": {},
                          "error": "encrypted_pdf"}
                break
            except Exception as e:  # extractor broken -> try the next one
                notes.append(f"{fn.__name__} failed: {type(e).__name__}")
                result = None
            if result:
                break
    elif suffix in (".docx", ".doc"):
        result = _via_docx(src)
    elif suffix in (".txt", ".md", ".markdown"):
        result = {"extractor": "plain-text",
                  "pages": [{"page": 1, "text": _clean(src.read_text(encoding="utf-8", errors="ignore"))}],
                  "meta": {}}
    else:
        print(f"unsupported input type: {suffix}", file=sys.stderr)
        sys.exit(2)

    if not result:
        print("no extractor available for this file", file=sys.stderr)
        sys.exit(3)

    empty = [p["page"] for p in result["pages"] if len(p["text"]) < 60]
    if empty and a.ocr == "auto" and suffix == ".pdf":
        recovered, still_empty = 0, []
        for pno in empty:
            txt = _ocr_page(src, pno, a.dpi)
            if txt:
                result["pages"][pno - 1]["text"] = txt
                recovered += 1
            else:
                still_empty.append(pno)
        if recovered:
            result["extractor"] += "+ocr"
            notes.append(f"ocr_recovered_pages={recovered}")
        if still_empty:
            degraded.append("empty_pages_after_ocr:" + ",".join(map(str, still_empty)))
    elif empty:
        degraded.append("empty_pages:" + ",".join(map(str, empty)))

    # two-column suspicion: many short lines ending mid-thought on one page
    for p in result["pages"]:
        lines = [l for l in p["text"].split("\n") if l.strip()]
        if len(lines) > 25:
            short = sum(1 for l in lines if len(l) < 45)
            if short / len(lines) > 0.6:
                degraded.append(f"column_order_suspect:p{p['page']}")

    # every page must carry paragraph blocks; regroup when the extractor had none
    for p in result["pages"]:
        if not p.get("blocks"):
            p["blocks"] = _blocks_from_text(p["text"])
            notes.append(f"blocks_regrouped:p{p['page']}")

    payload = {
        "source": str(src),
        "extractor": result.get("extractor", "unknown"),
        "error": result.get("error"),
        "pages": [{"page": p["page"], "text": p["text"], "chars": len(p["text"]),
                   "blocks": p.get("blocks") or []} for p in result["pages"]],
        "stats": {
            "pages": len(result["pages"]),
            "chars": sum(len(p["text"]) for p in result["pages"]),
            "blocks": sum(len(p.get("blocks") or []) for p in result["pages"]),
            "empty_pages": len(empty),
        },
        "degraded": sorted(set(degraded)),
        "notes": notes,
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "extractor": payload["extractor"],
                      "pages": payload["stats"]["pages"], "chars": payload["stats"]["chars"],
                      "blocks": payload["stats"]["blocks"],
                      "degraded": payload["degraded"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
