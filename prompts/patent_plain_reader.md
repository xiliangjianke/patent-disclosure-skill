# 专利通俗解读（阅读模式）

## 适用时机

用户意图为**读懂已有专利**（反向阅读），而非撰写交底书。典型触发：

- 专利通俗解读、读专利、看懂专利、反向专利
- 提供专利号 / 专利 PDF / 粘贴权利要求或说明书
- `/patent-read`、`/读专利`

**与主流程关系**：本模式**不**执行 intake → 交底书 Step 1–8。

## 是否依赖 Obsidian？

**强烈推荐配置 Obsidian 库**（`PATENT_READER_OBSIDIAN_VAULT`），才能完整体验索引、Canvas 知识图谱、术语网、关系图配色与公开线索旁注。  
无库时仍可写入 `outputs/patent_reader/`（降级），解读主链路照常，但图谱与旁注体验会弱一截。  
因此**对话一开始、取证之前**必须先探测环境；用户安装与可选社区插件见 **`docs/obsidian-setup-guide.md`**。

## 第 0 步（门禁）：探测 Obsidian 与库路径

**在向用户确认主题之外的实质步骤之前**，先运行：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/check_obsidian_env.py --json
```

| 结果 | Agent 行为 |
|------|------------|
| `status=ready` 且有 `resolved.vault` | 可 `--auto-accept` 写入持久化；本会话设置 `PATENT_READER_OBSIDIAN_VAULT` 后继续 |
| `needs_user_input=true`（未装 / 多库 / 无库） | **暂停取证**，**强烈建议**用户给出库根路径以获得完整体验（常见：`C:\Users\<用户>\Documents\Obsidian Vault`）；仅当用户明确只要 Markdown / 不要库时，才降级 `outputs/` |
| 用户提供路径后 | 执行 `--set "路径"`（Windows 可选再加 `--setx`），并在后续 Shell 中带上该环境变量 |

```bash
# 用户给出路径后
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/check_obsidian_env.py --set "库路径" --setx

# Windows 当前会话（Agent 后续命令需带上）
# PowerShell: $env:PATENT_READER_OBSIDIAN_VAULT = "库路径"
```

持久化文件：`~/.patent-disclosure-skill/obsidian_vault.txt`（脚本自动读，不单靠环境变量）。

用户明确说「只要 Markdown / 不要 Obsidian」→ 跳过入库增强，写入 `outputs/` 即可。

## Obsidian 增强（L0–L2）

写笔记前 **`Read`**：

- `prompts/obsidian_ofm_companion.md` — Callout / frontmatter / Mermaid 规范
- `references/patent_obsidian_format.md` + `assets/patent_note_template.md`

**标题纪律**：交付笔记的 `##` / `###` / callout 标题只用简洁名称（如「二、连贯叙事」「七、和现有技术的差别」），**禁止**加「（故事线）」「（若能从原文读出）」「（专利内依据）」等给 Agent 的说明。模板里「写作提示 · 勿写入交付稿」仅供撰写时参考，不得原样留在正文。

**实现痕迹禁令（硬性）**：交付笔记与库内索引**禁止**出现脚本/工具文件名（如 `*.py`）、流水线字段路径（如 `context_anchor.ipc_application`）、内部裁图文件名（如 `page_001_xref_01.png`）。附录「来源」只写「离线 IPC 行业词表」等自然语言；附图说明只写「第 N 页」。

有库时，`write_patent_obsidian_note.py` 入库会**自动** `bootstrap_vault`（CSS / Bases / 关系图 Groups）。**勿**再引导用户手动复制 CSS 或单独为「配库」跑初始化；交付对话只引导可选社区插件（见 `obsidian_plugin_guide.md`）。
## 工作流（严格按序）

生成运行 ID：`read-<公开号或slug>-<YYYYMMDDHHmm>`（**RUN**）。

### 第 1 步：取证与结构化

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/extract_patent_text.py \
  -i <全文> -o tmp/patent_reader/${RUN} --pub-number <若有>
```

**PDF 附图（有 PDF 时执行；caption+bbox + 质量门）**：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/extract_patent_figures.py \
  -i <patent.pdf> -o tmp/patent_reader/${RUN}/figures
# 人工确认后少丢可用图：追加 --include-review
```

