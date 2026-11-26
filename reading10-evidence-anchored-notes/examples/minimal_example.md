# 最小调用示例 / Minimal worked example

> **这是示例（example），不是正式案例结果。** 所用论文是本仓库 `selftest/gen_test_paper.py` 生成的合成 PDF（3 页，题为 *Sparse Attention Budgets and Retrieval Accuracy*），不含任何真实论文内容。正式评测由平台用其固定案例运行，本示例只用来展示接口与输出形状。

## 1. 输入

```
case.json            # 平台提供，含 case_id 与 output_contract
test_paper.pdf       # 3 页合成论文，含 Abstract / Introduction / Method / Results / Discussion / Conclusion
```

`case.json`（示例）：

```json
{
  "case_id": "ST-READING10-01",
  "output_contract": {
    "notes_markdown": "notes.md",
    "paper_card": "paper_card.json",
    "evidence_table": "evidence.csv",
    "anchors": "anchors.json"
  }
}
```

## 2. 调用

```bash
# 抽取（带版面分块，页内段落边界保留）
python scripts/pdf_to_pages.py --input test_paper.pdf --out work/pages.json --ocr auto
#   -> {"extractor": "pymupdf", "pages": 3, "chars": 3741, "blocks": 55, "degraded": []}

# 建结构：章节、锚点、论文卡片、知识点，写出 6 个产物
python scripts/build_notes.py --pages work/pages.json --out app/output \
    --paper test_paper.pdf --case-json case.json
#   -> {"anchors": 47, "sections": 9, "knowledge": 9}

# 合并模型写的语义字段（锚点必须是已存在的 anchor_id）
python scripts/build_notes.py --pages work/pages.json --out app/output \
    --paper test_paper.pdf --case-json case.json --fill semantic_fill.json
#   -> {"fill": {"filled_fields": 5, "filled_sections": 3, "knowledge_items": 10}}

# 自检：锚点白名单、引文是否真在该页、契约字段是否齐
python scripts/validate_notes.py --dir app/output --pages work/pages.json --strict --skill-root .
#   -> {"ok": true, "checked": {"anchors": 47, "referenced": 29, "text_files": 9}, "violations": []}
```

## 3. 输出

### 章节切分与页码（`notes.md` 片段）

```
## S1 Abstract
_p.1–1_
- **目的**: 界定研究问题：稀疏预算在哪种题型上真正丢失信息 `[p.1 | a-s1-1]`
- **方法**: On three long-document benchmarks we compare a fixed 12.5% token budget against full attention. `[p.1 | a-s1-2]`
- **结果**: Retrieval accuracy drops by 3.4 points on average, but the drop is concentrated on multi-hop questions. `[p.1 | a-s1-3]`
- **结论**: We release the evaluation harness and all per-question predictions. `[p.1 | a-s1-4]`
```

注意三点：章节标题取自论文原文而不是套模板；每条笔记末尾带 `[页 | 锚点 id]`；一条句子不会被同时当作"方法"和"结果"。

### 论文卡片（`paper_card.json` 片段）

```json
{
  "main_findings": {
    "value": "全注意力 71.8% exact match，12.5% 预算 68.4%，整体降 3.4 点；多跳题降 6.1 点，Qasper 仅降 1.9 点",
    "evidence": ["a-s6-3"],
    "status": "reported",
    "page": 3
  },
  "limitations": {
    "value": null,
    "evidence": [],
    "status": "not_reported",
    "note": "材料中未检出支撑该字段的表述，需人工确认"
  }
}
```

`status: not_reported` 是一等答案。材料里没有就留空并标出来，不填一个看起来合理的数字。

### 证据表（`evidence.csv` 片段）

```csv
anchor_id,page,section,paragraph,quote,kind
S1-head,1,S1,0,heading: Abstract,section
S6-head,3,S6,0,heading: Results,section
a-s6-3,3,S6,3,On MultiHop-Long the drop is 6.1 points,paragraph
```

`kind=section` 的行让"章节切分"这一步本身也可复核，而不只是段落能被复核。

### 交付契约（`result.json`）

```json
{
  "case_id": "ST-READING10-01",
  "status": "success",
  "status_reason": null,
  "sources": {"paper": "test_paper.pdf", "extractor": "pymupdf", "pages": 3},
  "uncertainty": [],
  "change_log": [
    {"step": "pdf_to_pages", "detail": "blocks_regrouped:p2"},
    {"step": "semantic_fill", "source": "semantic_fill.json", "fields": 5, "sections": 3, "result_fields": 4}
  ],
  "notes_markdown": "notes.md",
  "paper_card": "paper_card.json",
  "evidence_table": "evidence.csv",
  "anchors": "anchors.json"
}
```

## 4. 语义填充文件长什么样

模型只写"话"，不写结构，锚点必须引用现成的 id：

```json
{
  "fields": {
    "main_findings": {"value": "…", "anchor_id": "a-s6-3", "status": "reported"}
  },
  "sections": {
    "S4": {"method": {"text": "…", "anchor_id": "a-s4-4"}}
  },
  "knowledge_items": [
    {"term": "exact match", "definition": "…", "kind": "metric", "anchor_id": "a-s5-3"}
  ],
  "result": {"notes_markdown": "notes.md", "paper_card": "paper_card.json",
             "evidence_table": "evidence.csv", "anchors": "anchors.json"}
}
```

填错会被当场拒绝，而不是混进产物：

```bash
$ python scripts/build_notes.py … --fill bad_fill.json
{"ok": false, "code": "fill_anchor_invalid", "detail": ["fields.main_findings:a-s9-99"]}
# exit 4
```

## 5. 这个示例证明了什么、没证明什么

**证明了**：章节切分与论文自身标题一致、每条笔记可回链到页、伪造锚点与伪造引文都会被拦、契约字段缺失会被报出来。

**没证明**：真实论文（尤其双栏、扫描件、超长文）上的稳健性；也没做"加载 Skill vs 不加载"的对照实验。这两项属于平台固定案例的评测范围，示例不冒充那部分结果。
