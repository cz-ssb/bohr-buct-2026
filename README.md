# 玻尔产品周赛 · 北化分站赛第一期 参赛作品

本仓库收录「玻尔产品周赛·北化分站赛第一期」（2026-11-23 至 2026-11-29）的三份 Skill 作品。每个目录是一份可独立加载的 Agent Skill，包含入口说明、字段规范、示例与校验脚本。

| 目录 | 对应赛题 | 作品定位 |
|-|-|-|
| [`reading10-structured-notes/`](reading10-structured-notes/) | 阅读10｜文献总结与结构化笔记 | 章节对齐 + 锚点回链的结构化笔记，产出 Markdown、JSON 与字段字典三件套 |
| [`writing09-method-experiment/`](writing09-method-experiment/) | 写作09｜方法与实验章节写作 | 方法与实验章节的写作清单与结构校验，区分"可复现要素"与"必须人工确认项" |
| [`reading14-nanopublication/`](reading14-nanopublication/) | 阅读14｜Nanopublication | 把论文结论拆成可复用断言（assertion），附关系词表与 JSON-LD 示例 |

## 使用方式

每个目录都是完整的 Skill 单元，把目录整体放到 Agent 的 skills 路径下即可被识别（入口为各自目录内的 `SKILL.md`，含 `name` / `description` YAML frontmatter）。

```bash
# 以 reading10 为例
cp -r reading10-structured-notes/ ~/.claude/skills/
```

调用后按各 `SKILL.md` 的 Workflow 输入论文或稿件，脚本用于结构自检：

```bash
python reading10-structured-notes/scripts/validate_notes.py notes.json
python writing09-method-experiment/scripts/validate_materials.py materials.json
python reading14-nanopublication/scripts/validate_nanopub.py assertions.json
```

三个脚本只依赖 Python 标准库，不需要额外安装。

## 边界与已知限制

- 三份作品都是**提示驱动型** Skill：由 `SKILL.md` 约束工作流程与输出契约，脚本只做结构与字段校验，不替代抽取本身。
- `reading10` 对扫描版、双栏错序、公式缺失的 PDF 只给出"抽取条件"标注与不确定性说明，不做版面复原；锚点粒度取决于源文件是否带页码/章节标记。
- 示例文件中的论文数据为合成示例，用于说明接口与输出格式，**不是正式案例结果**。
- `reading14` 的断言以人工确认为准的部分在 `SKILL.md` 中单独标出，机器判定边界写在字段说明里。

## 许可

内容以 MIT 许可发布，可自由复用与改写；示例数据不涉及任何受版权保护的原文。
