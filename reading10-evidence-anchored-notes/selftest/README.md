# 自测说明 / Self-test

一条命令跑完整流程，并故意注入两处错误来证明检查真的会生效：

```bash
python selftest/run_selftest.py
```

需要 `pymupdf`（仅自测造 PDF 与抽取用；运行 skill 本身在没有 pdf 库时会退化并在 `sources.extractor` 里说明）。

## 覆盖的 8 项

| 检查 | 期望 |
|---|---|
| 生成 3 页合成论文 | exit 0 |
| 抽取页文本（带版面分块） | exit 0 |
| 建结构（章节 / 锚点 / 卡片） | exit 0 |
| 章节数 ≥ 5（防止整篇塌成一节） | 本机实测 9 |
| 合并语义填充 | exit 0 |
| 干净输入自检 | `ok: true`，无 violations |
| 注入虚构锚点 `a-s9-99` | exit 4，`fill_anchor_invalid` |
| 篡改引文为原文不存在句 | exit 1，`quote_not_on_page` |

本机实测输出：`8/8 checks behaved as expected`。

## 为什么要有"章节数 ≥ 5"这一项

早期版本按空行切段，真实 PDF 抽取出来相邻行之间只有单个换行，整页被当成一个块，结果整篇只识别出 1 个章节、3 个锚点——章节对齐这一评分维度会直接失分。改成读取版面分块后，同一份 3 页论文识别出 9 个章节、47 个锚点。这项检查就是为了防止该 bug 回归。

## 合成论文说明

`gen_test_paper.py` 生成的是虚构论文（*Sparse Attention Budgets and Retrieval Accuracy*），其中的数字与结论都是为测试编写的，不对应任何真实研究，也不得作为任何结论的依据。
