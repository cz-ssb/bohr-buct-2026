#!/usr/bin/env python3
"""Generate a synthetic multi-page paper PDF for end-to-end self-testing."""
import pymupdf

SECTIONS = [
    ("Abstract", [
        "We study whether sparse attention budgets preserve retrieval accuracy in long-context question answering.",
        "On three long-document benchmarks we compare a fixed 12.5% token budget against full attention.",
        "Retrieval accuracy drops by 3.4 points on average, but the drop is concentrated on multi-hop questions.",
        "We release the evaluation harness and all per-question predictions.",
    ]),
    ("1 Introduction", [
        "Long-context models are usually evaluated with a single aggregate score, which hides where attention fails.",
        "Prior work reports near-parity between sparse and dense attention at moderate sequence lengths.",
        "We ask a narrower question: at which question types does a sparse budget actually lose information?",
        "Our contribution is a per-question-type breakdown rather than a new attention mechanism.",
        "We also report the compute saved, because a 12.5% budget is only useful if the saving is real.",
    ]),
    ("2 Related Work", [
        "Sparse attention variants differ mainly in how they select which keys survive the budget.",
        "Block-sparse methods pool neighbouring tokens; learned routers score each key independently.",
        "Both families report aggregate accuracy, and both evaluate on the same three benchmarks we use.",
        "A recent survey notes that multi-hop questions are under-represented in these benchmark mixes.",
        "We therefore stratify our analysis by question type instead of reporting one number.",
    ]),
    ("3 Method", [
        "We keep the pretrained weights fixed and swap only the attention mask at inference time.",
        "The budget is applied per layer with a fixed ratio of 12.5% of the sequence length.",
        "Key selection uses a learned router trained on 2,000 synthetic long documents for 3 epochs.",
        "We do not retrain the base model; all reported numbers come from inference-only changes.",
        "All experiments run on 8 A100 GPUs with a batch size of 4 and no gradient checkpointing.",
        "The router adds 1.2 million parameters, which is 0.08% of the base model size.",
    ]),
    ("4 Experiments", [
        "We evaluate on three benchmarks: NarrativeQA, Qasper and MultiHop-Long.",
        "Each benchmark contributes 500 held-out questions, for 1,500 questions in total.",
        "Accuracy is exact-match against the annotated answer span, scored by two annotators.",
        "Inter-annotator agreement is 0.91 Cohen kappa on a 200-question overlap sample.",
        "Baselines are full attention, block-sparse attention and the learned router without a budget.",
    ]),
    ("5 Results", [
        "Full attention reaches 71.8% exact match averaged over the three benchmarks.",
        "The 12.5% budget reaches 68.4%, a drop of 3.4 points.",
        "On MultiHop-Long the drop is 6.1 points, while on Qasper it is only 1.9 points.",
        "Block-sparse attention loses 4.7 points, so the learned router recovers 1.3 points over it.",
        "Inference time falls from 41.2 to 18.6 seconds per 32k-token document.",
        "Memory for the key cache falls by 87.5%, consistent with the budget ratio.",
    ]),
    ("6 Discussion", [
        "The loss is not uniform: multi-hop questions depend on distractor keys that the router discards.",
        "At 25% budget the drop shrinks to 1.1 points, which suggests 12.5% is near a practical floor.",
        "Our router was trained on synthetic documents, so domain shift remains untested.",
        "We did not evaluate on code or multilingual inputs, which limits the claim.",
        "The compute saving is measured on a single hardware configuration.",
    ]),
    ("7 Conclusion", [
        "A 12.5% attention budget is viable for single-hop retrieval at a 1.9-point cost.",
        "It is not viable for multi-hop questions, where the cost is 6.1 points.",
        "Reporting one aggregate number would have hidden this difference entirely.",
        "Future work should train the router on in-domain documents and test code inputs.",
    ]),
]

PAGE_BREAKS = {"3 Method", "5 Results"}


def build(out_path):
    doc = pymupdf.open()
    page = None
    y = 0

    def new_page():
        nonlocal page, y
        page = doc.new_page(width=595, height=842)
        y = 60

    new_page()
    page.insert_text((72, y), "Sparse Attention Budgets and Retrieval Accuracy",
                     fontsize=16, fontname="hebo")
    y += 24
    page.insert_text((72, y), "A. Researcher, B. Coauthor, C. Third",
                     fontsize=10, fontname="helv")
    y += 14
    page.insert_text((72, y), "Institute of Synthetic Results, Technical Report TR-2026-114",
                     fontsize=9, fontname="helv")
    y += 22
    page.insert_text((72, y), "Preprint. Not peer reviewed. Synthetic document for testing only.",
                     fontsize=8, fontname="helv")
    y += 26

    for title, lines in SECTIONS:
        if title in PAGE_BREAKS:
            new_page()
        if y > 760:
            new_page()
        page.insert_text((72, y), title, fontsize=12, fontname="hebo")
        y += 10
        page.draw_line(pymupdf.Point(72, y), pymupdf.Point(523, y), width=0.5)
        y += 14
        for line in lines:
            # wrap at ~92 chars
            words, buf = line.split(), ""
            chunks = []
            for w in words:
                if len(buf) + len(w) + 1 > 92:
                    chunks.append(buf)
                    buf = w
                else:
                    buf = (buf + " " + w).strip()
            if buf:
                chunks.append(buf)
            for c in chunks:
                if y > 780:
                    new_page()
                page.insert_text((72, y), c, fontsize=10, fontname="helv")
                y += 14
            y += 3
        y += 8

    # page numbers
    for i, p in enumerate(doc):
        p.insert_text((290, 810), str(i + 1), fontsize=9, fontname="helv")

    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "test_paper.pdf"
    build(out)
    d = pymupdf.open(out)
    print(f"created {out} pages={d.page_count}")
    d.close()
