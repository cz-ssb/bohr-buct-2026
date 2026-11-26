#!/usr/bin/env python3
"""Build chapter-aligned, anchor-bearing reading notes from extracted page text.

Everything structural (sections, paragraphs, anchors, evidence table) is produced
here deterministically; a model may only add short semantic fields afterwards.

Usage:
  python build_notes.py --pages work/pages.json --out app/output \
      [--case-json /input/case.json] [--paper paper.pdf]
"""
import argparse, csv, json, re
from pathlib import Path

HEAD_EN = ["abstract", "summary", "introduction", "background", "related work",
           "methods", "method", "methodology", "materials and methods", "experiments",
           "experimental setup", "results", "results and discussion", "discussion",
           "conclusions", "conclusion", "limitations", "outlook", "references",
           "acknowledgements", "acknowledgments", "appendix", "data availability"]
HEAD_ZH = ["摘要", "引言", "前言", "背景", "相关工作", "方法", "材料与方法", "实验",
           "结果", "结果与讨论", "讨论", "结论", "局限", "不足", "展望", "参考文献", "致谢", "附录"]

NUM_HEAD = re.compile(r"^(?:第)?(\d+(?:\.\d+)*)(?:[.、]|\s)\s*(.{2,60})")
ZH_NUM_HEAD = re.compile(r"^(?:一|二|三|四|五|六|七|八|九|十)[、.]\s*(.{2,30})")
UPPER_HEAD = re.compile(r"^([A-Z][A-Z \-]{3,40})$")
HEAD_PUNCT_END = re.compile(r"[.。!?！？;；]$")

SENT_SPLIT = re.compile(r"(?<=[。！？])\s*|(?<=[.])\s+(?=[A-Z(])")

CUES = {
    "research_question": r"(we (?:investigate|examine|address|ask|study|report|propose)|here we|this (?:study|work|paper)|我们(?:研究|考察|探讨|提出)|本文)",
    "data": r"(dataset|data set|corpus|cohort|sample|participant|N\s*=\s*\d+|数据集|样本|数据来源|受试者)",
    "method_conditions": r"(we (?:use|used|apply|applied|employ|compare|evaluat\w*|measur\w*|train\w*|run\w*|swap\w*|keep\w*|freez\w*|implement\w*)|using |based on|implement|under (?:the )?(?:condition|temperature|pressure)|模型|方法|采用|条件|设置)",
    "main_findings": r"((?:drop|drops|dropped|increase|increases|decrease|decreases|higher|lower|improv\w*|reach\w*|fall\w*|falls|lose\w*|loses|recover\w*)\b[^.]{0,40}?\d+(?:\.\d+)?|\d+(?:\.\d+)?\s?%\s*(?:exact match|accuracy|of questions)|p\s*[<=]\s*\d|±|significant|提高|降低|显著|分别)",
    "limitations": r"(limitation|caveat|however|future work|remains unclear|not (?:yet )?(?:clear|tested)|局限|不足|有待|尚不)",
}
FIELD_ORDER = ["research_question", "data", "method_conditions", "main_findings", "limitations"]
PREFER_SECTION = {
    "research_question": ("abstract", "introduction"),
    "data": ("methods", "results", "introduction", "experimental"),
    "method_conditions": ("methods", "method", "experimental", "materials"),
    "main_findings": ("results", "discussion"),
    "limitations": ("limitation", "discussion", "conclusion", "outlook"),
}


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _plausible_title(title):
    """Guard against a body sentence that merely starts with a number."""
    if not title or len(title) > 55:
        return False
    if HEAD_PUNCT_END.search(title):
        return False
    if title.count(",") > 1:
        return False
    return len(title.split()) <= 8


def classify_heading(line):
    """Return (level, title) when the line looks like a section heading."""
    s = norm(line).strip(" .:：")
    if not s or len(s) > 80:
        return None
    # a heading does not end in a sentence stop
    if HEAD_PUNCT_END.search(s):
        return None
    low = s.lower().strip(" .:：")
    for h in HEAD_EN + HEAD_ZH:
        if low == h:
            return 1, s
    m = NUM_HEAD.match(s)
    if m:
        title = m.group(2).strip(" .:：")
        tlow = title.lower()
        if any(tlow.startswith(h) or h.startswith(tlow[:12]) for h in HEAD_EN) or \
           any(title.startswith(h) for h in HEAD_ZH) or _plausible_title(title):
            return m.group(1).count(".") + 1, title
    m = ZH_NUM_HEAD.match(s)
    if m:
        return 1, m.group(1).strip()
    m = UPPER_HEAD.match(s)
    if m and m.group(1).strip().lower() in HEAD_EN:
        return 1, m.group(1).strip()
    return None


