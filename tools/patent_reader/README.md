# 专利通俗解读工具（`tools/patent_reader/`）

阅读模式专用脚本，与交底书主流程工具（`mermaid_render.py`、`cnipa_*.py` 等）分离。

## 目录结构

| 文件 | 作用 |
|------|------|
| `common.py` | 领域路由、IPC 提示、路径与环境变量 |
| `obsidian.py` | Frontmatter、Canvas、库 bootstrap、Mermaid |
| `extract_patent_text.py` | 全文/PDF 取证 |
| `figure_extract.py` | 专利 caption+bbox 裁切 + 质量门（被 extract 调用） |
| `extract_patent_figures.py` | PDF 附图 CLI → manifest（insert/placeholder） |
| `build_context_anchor.py` | 技术落地线索包 |
| `build_claim_mermaid.py` | 权利要求 mermaid |
| `build_patent_canvas.py` | JSON Canvas 图谱（L2） |
| `lint_patent_note.py` | 笔记结构校验 |
| `validate_public_clues.py` | 附录 B 线索校验 + 置信度筛选（默认最多 3 条） |
| `clue_vault.py` | `clues/` 落地、附录/旁注/Canvas；脚本 HTTP 仅作降级 |
| `materialize_public_clues.py` | 对已有解读补跑线索落地；`--fetch-fallback` 才脚本抓取 |
| `check_obsidian_env.py` | 对话开始前探测库路径（**强烈推荐**有库；可降级 outputs） |
| `link_patent_notes.py` | 交付后常问：库内专利关联（规则+模型分）与全局 `_专利关联.canvas` |
| `write_patent_obsidian_note.py` | 入库 + 自动 bootstrap（CSS / Bases / 关系图） |
| `setup_obsidian_vault.py` | 与入库等价的库初始化（开发/排障用；用户流程勿单独强调） |
| `requirements.txt` | 可选依赖（`pymupdf`） |

库内模板：`assets/obsidian/`（CSS、Bases、索引页）。

流程见 **`prompts/patent_plain_reader.md`**。

## 快速开始

```bash
pip install -r tools/patent_reader/requirements.txt

# 先探测库路径（强烈推荐已装 Obsidian 并开库）
python tools/patent_reader/check_obsidian_env.py --auto-accept

python tools/patent_reader/extract_patent_text.py \
  -i tests/fixtures/patent_reader_sample.txt \
  -o tmp/patent_reader/demo --pub-number CN999999999B
```

入库用 `write_patent_obsidian_note.py`（内含 bootstrap）；勿再单独要求用户跑 `setup_obsidian_vault.py`。
## 环境变量

| 变量 | 说明 |
|------|------|
| `PATENT_READER_OBSIDIAN_VAULT` | Obsidian 库根（兼容 `PATENT_DISCLOSURE_OBSIDIAN_VAULT`）；也可用 `check_obsidian_env.py --set` 持久化到 `~/.patent-disclosure-skill/obsidian_vault.txt` |
| `PATENT_READER_PAPERS_DIR` | 库内目录，默认 `Research/Patents` |
| `PATENT_READER_OUTPUT_DIR` | 未配置库时输出目录 |

## L0–L2 能力对照

| 层级 | 实现 |
|------|------|
| L0 | Callout 模板、`patent-reader.css`、`build_claim_mermaid.py` |
| L1 | `patents.base`（证据/推测列中文）、索引页、`evidence_label` / `speculative_label` |
| L2 | Canvas（**叙事卡** + 著录/权项/术语/关联）+ 术语 stub（第五节含义回填）；附图闸门 + **扫描件整页预览**（`--scan-pages`） |

环境变量额外：`PATENT_READER_GLOSSARY_DIR`（默认 `Research/术语`）。

交付后插件引导：`prompts/obsidian_plugin_guide.md`。  
关系图配色说明：`references/obsidian_recommended_plugins.md`（原生 Groups，无需插件）。