- 读 `FIGURES_MANIFEST`：`decision=insert` 可嵌入；`placeholder` 仅用 `[!figure]` 占位。
- `quality=review` 默认 placeholder；加 `--include-review`（抽取或入库）可按 insert 处理。
- 写笔记第六节：`insert` → `![[images/…]]`；其余 → `[!figure]`。

### 第 1.5 步：技术落地线索 + 可视化草稿

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_context_anchor.py -w tmp/patent_reader/${RUN}

python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_claim_mermaid.py \
  --claim-tree tmp/patent_reader/${RUN}/claim_tree.json \
  --pub-number <公开号> \
  -o tmp/patent_reader/${RUN}/claim_mermaid.mmd
```

- 第三节优先交给入库脚本生成**单一树形表**（结构 | 权 | 本项新增）。勿再「mermaid + 表」双份主展示；`claim_mermaid.mmd` 仅作可选附件。

### 第 2 步：公开检索 → 充实 `public_clues.json`（Agent 主路径）

对 `context_anchor.json` → `web_search_queries` 执行 **WebSearch**（或国知局脚本）得到候选后：

1. **先**跑校验+筛选（置信度高→低，**默认最多 3 条**）：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/validate_public_clues.py \
  -i tmp/patent_reader/${RUN}/public_clues.json \
  -o tmp/patent_reader/${RUN}/public_clues.lint.json \
  --write-filtered
```

2. **再由你（Agent）自主规划**打开每条 URL 并写回同文件（**主路径，勿依赖入库脚本爬虫**）：
   - 按站点选型：静态页可用 WebFetch / `mcp_web_fetch`；强反爬或 SPA 用浏览器类工具；打不开则标失败，勿编造正文。
   - 每条补全字段（可复现、可入库）：

```json
[
  {
    "title": "……",
    "url": "https://…",
    "confidence": "中",
    "reason": "与权利要求/实施例的对应关系…",
    "page_title": "页面标题（若可得）",
    "summary": "200～800 字可读摘要，只写页面上能核验的内容",
    "status": "agent_fetched",
    "related_claims": [1, 6],
    "related_features": ["水性PVDF"],
    "fetch_note": "选用的读取方式；失败原因（可选）"
  }
]
```

- `status`：`agent_fetched`（已读）/ `fetch_failed`（打不开）/ `draft`（仅有链接）。
- `related_claims` / `related_features`：弱匹配建议，**标注为推测**，不得写成说明书证据。
- **`summary` 写法（硬性）**：写成 3～8 条要点或两三句连贯短文；**禁止**粘贴导航/页脚/面包屑/整页纯文本；化学式写在同一行（如 `Al2O3/勃姆石涂覆`，勿拆成多行单字）。不要用行首 `>`（会在 Obsidian 变成引用竖线）。
- 无可靠结果时写 `[]`，附录 B「未发现…」。
- **禁止**把推测线索写进一至八主结论。

入库脚本只做**结构化落地与 L1–L4 融合**（`clues/`、导航入口、各节折叠旁注、权/特征点对点、附录 B、Canvas）。脚本 HTTP 抓取仅为**降级**：仅当某条缺少 `summary` 且显式传入 `--fetch-clues-fallback` 时才尝试。

### 第 3 步：`note_plan.json`

含 `context_anchor_ref`、`public_clues_ref`、`grounding`。

### 第 4 步：写解读笔记

遵循 **L0 Callout 模板**（`[!patent-meta]`、`[!grounding]`、`[!warning]-`）。

若有 `figures/manifest.json`：
- `decision=insert` → 第六节 `![[images/…]]`（入库脚本也会自动补嵌）
- `decision=placeholder` → `[!figure]` 占位，**不要**当正式插图

术语：第五节优先 `[[Research/术语/术语名|术语]]`。入库脚本会合并 `glossary_candidates` **与笔记第五节表/已有 wikilink** 再建 stub、反链与 Canvas（避免 extract 抽不到术语时术语网空白）。

### 第 5 步：lint

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/lint_patent_note.py \
  --note <笔记.md> \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  --claim-tree tmp/patent_reader/${RUN}/claim_tree.json \
  --plan tmp/patent_reader/${RUN}/note_plan.json \
  --context-anchor tmp/patent_reader/${RUN}/context_anchor.json \
  --figures-manifest tmp/patent_reader/${RUN}/figures/manifest.json \
  --output tmp/patent_reader/${RUN}/lint.json