SENT_END = re.compile(r"[.。!?！？;；]$")


def regroup_blocks(text, max_sent=3, max_chars=320):
    """Fallback paragraph units for a pages.json that carries no blocks.

    Without layout information one flat line-per-sentence dump collapses a whole
    section into a single unverifiable anchor, so regroup into small paragraphs
    and let short punctuation-free lines stand as headings.
    """
    blocks, buf, sent = [], [], 0

    def flush():
        nonlocal buf, sent
        if buf:
            blocks.append(" ".join(buf).strip())
            buf, sent = [], 0

    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            flush()
            continue
        if len(s) <= 70 and not SENT_END.search(s):
            flush()
            blocks.append(s)
            continue
        buf.append(s)
        if SENT_END.search(s):
            sent += 1
        if sent >= max_sent or sum(len(x) for x in buf) >= max_chars:
            flush()
    flush()
    return blocks


def build_structure(pages):
    sections, cur, counter = [], None, 0
    for p in pages:
        blocks = [b["text"] for b in (p.get("blocks") or [])
                  if isinstance(b, dict) and b.get("text")]
        units = blocks or regroup_blocks(p["text"])
        for unit in units:
            lines = [l for l in unit.split("\n") if l.strip()]
            if not lines:
                continue
            head = classify_heading(lines[0])
            body = norm(" ".join(lines[1:]))
            if head:
                if cur is not None:
                    cur["end_page"] = p["page"]
                    sections.append(cur)
                counter += 1
                cur = {"sid": f"S{counter}", "title": head[1], "level": head[0],
                       "start_page": p["page"], "end_page": p["page"], "paragraphs": []}
                if not body:
                    continue
                unit = body  # a heading sharing its block with the first paragraph
            if cur is None:
                cur = {"sid": "S0", "title": "Front matter（论文题头，非正文章节）", "level": 1,
                       "start_page": p["page"], "end_page": p["page"], "paragraphs": []}
            para_idx = len(cur["paragraphs"]) + 1
            aid = f"a-{cur['sid'].lower()}-{para_idx}"
            cur["paragraphs"].append({"anchor": {
                "anchor_id": aid, "page": p["page"], "section": cur["sid"],
                "section_title": cur["title"], "paragraph": para_idx,
                "quote": norm(unit)[:120]}, "text": unit})
    if cur is not None:
        cur["end_page"] = pages[-1]["page"] if pages else cur["start_page"]
        sections.append(cur)
    return sections


def sentences_of(sections):
    out = []
    for sec in sections:
        for para in sec["paragraphs"]:
            for sent in SENT_SPLIT.split(para["text"]):
                s = norm(sent)
                if len(s) < 15:
                    continue
                out.append({"text": s, "section": sec["sid"], "section_title": sec["title"],
                            "anchor_id": para["anchor"]["anchor_id"],
                            "page": para["anchor"]["page"]})
    return out


def pick(snips, field):
    pat = re.compile(CUES[field], re.I)
    pref = PREFER_SECTION[field]
    hits = []
    for s in snips:
        if not pat.search(s["text"]):
            continue
        tlow = s["section_title"].lower()
        rank = next((i for i, p in enumerate(pref) if p in tlow), len(pref))
        hits.append((rank, -len(s["text"]), s))
    if not hits:
        return None
    hits.sort(key=lambda x: (x[0], x[1]))
    return hits[0][2]


def build_card(snips, sections):
    card = {}
    for f in FIELD_ORDER:
        hit = pick(snips, f)
        if hit:
            card[f] = {"value": hit["text"][:240], "evidence": [hit["anchor_id"]],
                       "status": "reported", "page": hit["page"]}
        else:
            card[f] = {"value": None, "evidence": [], "status": "not_reported",
                       "note": "材料中未检出支撑该字段的表述，需人工确认"}
    return card


ABBR = re.compile(r"([A-Za-z][A-Za-z\- ]{4,60}?)\s*\(([A-Z]{2,8})\)")
DEFN = re.compile(r"(\b[A-Za-z][A-Za-z\-]{2,40}\b)\s+(?:is|are|refers to|denotes|means)\s+([^.;]{12,200})")


