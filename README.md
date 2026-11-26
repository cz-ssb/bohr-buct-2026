# 玻尔产品周赛 · 北化分站赛第一期 参赛作品

本仓库收录「玻尔产品周赛·北化分站赛第一期」（2026-11-23 至 2026-11-29）的参赛 Skill 作品。每个目录是一份可独立加载的 Agent Skill，包含入口说明、字段规范、示例与校验脚本。

| 目录 | 对应赛题 | 作品定位 |
|-|-|-|
| [`reading10-evidence-anchored-notes/`](reading10-evidence-anchored-notes/) | 阅读10｜文献总结与结构化笔记 | **最终提交版。** 版面分块抽取 + 章节对齐 + 锚点白名单校验 + 证据表，附一键自测（8 项，含故意注入的伪造锚点与伪造引文） |
| [`writing09-evidence-methods/`](writing09-evidence-methods/) | 写作09｜方法与实验章节写作 | **最终提交版。** 从配置、日志、代码抽取带 `path#line` 地址的参数表，渲染八节章节，正文数值与参数表双向对齐，冲突只上报不静默择一；附一键自测（16 项，含 4 类注入故障） |
| [`reading14-atomic-assertions/`](reading14-atomic-assertions/) | 阅读14｜Nanopublication | **最终提交版。** 论文→带页码的句子→原子断言候选→最小逐字证据→`assertions.json` + JSON-LD；断言改写、引文篡改、关系越界、重复记录四类故障均被拦下；附一键自测（20 项） |
| [`reading10-structured-notes/`](reading10-structured-notes/) | 阅读10｜文献总结与结构化笔记 | 早期提示驱动版，保留作为对照 |
| [`writing09-method-experiment/`](writing09-method-experiment/) | 写作09｜方法与实验章节写作 | 早期提示驱动版，保留作为对照 |
| [`reading14-nanopublication/`](reading14-nanopublication/) | 阅读14｜Nanopublication | 早期提示驱动版，保留作为对照 |

## 使用方式

每个目录都是完整的 Skill 单元，把目录整体放到 Agent 的 skills 路径下即可被识别（入口为各自目录内的 `SKILL.md`，含 `name` / `description` YAML frontmatter）。

```bash
# 以阅读14 加强版为例
cp -r reading14-atomic-assertions/ ~/.claude/skills/
```

三份加强版各自带一条命令的端到端自测，脚本只依赖 Python 标准库（PDF 抽取器 `pymupdf` / `pdfplumber` / `pypdf` / `pdftotext` 可选，全部缺失时如实报告 `no_pdf_extractor`）：

```bash
# 阅读10：8/8
python reading10-evidence-anchored-notes/selftest/run_selftest.py

# 写作09：16/16
python writing09-evidence-methods/selftest/run_selftest.py

# 阅读14：20/20
python reading14-atomic-assertions/selftest/run_selftest.py
```

自测不只会跑通主干，还会故意注入故障并确认校验真的报错：阅读10 注入虚构锚点与伪造引文；写作09 注入不存在的参数引用、无来源数字、指向空文件的地址、非法 gap 类型；阅读14 注入改写后的断言、越界关系、改动一个字符的引文、重复记录。自测产物写在系统临时目录，不会进入 Skill 资源包。

## 三份加强版的共同设计

同一套取舍贯穿三份作品，这也是它们与提示驱动版的区别：

- **确定性优先。** 结构、页码、地址、证据表由脚本产出；模型只写短语义字段，且必须引用已存在的 id（`anchor_id` / `param_id` / `cid`），引用不存在的 id 一律 exit 4 当场拒绝。
- **冲突与缺口只上报，不消解。** 参数表里 `status: conflict` 同时留两个来源，章节里变成给作者的问题；断言导出里未标注的候选留在 `gaps.json`，不会悄悄消失。
- **`not_reported` 是一等答案。** 缺项写成缺项，不是从典型默认值补一个数字。
- **失败必须说出来。** 扫描版无文本层、二进制材料、指向空文件的地址、越界关系词，全部落进 `uncertainty` 或 `sources.skipped`，不会伪装成已读。

## 边界与已知限制

- 分析对象限于材料里真实写下的内容：不做版面复原，不替作者补实验条件，不从图注反推图中数值。
- 写作09 的参数词表覆盖约 30 个常见训练/评测参数名；遇到 Hydra composition、argparse 分组这类方言需要扩展 `scripts/extract_params.py::SCHEMA`。
- 阅读14 的断言切分在同一句内完成，跨句合并的断言会被保留为整句而非硬拆，宁可宽一点也不要不可判断的碎片。
- 示例与自测中的论文、实验与数据全部为合成示例，用于说明接口与输出格式，**不是正式案例结果**，也不对应任何真实研究。

## 许可

内容以 MIT 许可发布，可自由复用与改写；示例数据不涉及任何受版权保护的原文。