```

- `section3_missing_mermaid_optional`、`insert_figure_not_referenced:*` 为 **warnings**（不阻断）；issues 须修到 passed。
- 有 ≥2 条独立权时第三节应补 mermaid。

### 第 6 步：写入 Obsidian

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/write_patent_obsidian_note.py \
  --content-file <笔记.md> \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  --context-anchor tmp/patent_reader/${RUN}/context_anchor.json \
  --bundle tmp/patent_reader/${RUN}/synthesis_bundle.json \
  --public-clues tmp/patent_reader/${RUN}/public_clues.json \
  --workdir tmp/patent_reader/${RUN} \
  --lint-json tmp/patent_reader/${RUN}/lint.json \
  --output tmp/patent_reader/${RUN}/write_status.json
# 可选：--include-review（入库时把 review 图当 insert）
# 可选：--strict-figures（要求笔记已嵌入，禁止只靠自动补嵌）
```

自动：`bootstrap_vault`（CSS / Bases / 关系图）、frontmatter 标签、`*.canvas` 图谱（叙事/著录/权项/术语/相关专利/**公开线索卡**）、`clues/` 落地（用第 2 步 Agent 已写的 summary）、扫描件整页预览、术语反链。线索脚本抓取默认关闭，仅 `--fetch-clues-fallback`。无 vault 时仍写 `outputs/`。入库可加 `--scan-pages`。

可选单独生成 Canvas：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/build_patent_canvas.py \
  --note-rel Research/Patents/<领域>/<公开号>/<文件>.md \
  --manifest tmp/patent_reader/${RUN}/source_manifest.json \
  -o Research/Patents/<领域>/<公开号>/<公开号>_图谱.canvas
```

### 第 7 步：交付

1. 笔记路径、Canvas 路径、索引页路径  
2. 一句话结论、证据范围、应用场景要点  
3. **`Read`** `prompts/obsidian_plugin_guide.md` → 向用户出示**插件安装引导**（含社区插件 URL）

### 第 8 步（交付后常问 · 推荐）：库内专利关联

交付第 7 步后，**只要库内已有 ≥2 篇解读笔记，就必须用一句话反问**（勿静默跳过）：

> 库里已有其它专利解读，要不要做一次「专利关联」？会按同申请人 / IPC / 共术语等规则连边，并生成全局 `Research/Patents/_专利关联.canvas`（不构成法律意见）。

| 用户态度 | Agent 行为 |
|----------|------------|
| 明确同意 / 「要关联」 / 「好」 | 执行下方命令；可先 `--dry-run` 预览边再写入 |
| 拒绝 / 「不用」 | **跳过**，结束本轮 |
| 「先看看有哪些边」 | 仅 `--dry-run`，再问是否写入 |
| 库内不足 2 篇 | 可省略反问，或说明「再解读一篇后可做关联」 |

```bash
# 预览
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> --dry-run \
  -o tmp/patent_reader/${RUN}/patent_links.preview.json

# 写入（双向回写 related_pubs + 相关专利节 + 单篇图谱 + 全局 _专利关联.canvas）
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> \
  -o tmp/patent_reader/${RUN}/patent_links.json
```

**可选增强（模型边）**：若 dry-run 后仍有「疑似相关但规则分不够」的对，Agent 可阅读两篇笔记后写 `model_links.json`：

```json
[
  {
    "pub_a": "CNxxx",
    "pub_b": "CNyyy",
    "relation": "improvement",
    "score": 0.75,
    "rationale": "独立权均含…；B 增加…"
  }
]
```

再执行：

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/patent_reader/link_patent_notes.py \
  --focus-pub <本轮公开号> \
  --model-scores tmp/patent_reader/${RUN}/model_links.json \
  -o tmp/patent_reader/${RUN}/patent_links.json
```

**约束**：无 vault 时跳过本步；关联仅为辅助导航，须在相关专利节保留免责提示；**禁止**把关联写成侵权/无效结论。

## 与国知局查新的一致性

公开号、摘要须先检索核验；**禁止虚构**链接。