def build_knowledge(snips, lexicon):
    items, seen = [], set()
    for s in snips:
        for m in ABBR.finditer(s["text"]):
            term, longform = m.group(2), norm(m.group(1))
            if term in seen:
                continue
            seen.add(term)
            items.append({"term": term, "definition": longform, "kind": "abbreviation",
                          "anchor_id": s["anchor_id"], "page": s["page"]})
        for m in DEFN.finditer(s["text"]):
            term = m.group(1).strip()
            if term.lower() in seen or len(term) < 3:
                continue
            seen.add(term.lower())
            items.append({"term": term, "definition": norm(m.group(2)), "kind": "concept",
                          "anchor_id": s["anchor_id"], "page": s["page"]})
    for term, definition in (lexicon or {}).items():
        if term.lower() not in seen:
            items.append({"term": term, "definition": definition, "kind": "lexicon",
                          "anchor_id": None, "page": None})
    return items[:40]


def section_notes(sections):
    out = []
    for sec in sections:
        snips = []
        for para in sec["paragraphs"]:
            for sent in SENT_SPLIT.split(para["text"]):
                s = norm(sent)
                if len(s) > 15:
                    snips.append({"text": s, "anchor_id": para["anchor"]["anchor_id"],
                                  "page": para["anchor"]["page"]})
        if sec["sid"] == "S0":
            # the title block is not a chapter; keep its place but do not force
            # purpose/method/result/conclusion onto a title and an author line
            out.append({"section": sec["sid"], "title": sec["title"],
                        "role": "front_matter",
                        "pages": [sec["start_page"], sec["end_page"]],
                        "purpose": None, "method": None, "result": None, "conclusion": None})
            continue
        base = {"section": sec["sid"], "title": sec["title"], "role": "section",
                "pages": [sec["start_page"], sec["end_page"]]}
        if not snips:
            out.append({**base, "purpose": None, "method": None,
                        "result": None, "conclusion": None})
            continue
        result = next(({"text": s["text"][:200], "anchor_id": s["anchor_id"]}
                       for s in snips if re.search(CUES["main_findings"], s["text"], re.I)), None)
        result_anchor = result["anchor_id"] if result else None
        # a sentence already used as the result must not be re-used as the method
        method = next(({"text": s["text"][:200], "anchor_id": s["anchor_id"]}
                       for s in snips if s["anchor_id"] != result_anchor
                       and re.search(CUES["method_conditions"], s["text"], re.I)), None)
        used = {x["anchor_id"] for x in (result, method) if x}
        # the closing sentence should not merely repeat the result sentence
        closing = next((s for s in reversed(snips) if s["anchor_id"] not in used),
                       snips[-1])
        opening = next((s for s in snips if s["anchor_id"] not in used and s is not closing),
                       snips[0])
        out.append({**base,
                    "purpose": {"text": opening["text"][:200], "anchor_id": opening["anchor_id"]},
                    "method": method, "result": result,
                    "conclusion": {"text": closing["text"][:200], "anchor_id": closing["anchor_id"]}})
    return out


def render_md(outdir, secnotes, knowledge, anchors, paper):
    lines = [f"# 结构化阅读笔记 / Structured reading notes", "", f"Paper: `{paper or ''}`", ""]
    for sec in secnotes:
        lines.append(f"## {sec['section']} {sec['title']}  \n_p.{sec['pages'][0]}–{sec['pages'][1]}_")
        if sec.get("role") == "front_matter":
            lines.append("- 题头信息（标题 / 作者 / 机构），保留为可核验锚点，不作为正文章节评分")
            lines.append("")
            continue
        for key, label in (("purpose", "目的"), ("method", "方法"), ("result", "结果"), ("conclusion", "结论")):
            v = sec.get(key)
            if not v:
                lines.append(f"- **{label}**: 未检出（not_reported）")
                continue
            aid = v["anchor_id"]
            page = next((x["page"] for x in anchors if x["anchor_id"] == aid), "?")
            lines.append(f"- **{label}**: {v['text']} `[p.{page} | {aid}]`")
        lines.append("")
    if knowledge:
        lines.append("## 知识点 / Knowledge items")
        for k in knowledge:
            anchor = f" `[{k['anchor_id']}]`" if k.get("anchor_id") else " `[lexicon]`"
            lines.append(f"- **{k['term']}**（{k['kind']}）: {k['definition']}{anchor}")
        lines.append("")
    (outdir / "notes.md").write_text("\n".join(lines), encoding="utf-8")


