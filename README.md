# 玻尔产品周赛 · 北化分站赛第一期 参赛作品

本仓库收录「玻尔产品周赛·北化分站赛第一期」（2026-11-23 至 2026-11-29）的参赛 Skill 作品。每个目录是一份可独立加载的 Agent Skill，包含入口说明、字段规范、示例与校验脚本。

| 目录 | 对应赛题 | 作品定位 |
|-|-|-|
| [`reading10-evidence-anchored-notes/`](reading10-evidence-anchored-notes/) | 阅读10｜文献总结与结构化笔记 | **最终提交版。** 版面分块抽取 + 章节对齐 + 锚点白名单校验 + 证据表，附一键自测（含两处故意注入的伪造验证） |
| [`reading10-structured-notes/`](reading10-structured-notes/) | 阅读10｜文献总结与结构化笔记 | 早期提示驱动版，保留作为对照 |
| [`writing09-method-experiment/`](writing09-method-experiment/) | 写作09｜方法与实验章节写作 | 方法与实验章节的写作清单与结构校验，区分"可复现要素"与"必须人工确认项" |
| [`reading14-nanopublication/`](reading14-nanopublication/) | 阅读14｜Nanopublication | 把论文结论拆成可复用断言（assertion），附关系词表与 JSON-LD 示例 |

## 使用方式

每个目录都是完整的 Skill 单元，把目录整体放到 Agent 的 skills 路径下即可被识别（入口为各自目录内的 `SKILL.md`，含 `name` / `description` YAML frontmatter）。

```bash
# 以阅读10 加强版为例
cp -r reading10-evidence-anchored-notes/ ~/.claude/skills/
```

各 Skill 的脚本用于结构抽取与自检，只依赖 Python 标准库（`pymupdf` 可选，缺失时降级并如实报告）：

```bash
python reading10-evidence-anchored-notes/scripts/pdf_to_pages.py --input paper.pdf --out work/pages.json
python reading10-evidence-anchored-notes/scripts/build_notes.py --pages work/pages.json --out app/output --case-json case.json
python reading10-evidence-anchored-notes/scripts/validate_notes.py --dir app/output --pages work/pages.json --strict
python writing09-method-experiment/scripts/validate_materials.py materials.json
python reading14-nanopublication/scripts/validate_nanopub.py assertions.json
```

阅读10 加强版还带一条命令的端到端自测：

```bash
python reading10-evidence-anchored-notes/selftest/run_selftest.py
# 本机实测: 8/8 checks behaved as expected
```

自测会故意注入一个虚构锚点和一个伪造引文，确认两项校验都真的报错，而不是只在文档里声称会报错。

## 边界与已知限制

- 阅读10 加强版里，结构、锚点与证据表由脚本确定性产出；模型只写短语义字段，且必须引用已存在的 `anchor_id`，填不存在的锚点会被当场拒绝（exit 4）。
- 对扫描版、双栏错序、公式与图表仅存为图像的 PDF，只做识别与标注（`uncertainty` 里写明），不做版面复原；图像内容不会被当作已读取。
- 示例与自测中的论文数据为合成示例，用于说明接口与输出格式，**不是正式案例结果**，也不对应任何真实研究。
- 三份提示驱动型作品（`reading10-structured-notes`、`writing09-*`、`reading14-*`）由 `SKILL.md` 约束流程与输出契约，脚本只做结构校验，不替代抽取本身。

## 许可

内容以 MIT 许可发布，可自由复用与改写；示例数据不涉及任何受版权保护的原文。
