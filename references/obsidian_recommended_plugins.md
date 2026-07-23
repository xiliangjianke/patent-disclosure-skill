# 推荐 Obsidian 社区插件（专利解读增强）

阅读模式交付后，可向用户出示本清单。均为**可选**；未安装时笔记仍为合法 Obsidian Markdown。

**Windows 安装 Obsidian + 社区插件市场步骤**见 [`docs/obsidian-setup-guide.md`](../docs/obsidian-setup-guide.md)。  
CSS / Bases / 关系图配色由**解读入库自动完成**，勿再引导用户手动装 CSS 或跑初始化脚本。

## 必看：关系图自动上色（无需插件）

入库时会写入 `.obsidian/graph.json` 的 **Groups**：

| 颜色 | 节点类型 |
|------|----------|
| 靛色 | 专利解读笔记 |
| 青绿 | `*_图谱.canvas` / `_专利关联.canvas` |
| 橙色 | 术语页（`Research/术语`） |
| 石板灰 | 索引页 |
| 琥珀 | 含推测线索的解读 |

打开 **关系图** 后若仍全灰：确认已入库过，然后 **Ctrl/Cmd+R** 重载。

## 社区插件

| 插件 | 作用 | 安装页 | 吸引力 |
|------|------|--------|--------|
| **Dataview** | 索引页动态表回退 | https://obsidian.md/plugins?id=dataview | 表格 |
| **Colored Tags** | `#patents/…` `#glossary` 标签上色 | https://obsidian.md/plugins?id=colored-tags | 笔记内彩色标签 |
| **Colored Bases Properties** | Bases 表格属性 pill 上色 | https://obsidian.md/plugins?id=colored-bases-properties | 仪表盘 pill |
| **Iconize** | 文件夹/文件图标（如 Patents、术语） | https://obsidian.md/plugins?id=iconize | 侧栏辨识度 |
| **Supercharged Links** | 按属性/标签给双链上色 | https://obsidian.md/plugins?id=supercharged-links | 正文链接彩色 |

> Bases 为核心插件，入库时自动开启。关系图颜色靠原生 Groups；Colored Tags 美化正文标签，二者互补。

## 安装步骤（对话交付话术）

1. Obsidian → **设置** → **社区插件** → 关闭「限制模式」
2. **浏览** → 搜索上表插件名 → **安装** → **启用**
3. **Ctrl/Cmd+R** 重载 → 打开关系图与 `Research/Patents/_专利解读索引.md` 验收
4. （可选）安装 [Obsidian CLI](https://help.obsidian.md/cli) 后，入库脚本可自动 `property:set`

## GitHub 参考

- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — OFM / Bases 写法
- [GalaxyRuler/obsidian-writing-skill](https://github.com/GalaxyRuler/obsidian-writing-skill) — Dataview / Canvas