def render_csv(outdir, sections, card, anchors):
    with (outdir / "evidence.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["anchor_id", "page", "section", "paragraph", "quote", "kind"])
        # the section cut itself is an auditable step, not just the paragraphs
        for s in sections:
            w.writerow([f"{s['sid']}-head", s["start_page"], s["sid"], 0,
                        f"heading: {s['title']}", "section"])
        for s in sections:
            for p in s["paragraphs"]:
                a = p["anchor"]
                w.writerow([a["anchor_id"], a["page"], a["section"], a["paragraph"], a["quote"], "paragraph"])
        for fname, v in card.items():
            for aid in v.get("evidence", []):
                sec = next((x["section"] for x in anchors if x["anchor_id"] == aid), "")
                w.writerow([aid, v.get("page", ""), sec, "", (v.get("value") or "")[:120], f"card:{fname}"])


def anchors_to_sections(anchors):
    """Minimal section view rebuilt from anchors.json, for re-rendering the CSV."""
    secs = {}
    for a in anchors:
        sid = a["section"]
        s = secs.get(sid)
        if s is None:
            s = secs[sid] = {"sid": sid, "title": a.get("section_title", ""),
                             "start_page": a["page"], "end_page": a["page"], "paragraphs": []}
        s["start_page"] = min(s["start_page"], a["page"])
        s["end_page"] = max(s["end_page"], a["page"])
        s["paragraphs"].append({"anchor": a, "text": a["quote"]})
    return sorted(secs.values(), key=lambda s: (len(s["sid"]), s["sid"]))


def apply_fill(outdir, fill_path):
    """Merge a model-authored semantic_fill.json into the produced notes.

    The model may only write text plus an anchor_id that already exists in
    anchors.json. A fill pointing at an invented anchor is rejected here, before
    validation, so it can never reach the delivered notes.
    """
    fill = json.loads(Path(fill_path).read_text(encoding="utf-8"))
    adoc = json.loads((outdir / "anchors.json").read_text(encoding="utf-8"))
    anchors = adoc["anchors"]
    ids = {a["anchor_id"] for a in anchors}
    bad = []

    def check(aid, where):
        if aid is not None and aid not in ids:
            bad.append(f"{where}:{aid}")

    card_doc = json.loads((outdir / "paper_card.json").read_text(encoding="utf-8"))
    n_fields = 0
    for fname, ent in (fill.get("fields") or {}).items():
        if fname not in FIELD_ORDER:
            bad.append(f"fields:{fname} not a contract field")
            continue
        aid = ent.get("anchor_id")
        check(aid, f"fields.{fname}")
        card_doc["fields"][fname] = {
            "value": ent.get("value") or ent.get("text"),
            "evidence": [aid] if aid else [],
            "status": ent.get("status") or "reported",
            "page": next((a["page"] for a in anchors if a["anchor_id"] == aid), None)}
        n_fields += 1

    notes_doc = json.loads((outdir / "notes.json").read_text(encoding="utf-8"))
    by_sid = {s["section"]: s for s in notes_doc["sections"]}
    n_secs = 0
    for sid, fields in (fill.get("sections") or {}).items():
        sec = by_sid.get(sid)
        if sec is None:
            bad.append(f"sections:{sid} is not a known section")
            continue
        for key in ("purpose", "method", "result", "conclusion"):
            v = (fields or {}).get(key)
            if not v:
                continue
            aid = v.get("anchor_id")
            check(aid, f"{sid}.{key}")
            sec[key] = {"text": (v.get("text") or "")[:200], "anchor_id": aid}
        n_secs += 1
    for item in (fill.get("knowledge_items") or []):
        aid = item.get("anchor_id")
        check(aid, f"knowledge:{item.get('term')}")
        notes_doc["knowledge_items"].append({
            "term": item.get("term"), "definition": item.get("definition"),
            "kind": item.get("kind", "concept"), "anchor_id": aid})

    if bad:
        print(json.dumps({"ok": False, "code": "fill_anchor_invalid",
                          "detail": bad[:10]}, ensure_ascii=False))
        raise SystemExit(4)

    (outdir / "paper_card.json").write_text(json.dumps(card_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "notes.json").write_text(json.dumps(notes_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    render_md(outdir, notes_doc["sections"], notes_doc["knowledge_items"], anchors, adoc.get("paper", ""))
    render_csv(outdir, anchors_to_sections(anchors), card_doc["fields"], anchors)

    rpath = outdir / "result.json"
    if rpath.exists():
        res = json.loads(rpath.read_text(encoding="utf-8"))
        # contract fields declared by case.json are filled here, never invented
        n_result = 0
        for k, val in (fill.get("result") or {}).items():
            if k not in res:
                bad.append(f"result:{k} is not a declared contract field")
                continue
            res[k] = val
            n_result += 1
        if bad:
            print(json.dumps({"ok": False, "code": "fill_field_invalid",
                              "detail": bad[:10]}, ensure_ascii=False))
            raise SystemExit(4)
        res.setdefault("change_log", []).append({"step": "semantic_fill", "source": Path(fill_path).name,
                                                 "fields": n_fields, "sections": n_secs,
                                                 "result_fields": n_result})
        rpath.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"filled_fields": n_fields, "filled_sections": n_secs,
            "knowledge_items": len(notes_doc["knowledge_items"])}


def write_outputs(outdir, pages_payload, sections, card, knowledge, secnotes, case_json, paper):
    outdir.mkdir(parents=True, exist_ok=True)
    anchors = [p["anchor"] for s in sections for p in s["paragraphs"]]
    (outdir / "anchors.json").write_text(
        json.dumps({"paper": str(paper or ""), "anchors": anchors}, ensure_ascii=False, indent=2), encoding="utf-8")

    card_doc = {"paper": str(paper or ""), "fields": card,
                "field_order": FIELD_ORDER,
                "status_counts": {k: sum(1 for v in card.values() if v["status"] == k)
                                  for k in ("reported", "not_reported", "uncertain", "conflict")}}
    (outdir / "paper_card.json").write_text(json.dumps(card_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    notes = {"paper": str(paper or ""), "sections": secnotes,
             "knowledge_items": knowledge,
             "anchors_total": len(anchors)}
    (outdir / "notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    render_md(outdir, secnotes, knowledge, anchors, paper)
    render_csv(outdir, sections, card, anchors)


    skeleton = {"case_id": None, "status": "partial" if pages_payload.get("degraded") else "success",
                "status_reason": "; ".join(pages_payload.get("degraded", [])) or None,
                "sources": {"paper": str(paper or ""), "extractor": pages_payload.get("extractor"),
                            "pages": pages_payload.get("stats", {}).get("pages")},
                "uncertainty": [], "change_log": []}
    # extraction-level caveats belong in uncertainty, where a human will look
    for d in pages_payload.get("degraded", []):
        skeleton["uncertainty"].append({"kind": "extraction", "detail": d,
                                        "needs_human": True})
    for n in pages_payload.get("notes", []):
        skeleton["change_log"].append({"step": "pdf_to_pages", "detail": n})
    if case_json:
        try:
            case = json.loads(Path(case_json).read_text(encoding="utf-8"))
            skeleton["case_id"] = case.get("case_id") or case.get("id")
            for k in (case.get("output_contract") or {}).keys():
                skeleton[k] = None
        except Exception as e:
            skeleton["uncertainty"].append({"kind": "case_json",
                                            "detail": f"case.json unreadable: {type(e).__name__}",
                                            "needs_human": True})
    (outdir / "result.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"anchors": len(anchors), "sections": len(sections), "knowledge": len(knowledge)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--case-json")
    ap.add_argument("--paper", default="")
    ap.add_argument("--lexicon", default="")
    ap.add_argument("--fill", default="")
    a = ap.parse_args()

    payload = json.loads(Path(a.pages).read_text(encoding="utf-8"))
    pages = payload["pages"]
    sections = build_structure(pages)
    snips = sentences_of(sections)
    card = build_card(snips, sections)
    lexicon = {}
    if a.lexicon and Path(a.lexicon).exists():
        raw = json.loads(Path(a.lexicon).read_text(encoding="utf-8"))
        lexicon = raw.get("entries", raw) if isinstance(raw, dict) else {}
    knowledge = build_knowledge(snips, lexicon)
    secnotes = section_notes(sections)
    stats = write_outputs(Path(a.out), payload, sections, card, knowledge, secnotes,
                          a.case_json, a.paper or payload.get("source"))
    if a.fill:
        stats["fill"] = apply_fill(Path(a.out), a.fill)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
