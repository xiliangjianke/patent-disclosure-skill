# 专利解读 Obsidian 笔记格式

## 目录与命名

- 库内默认：`Research/Patents/<领域>/<公开号>/<公开号>_解读_<YYYYMMDD>.md`
- 同目录：`images/`（附图）、`<公开号>_图谱.canvas`（专利族图谱）
- 库级：`Research/Patents/patents.base`（Bases 仪表盘）、`.obsidian/snippets/patent-reader.css`
- 领域路由：见 `references/patent_domain_rules.yaml`

## YAML Frontmatter

```yaml
---
tags:
  - patents/化工与材料
  - patent/evidence/full
  - patent/speculative
aliases:
  - CN107785522B
cssclasses:
  - patent-reader
pub_number: CN107785522B
domain: 化工与材料
ipc: H01M10/0525
assignees:
  - 某某科技有限公司
read_date: 2026-07-21
perspective: 入门
evidence_scope: full_text
confidence_speculative: false
---
```

- `evidence_scope`：`full_text` | `abstract_only` | `partial`
- `confidence_speculative`：附录 B 含中/低置信公开线索时为 `true`
- 标签：`patent/evidence/full|abstract|partial`；有推测时加 `patent/speculative`

## 著录项卡片（L0）

```markdown
> [!patent-meta] 著录项
> - **公开号**：CN…
> - **领域**：…
> - **IPC**：…
```

CSS 片段 `patent-reader` 由解读**入库时自动**复制并启用。

## 权利要求树

推荐结构（`render_claim_tree_markdown` / 入库自动写入）——**只保留一份信息**：

| 结构 | 权 | 本项新增 |
| --- | ---: | --- |
| `◆` | 1 | … |
| `├─` | 2 | … |
| `└─` | 3 | … |

- `◆` = 独立权；`├─`/`└─`/`│` = 从属层级  
- 独立权细节只在**第四节**展开  
- mermaid 默认不进正文（可生成 `claim_mermaid.mmd` 备用）
- Canvas「权项」卡与第三节同构（树形表，短句）；入库时旁路保存 `claim_tree.json`

## 第四节 Callout

```markdown
> [!patent-claim] 权利要求 1
> 【CN…·权利要求1】…
```

## 用户可见标题（硬性）

章节标题、小节标题、callout 标题**只用简洁名称**，禁止加给 Agent 的说明性括号，例如不要写：

- ~~`## 七、和现有技术的差别（若能从原文读出）`~~ → `## 七、和现有技术的差别`
- ~~`## 二、连贯叙事（故事线）`~~ → `## 二、连贯叙事`
- ~~`## 九、技术应用场景（专利内依据）`~~ → `## 九、技术应用场景`

写作要求写在 prompt / 模板正文的「写作提示」里，**不要**写进交付笔记标题。入库脚本 `sanitize_user_facing_titles` 会幂等清理常见旧标题。

## 第九节：应用场景

整节置于：

```markdown
> [!grounding] 应用场景
> …
```

**禁止 URL**。

## 第十节 B：推测线索

`validate_public_clues.py` 按置信度排序后**默认最多保留 3 条**。

**摘要主路径**：Agent 按 `patent_plain_reader.md` 第 2 步自主规划打开 URL，写入 `summary` / `status=agent_fetched` 等字段。  
**脚本降级**：仅 `--fetch-clues-fallback` / `--fetch-fallback`，且只处理缺 `summary` 的条目。

入库/materialize 负责结构化落地与 **L1–L4 融合**：

| 层 | 位置 |
| --- | --- |
| L1 | 导航「公开线索（N 条）」+ 文首 tip 入口 |
| L2 | 一/二/七/八/九 + 术语：折叠「公开案例/对照」旁注 |
| L3 | 第四节按权旁注；**第六节对照表正下方**挂「特征—公开语境」，条目必须对应笔记内特征行（F+名称或本表特征名；禁止空号 F1–F6） |
| L4 | 附录 B + `clues/` + Canvas「公开线索」分组 |

```markdown
> [!warning]- 公开检索线索
> 详情见 [[clues/_线索索引|线索文件夹]]
> - **线索**：[[clues/01-…|…]] — 置信度：中 — [来源](URL) — 理由：…
```

## 附图（P1/P2）

`extract_patent_figures.py`（caption+bbox，参考 DeepPaperNote 视觉引擎）：

- `decision=insert` + 质量 usable → 笔记嵌入 `![[images/…]]`
- 扫描件（无可靠图注）：入库启用**扫描件整页预览**（`--scan-pages` 或无 insert 时自动），第六节追加：

```markdown
### 附图

> [!tip] 扫描 PDF
> 官方文本多为扫描件，下列为整页渲染预览（非矢量裁切图）。

![[images/page_001_xref_01.png]]
*第 1 页*
```

- 仅当确无页面 PNG 时保留 `[!figure]` 占位，避免长期只显示 `insert=0`。

## 术语网（P0）

- 目录：`Research/术语/`（`PATENT_READER_GLOSSARY_DIR`）
- 入库自动建 stub、Canvas **file** 节点、第五节 wikilink
- stub 正文优先写入第五节「本文含义」一句，避免长期停留在「（待补充…）」空壳
- 索引：`Research/术语/_术语索引.md`

## Canvas（L2）

- 路径：`<公开号>_图谱.canvas`（导航须带 `.canvas` 后缀，避免点出空 `.md`）
- 由 `build_patent_canvas.py` / 入库脚本生成，建议包含：
  - **叙事分组**（问题 / 思路 / 怎么做 / 效果 / 差别）— 从笔记一、二、七节收获
  - **精简中心卡**（公开号 + 一句话 + 链到笔记，避免属性墙）
  - 著录 / 权项摘要；**术语 text 卡**（本文含义一句 + 术语页链接）
  - 关联专利精简卡；扫描附图默认不挂画布
  - hex 配色 + group 分区（叙事 / 术语 / 关联）
- **交付后常问（推荐）**：库内 ≥2 篇时反问；用户同意后 `link_patent_notes.py` 刷新单篇边标签，并生成库级 `Research/Patents/_专利关联.canvas`（富文本专利卡 + 关联桥卡写明依据，非裸 file 预览）

## 相关专利（交付后常问 · link_patent_notes）

Frontmatter：

```yaml
related_pubs:
  - CN107785522B
```

笔记中追加节 `## 相关专利`（表格 + wikilink）。规则边：同申请人 / IPC / 共术语 / 正文互引；可用 `--model-scores` 合并模型判定。主流程不自动写入；交付后**须反问**，同意再跑。

## 索引与仪表盘（L1）

- `_专利解读索引.md` 嵌入 `![[Research/Patents/patents.base#全部专利解读]]`
- Bases / Dataview 证据列显示中文（`evidence_label`：全文 / 仅摘要 / 部分）；含推测列用 `speculative_label`（是 / 否）
- Dataview 回退见索引模板

## 交付后插件引导

见 `prompts/obsidian_plugin_guide.md`、`references/obsidian_recommended_plugins.md`。
