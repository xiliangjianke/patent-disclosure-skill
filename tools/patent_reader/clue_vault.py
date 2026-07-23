"""公开检索线索：筛选、抓取、clues/ 入库、附录 B、旁注与 Canvas 数据。"""
from __future__ import annotations

import json
import re
from datetime import date
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_MAX_CLUES = 3

CONF_RANK = {
    "高": 3,
    "high": 3,
    "中": 2,
    "medium": 2,
    "med": 2,
    "mid": 2,
    "低": 1,
    "low": 1,
}

APPENDIX_B_RE = re.compile(
    r"(###\s*B\.\s*公开检索线索[\s\S]*?)(?=^##\s+|\Z)",
    re.M,
)
SECTION4_RE = re.compile(
    r"(^##\s*四、独立权利要求精读[\s\S]*?)(?=^##\s*五、|\Z)",
    re.M,
)
SECTION6_RE = re.compile(
    r"(^##\s*六、[\s\S]*?)(?=^##\s*七、|\Z)",
    re.M,
)


def as_clues(raw) -> list[dict]:
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    if isinstance(raw, dict):
        clues = raw.get("clues") or raw.get("items") or []
        if isinstance(clues, list):
            return [c for c in clues if isinstance(c, dict)]
    return []


def _conf_rank(conf: str) -> int:
    s = (conf or "").strip()
    if not s:
        return 0
    if s in CONF_RANK:
        return CONF_RANK[s]
    return CONF_RANK.get(s.lower(), 0)


def normalize_clue(c: dict, *, index: int = 0) -> dict:
    title = (c.get("title") or c.get("name") or "").strip()
    url = (c.get("url") or c.get("link") or "").strip()
    conf = (c.get("confidence") or "").strip() or "中"
    reason = (
        c.get("reason") or c.get("rationale") or c.get("note") or ""
    ).strip()
    out = {
        **c,
        "title": title,
        "url": url,
        "confidence": conf,
        "reason": reason,
        "clue_id": c.get("clue_id") or f"clue-{index + 1:02d}",
    }
    return out


def filter_clues(
    clues: list[dict],
    *,
    max_keep: int = DEFAULT_MAX_CLUES,
) -> tuple[list[dict], list[dict]]:
    """按置信度高→低排序，默认最多保留 max_keep 条。"""
    if max_keep <= 0:
        return [], list(clues)
    ranked: list[tuple[int, int, dict]] = []
    for i, c in enumerate(clues):
        n = normalize_clue(c, index=i)
        ranked.append((_conf_rank(n["confidence"]), -i, n))
    ranked.sort(key=lambda t: (-t[0], -t[1]))
    kept = [t[2] for t in ranked[:max_keep]]
    dropped = [t[2] for t in ranked[max_keep:]]
    # 重编号 clue_id
    for i, c in enumerate(kept):
        c["clue_id"] = f"clue-{i + 1:02d}"
    return kept, dropped


def clue_filename(title: str, index: int) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", (title or "线索").strip())
    base = re.sub(r"-{2,}", "-", base).strip("-")[:36] or "线索"
    return f"{index + 1:02d}-{base}.md"


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# 企业站常见导航/页脚噪音（脚本降级抓取时常混入）
_NAV_NOISE = {
    "oa",
    "srm",
    "邮箱",
    "魔学院",
    "主页",
    "首页",
    "产品展示",
    "新闻中心",
    "企业动态",
    "集团要闻",
    "行业资讯",
    "通知公告",
    "友情链接",
    "联系方式",
    "分享到",
    "基膜",
    "涂覆",
    "copyright",
    "回到顶部",
    "新闻频道",
    "财经频道",
    "城市频道",
    "公司新闻",
    "名企名片",
    "招贤纳士",
    "锂电世界",
    "我爱电车网",
    "石墨烯",
    "燃料电池",
    "海融网",
    "abec",
    "放大",
    "缩小",
    "扫描到手机",
    "点击：",
    "来源：",
    "作者：",
}


def _is_formula_glyph_frag(s: str) -> bool:
    """仅 ASCII/数字/下标短片段视为化学式竖排拆字（勿吞中文导航词）。"""
    return bool(re.fullmatch(r"[A-Za-z0-9²³₀-₉]{1,2}", s))


def _join_broken_glyph_lines(lines: list[str]) -> list[str]:
    """把 Al / 2 / O / 3 这类竖排拆字拼回 Al2O3。"""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    for raw in lines:
        s = raw.strip()
        if not s:
            flush()
            continue
        if _is_formula_glyph_frag(s):
            buf.append(s)
            continue
        if buf:
            # 拆字后紧跟公式续接（如 /勃姆石涂覆）
            if s.startswith("/") or re.fullmatch(r"[A-Za-z0-9²³₀-₉/.\-]+", s):
                buf.append(s)
                flush()
                continue
            # 中文续接且缓冲已是化学式前缀
            joined = "".join(buf)
            if re.search(r"[A-Za-z]\d", joined) and len(s) <= 16:
                buf.append(s)
                flush()
                continue
            flush()
        out.append(s)
    flush()
    return out


def sanitize_clue_summary(
    text: str,
    *,
    title: str = "",
    reason: str = "",
    max_chars: int = 700,
) -> str:
    """清洗脚本/脏抓取摘要：去导航、拼拆字、去掉会触发引用块的 > 行，整理为可读短文。"""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""

    # 已是干净要点列表 / 短文：勿再拼成一行
    if re.search(r"(?m)^页面要点：\s*$", raw) and re.search(r"(?m)^-\s+\S", raw):
        out = format_summary_for_markdown(raw)
        if len(out) > max_chars:
            out = out[: max_chars - 1].rstrip() + "…"
        return out
    if (
        raw.count("\n") >= 2
        and not re.search(r"(?m)^>{1,}\s*$", raw)
        and not re.search(r"(?m)^(OA|SRM|主页|产品展示)\s*$", raw)
        and sum(1 for ln in raw.splitlines() if 0 < len(ln.strip()) <= 2) <= 2
    ):
        out = format_summary_for_markdown(raw)
        if len(out) > max_chars:
            out = out[: max_chars - 1].rstrip() + "…"
        return out

    lines = [ln.strip() for ln in raw.split("\n")]
    lines = _join_broken_glyph_lines(lines)

    bullets: list[str] = []
    body: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        i += 1
        if not ln:
            continue
        low = ln.lower()
        if low in _NAV_NOISE or ln in _NAV_NOISE:
            continue
        if re.match(r"^(copyright|苏icp|京icp|邮编\s*：|地址\s*：|邮箱\s*：)", ln, re.I):
            continue
        if re.search(r"@|\.com\b", ln) and len(ln) < 80:
            continue
        # 单独的 >> 行：下一非空行视为卖点
        if re.fullmatch(r">+", ln):
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                bit = lines[i].strip()
                i += 1
                bit = re.sub(r"^>+\s*", "", bit)
                if len(bit) >= 4 and bit not in _NAV_NOISE and bit.lower() not in _NAV_NOISE:
                    bullets.append(bit)
            continue
        # 同行面包屑 / 卖点：>> xxx
        m = re.match(r"^>{1,}\s*(.+)$", ln)
        if m:
            bit = m.group(1).strip()
            if bit and bit not in _NAV_NOISE and bit.lower() not in _NAV_NOISE:
                if len(bit) >= 4:
                    bullets.append(bit)
            continue
        # 重复标题噪音
        if title and ln.replace(" ", "") == title.replace(" ", ""):
            continue
        if "有限公司_有限公司" in ln or (ln.count("_") >= 2 and "公司" in ln):
            continue
        if len(ln) <= 1:
            continue
        # 菜单式短词（无句号、偏导航）
        if len(ln) <= 16 and not re.search(r"[。！？；,.!?]", ln) and (
            ln.endswith("隔膜") or ln in {"基膜", "涂覆"}
        ):
            continue
        body.append(ln)

    # 脏页特征：短行过多或卖点较多 → 优先要点列表
    short_ratio = 0.0
    if lines:
        short_ratio = sum(1 for x in lines if 0 < len(x.strip()) <= 2) / max(
            len(lines), 1
        )

    parts: list[str] = []
    prefer_bullets = bool(bullets) and (
        short_ratio > 0.08 or len(bullets) >= 3 or len(body) < 4
    )
    if prefer_bullets:
        parts.append("页面要点：")
        for b in list(dict.fromkeys(bullets))[:8]:
            parts.append(f"- {b}")
    else:
        # 正常正文：合并为段落；过长时截断
        para = re.sub(r"\s+", " ", " ".join(body)).strip()
        # 去掉残留面包屑符号
        para = re.sub(r"\s*>+\s*", " ", para)
        para = re.sub(r"\s{2,}", " ", para).strip()
        # 新闻站：从首个「实质句」切开（去掉频道栏粘连）
        m_lead = re.search(
            r"((?:\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日).{20,})",
            para,
        )
        if not m_lead:
            m_lead = re.search(
                r"((?:获悉|讯（|报道）|将携|掌握|展示).{30,})",
                para,
            )
        if m_lead and m_lead.start() > 12:
            para = m_lead.group(1).strip()
        para = re.sub(
            r"(点击：?\s*|扫描到手机\s*|放大\s*|缩小\s*|回到顶部\s*)",
            "",
            para,
        )
        para = re.sub(r"\s{2,}", " ", para).strip()
        if para:
            parts.append(para)
        elif bullets:
            parts.append("页面要点：")
            for b in list(dict.fromkeys(bullets))[:8]:
                parts.append(f"- {b}")

    out = "\n".join(parts).strip()
    if not out and reason:
        out = f"（页面正文未能干净抽取，仅保留检索理由）{reason[:160]}"
    if len(out) > max_chars:
        out = out[: max_chars - 1].rstrip() + "…"
    return out


def format_summary_for_markdown(summary: str) -> str:
    """写入笔记时避免以 > 开头的行被 Obsidian 当成引用块。"""
    lines_out: list[str] = []
    for ln in (summary or "").splitlines():
        if re.match(r"^\s*>+", ln):
            ln = re.sub(r"^\s*>+\s*", "", ln)
            if ln:
                lines_out.append(f"- {ln}")
            continue
        lines_out.append(ln)
    return "\n".join(lines_out).strip()


def fetch_url_summary(url: str, *, max_chars: int = 900, timeout: int = 18) -> dict:
    """自动抓取 URL 可读摘要；失败不抛错，返回 status=fetch_failed。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": "",
            "summary": "",
            "error": "invalid_url",
        }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
            final_url = resp.geturl()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": "",
            "summary": "",
            "error": str(e)[:160],
        }

    page_title = ""
    summary = ""
    # 优先 readability / bs4（若已安装）
    try:
        from readability import Document  # type: ignore

        doc = Document(html)
        page_title = (doc.short_title() or "").strip()
        summary = _strip_html(doc.summary())
    except Exception:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                page_title = soup.title.string.strip()
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            summary = soup.get_text("\n", strip=True)
        except Exception:
            mt = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
            page_title = unescape(mt.group(1)).strip() if mt else ""
            summary = _strip_html(html)

    summary = sanitize_clue_summary(
        summary, title=page_title, max_chars=max_chars
    )
    if not summary:
        return {
            "ok": False,
            "status": "fetch_failed",
            "page_title": page_title,
            "summary": "",
            "error": "empty_body",
            "final_url": final_url,
        }
    return {
        "ok": True,
        "status": "script_fetched",
        "page_title": page_title,
        "summary": summary,
        "final_url": final_url,
        "error": "",
    }


def _tokenize(text: str) -> set[str]:
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9\-]{2,}", text or "")
    stop = {
        "一种",
        "方法",
        "包括",
        "所述",
        "以及",
        "进行",
        "公开",
        "专利",
        "公司",
        "技术",
        "产品",
        "相关",
        "是否",
        "需要",
        "本申请",
        "本专利",
        "置信度",
        "来源",
        "理由",
    }
    return {p for p in parts if p not in stop and len(p) >= 2}


def _term_match_tokens(term: str) -> list[str]:
    """术语共现匹配：整词 + 连续汉字二元组（避免「陶瓷涂层」整词过严）。"""
    term = (term or "").strip()
    if not term:
        return []
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", term))
    tokens: list[str] = [term]
    if len(chars) >= 2:
        if chars != term:
            tokens.append(chars)
        tokens.extend(chars[i : i + 2] for i in range(len(chars) - 1))
    tokens.extend(re.findall(r"[A-Za-z0-9]{2,}", term))
    return list(dict.fromkeys(t for t in tokens if len(t) >= 2))


def harvest_feature_rows(content: str) -> list[str]:
    return [e["text"] for e in harvest_feature_entries(content)]


def harvest_feature_entries(content: str) -> list[dict]:
    """从第四节/第六节表收集特征行；优先识别 F1、F2… 编号。"""
    entries: list[dict] = []
    seen: set[str] = set()
    for sec_re in (SECTION4_RE, SECTION6_RE):
        m = sec_re.search(content or "")
        block = m.group(1) if m else ""
        for line in block.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or cells[0] in ("特征", "---") or re.match(r"^[-:]+$", cells[0]):
                continue
            head = cells[0]
            fm = re.match(r"^(F\d+)\s*(.*)$", head, re.I)
            fid = fm.group(1).upper() if fm else ""
            label = (fm.group(2).strip() if fm else head)[:40]
            text = " ".join(cells)
            key = fid or text[:48]
            if key in seen:
                continue
            seen.add(key)
            entries.append({"id": fid, "label": label or head, "text": text})
    return entries


# 特征名 ↔ 公开话术常见同义（用于弱匹配，勿当权要解释）
_FEATURE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "水性": ("水性", "水系", "水基"),
    "油性": ("油性", "油系", "油基"),
    "涂覆": ("涂覆", "涂布", "涂层"),
    "陶瓷": ("陶瓷", "无机涂覆", "勃姆石"),
    "球状": ("球状", "球形", "颗粒"),
    "基膜": ("基膜", "隔膜基材", "基材"),
}

_FEATURE_LABEL_STOP = {
    "对比",
    "相关",
    "性能",
    "具体",
    "实施",
    "方式",
    "问题",
    "参数",
    "叙述",
    "占位",
    "附图",
}


def feature_display_name(ent: dict) -> str:
    """旁注展示名：有 F 编号则「F1 标签」，否则用对照表特征名。"""
    fid = (ent.get("id") or "").strip()
    label = (ent.get("label") or "").strip()
    if fid and label:
        return f"{fid} {label}"
    return fid or label or "特征"


def resolve_feature_entry(key: str, catalog: list[dict]) -> dict | None:
    """把 related_feature_ids 中的 F1 / 特征名 解析到笔记内真实特征行。"""
    key = (key or "").strip()
    if not key or not catalog:
        return None
    ku = key.upper()
    for e in catalog:
        if e.get("id") and str(e["id"]).upper() == ku:
            return e
    for e in catalog:
        lab = (e.get("label") or "").strip()
        if lab == key or key == feature_display_name(e):
            return e
    for e in catalog:
        lab = (e.get("label") or "").strip()
        if lab and (key in lab or lab in key):
            return e
    return None


def _label_hits_blob(label: str, blob: str) -> bool:
    """特征名与线索文本弱共现（含水系/水性等同义）。"""
    label = (label or "").strip()
    blob = blob or ""
    if not label or not blob:
        return False
    if label in blob:
        return True
    blob_l = blob.lower()
    for eng in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", label):
        if eng.lower() in blob_l:
            return True
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", label))
    for i in range(max(0, len(chars) - 1)):
        d = chars[i : i + 2]
        if d in _FEATURE_LABEL_STOP:
            continue
        alts = _FEATURE_SYNONYMS.get(d, (d,))
        if any(a in blob for a in alts):
            return True
    return False


def _clue_stem(clue: dict) -> str:
    return Path(clue.get("filename") or "x.md").stem


def _clue_link(clue: dict, title: str | None = None) -> str:
    stem = _clue_stem(clue)
    t = title or clue.get("title") or stem
    return f"[[clues/{stem}|{t}]]"


def _clue_highlight(clue: dict, *, limit: int = 72) -> str:
    """取摘要首条要点或理由短句，供旁注。"""
    summary = sanitize_clue_summary(
        clue.get("summary") or "",
        title=clue.get("title") or "",
        reason=clue.get("reason") or "",
    )
    for ln in summary.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            return s[2:].strip()[:limit]
        if s and s != "页面要点：":
            return s[:limit]
    reason = (clue.get("reason") or "").strip()
    return reason[:limit] if reason else (clue.get("title") or "公开线索")


def match_clue_to_note(
    clue: dict,
    *,
    claim_summaries: dict[int, str] | None = None,
    feature_rows: list[str] | None = None,
    feature_entries: list[dict] | None = None,
    extra_text: str = "",
) -> dict:
    """弱匹配：线索文本 ↔ 权项摘要 / 特征行（含 F1…）。"""
    blob = " ".join(
        [
            clue.get("title") or "",
            clue.get("reason") or "",
            clue.get("summary") or "",
            clue.get("page_title") or "",
            extra_text,
        ]
    )
    tokens = _tokenize(blob)
    related_claims: list[int] = []
    claim_hits: list[str] = []
    for num, summ in sorted((claim_summaries or {}).items()):
        ct = _tokenize(str(summ))
        overlap = sorted(tokens & ct)
        if len(overlap) >= 1 and (
            len(overlap) >= 2 or any(len(x) >= 4 for x in overlap)
        ):
            related_claims.append(int(num))
            claim_hits.append("、".join(overlap[:4]))

    entries = list(feature_entries or [])
    if not entries and feature_rows:
        entries = [{"id": "", "label": "", "text": r} for r in feature_rows]

    related_features: list[str] = []
    related_feature_ids: list[str] = []
    for ent in entries:
        ft = _tokenize(ent.get("text") or "")
        overlap = sorted(tokens & ft)
        label_hit = _label_hits_blob(ent.get("label") or "", blob)
        if (
            len(overlap) >= 2
            or (overlap and any(len(x) >= 4 for x in overlap))
            or label_hit
        ):
            related_features.append(
                "、".join(overlap[:4]) if overlap else (ent.get("label") or "")[:20]
            )
            if ent.get("id"):
                related_feature_ids.append(str(ent["id"]))
            elif ent.get("label"):
                related_feature_ids.append(str(ent["label"])[:40])
    # 启发式：仅当笔记里确有对应 F 编号时才补（避免空号 F1–F6）
    joined = " ".join(tokens)
    if any(k in joined for k in ("陶瓷", "涂覆", "勃姆石", "al2o3")):
        for prefer in ("F1", "F6"):
            if prefer not in related_feature_ids and any(
                e.get("id") == prefer for e in entries
            ):
                related_feature_ids.append(prefer)
    if any(k in joined for k in ("湿法", "拉伸", "基膜")):
        for prefer in ("F2", "F5"):
            if prefer not in related_feature_ids and any(
                e.get("id") == prefer for e in entries
            ):
                related_feature_ids.append(prefer)

    return {
        "related_claims": related_claims[:6],
        "related_features": related_features[:4],
        "related_feature_ids": list(dict.fromkeys(related_feature_ids))[:6],
        "claim_hit_terms": claim_hits[:6],
        "match_score": len(related_claims) + len(related_feature_ids or related_features),
    }


def _strip_injected_clue_blocks(content: str) -> str:
    """幂等：去掉先前 L1–L3 注入的线索旁注/入口。"""
    titles = (
        "公开线索入口",
        "公开线索",
        "公开案例（推测）",
        "外部线索（推测）",
        "权项—公开语境（推测）",
        "特征—公开语境（推测）",
        "阅读建议·公开线索",
        "差别对照·公开线索",
        "场景·公开线索",
        "术语·公开语境",
    )
    for title in titles:
        content = re.sub(
            rf"\n?>\s*\[!(?:warning|tip)\]-?\s*{re.escape(title)}[\s\S]*?"
            rf"(?=\n##\s|\n###\s|\n>\s*\[!|\Z)",
            "\n",
            content,
        )
    content = re.sub(
        r"^[ \t]*-\s*\[\[[^\]]*clues/_线索索引[^\]]*\]\][^\n]*\n?",
        "",
        content,
        flags=re.M,
    )
    return content


def _insert_before_heading(content: str, heading_pat: str, block: str) -> str:
    m = re.search(heading_pat, content, re.M)
    if not m:
        return content
    return content[: m.start()].rstrip() + "\n\n" + block.strip() + "\n\n" + content[m.start() :]


def _insert_after_section(content: str, section_re: re.Pattern[str], block: str) -> str:
    m = section_re.search(content)
    if not m:
        return content
    end = m.end()
    return content[:end].rstrip() + "\n\n" + block.strip() + "\n\n" + content[end:]


def _render_warning(title: str, body_lines: list[str]) -> str:
    lines = [f"> [!warning]- {title}", ">"]
    for ln in body_lines:
        lines.append(f"> {ln}" if ln else ">")
    return "\n".join(lines)


def _insert_after_section6_feature_table(content: str, block: str) -> str:
    """插在第六节对照表正下方（附图/扫描预览之前），避免沉到节末看不见。"""
    sec = re.search(
        r"(^##\s*六、[^\n]*\n)([\s\S]*?)(?=^##\s*七、|\Z)",
        content,
        re.M,
    )
    if not sec:
        if re.search(r"^##\s*七、", content, re.M):
            return _insert_before_heading(content, r"^##\s*七、", block)
        return content.rstrip() + "\n\n" + block.strip() + "\n"

    head, body = sec.group(1), sec.group(2)
    # 节内第一张 markdown 表（特征|说明书|附图）
    m_table = re.search(
        r"(\|[^\n]+\|\n\|[-: |]+\|\n(?:\|[^\n]+\|\n)+)",
        body,
    )
    if m_table:
        insert_at = sec.start(2) + m_table.end()
        return (
            content[:insert_at].rstrip()
            + "\n\n"
            + block.strip()
            + "\n\n"
            + content[insert_at:].lstrip("\n")
        )
    # 无表则插在「### 附图」前，再不行节末（七之前）
    m_fig = re.search(r"^###\s*附图", body, re.M)
    if m_fig:
        insert_at = sec.start(2) + m_fig.start()
        return (
            content[:insert_at].rstrip()
            + "\n\n"
            + block.strip()
            + "\n\n"
            + content[insert_at:]
        )
    return _insert_before_heading(content, r"^##\s*七、", block)


def inject_clue_annotations(content: str, clues: list[dict]) -> str:
    """L1–L3：导航入口 + 一/二/七/八/九语境旁注 + 权/特征点对点；L4 附录由 upsert_appendix_b。"""
    if not clues:
        return content
    content = _strip_injected_clue_blocks(content)
    n = len(clues)
    primary = clues[0]
    point = _clue_highlight(primary)

    # —— L1：导航 + 文首入口 ——
    nav_item = f"[[clues/_线索索引|公开线索（{n} 条）]]"
    if "## Obsidian 导航" in content and f"公开线索（{n} 条）" not in content:
        content = re.sub(
            r"(##\s*Obsidian\s*导航\s*\n(?:- .+\n)*)",
            rf"\1- {nav_item}\n",
            content,
            count=1,
        )
    l1 = (
        f"> [!tip]- 公开线索入口\n"
        f"> 本案整理了 **{n}** 条公开检索线索（推测语境）。"
        f"详见 [[clues/_线索索引|线索文件夹]]；"
        f"下文各节有折叠旁注，**不是**说明书/权利要求证据。"
    )
    if "公开线索入口" not in content:
        content = _insert_before_heading(content, r"^##\s*一、", l1)

    # —— L2：一、二、七、八、九 ——
    l2_one = _render_warning(
        "公开案例（推测）",
        [
            f"公开语境示例：{point} — {_clue_link(primary)}。",
            "仅供理解行业落地话术，**不能**等同或缩小本专利保护范围。",
        ],
    )
    content = _insert_before_heading(content, r"^##\s*二、", l2_one)

    l2_two = _render_warning(
        "公开案例（推测）",
        [
            "叙事对照：外部材料多谈「涂覆隔膜 / 耐温安全」产品能力；"
            "本案专利叙事还强调**基膜配方与湿法工艺组合**（以正文权要/说明书为准）。",
            " · ".join(_clue_link(c) for c in clues[:3]),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*三、", l2_two)

    l2_seven = _render_warning(
        "差别对照·公开线索",
        [
            "对照公开产品话术时：可看外部强调的「涂覆 / 耐热 / 粘接」等卖点，"
            "再回到本节——哪些差别来自**专利文本**，哪些只是行业语境。",
            " · ".join(_clue_link(c) for c in clues[:3]),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*八、", l2_seven)

    l2_eight = _render_warning(
        "阅读建议·公开线索",
        [
            f"建议打开 [[clues/_线索索引|线索文件夹]]，先扫产品/新闻话术，再回看权1骨架与特征表。",
            f"当前高相关示例：{_clue_link(primary)} — {point}",
        ],
    )
    content = _insert_before_heading(content, r"^##\s*九、", l2_eight)

    l2_nine = _render_warning(
        "场景·公开线索",
        [
            "应用场景的专利内依据见上表；公开线索仅补充「谁在卖类似隔膜/涂覆」的语境。",
            " · ".join(_clue_link(c) for c in clues[:3]),
        ],
    )
    content = _insert_before_heading(content, r"^##\s*十、", l2_nine)

    # —— L3：权项点对点 ——
    claim_groups: dict[int, list[dict]] = {}
    for c in clues:
        for num in c.get("related_claims") or []:
            try:
                claim_groups.setdefault(int(num), []).append(c)
            except (TypeError, ValueError):
                continue
    # 从后往前插，避免偏移
    for num, group in sorted(claim_groups.items(), reverse=True):
        body = [
            f"与**权利要求 {num}** 弱匹配的公开语境（非权要证据）：",
        ]
        for c in group[:3]:
            body.append(f"- {_clue_link(c)} — {_clue_highlight(c)}")
        block = _render_warning("权项—公开语境（推测）", body)
        pat = re.compile(
            rf"(>\s*\[!patent-claim\]\s*权利要求\s*{num}\b[\s\S]*?)(?=\n>\s*\[!patent-claim\]|\n##\s|\n\| 特征 \||\Z)",
            re.M,
        )
        m = pat.search(content)
        if m:
            content = content[: m.end()].rstrip() + "\n\n" + block + "\n\n" + content[m.end() :]
        else:
            pass

    # 若完全没插到权 callout，保留总览挂在第四节末
    if "权项—公开语境（推测）" not in content:
        overview = render_annotation_callout(clues)
        if overview:
            content = _insert_before_heading(content, r"^##\s*五、", overview.strip())

    # —— L3：特征公开语境 → 紧挨第六节对照表下方（附图之前）——
    # 只展示笔记里真实存在的特征行（第四节 F 编号或第六节特征名）；丢弃 sidecar 残留空号。
    catalog = harvest_feature_entries(content)
    feat_groups: dict[str, dict] = {}  # display_key -> {ent, clues}
    for c in clues:
        keys = list(c.get("related_feature_ids") or [])
        if not keys and c.get("related_features"):
            keys = [str(x) for x in c.get("related_features")[:2]]
        resolved: list[dict] = []
        for key in keys:
            ent = resolve_feature_entry(str(key), catalog)
            if ent:
                resolved.append(ent)
        if not resolved and catalog:
            live = match_clue_to_note(c, feature_entries=catalog)
            for key in live.get("related_feature_ids") or []:
                ent = resolve_feature_entry(str(key), catalog)
                if ent:
                    resolved.append(ent)
        for ent in resolved:
            disp = feature_display_name(ent)
            slot = feat_groups.setdefault(disp, {"ent": ent, "clues": []})
            if c not in slot["clues"]:
                slot["clues"].append(c)
    if feat_groups:
        lines = [
            "下列为**本笔记特征表**与公开线索的弱匹配（有 F 编号则写 F+名称，否则用第六节特征名）。",
            "仅供语境对照，不改写表内说明书/附图依据。",
            "",
        ]
        for disp, slot in list(feat_groups.items())[:8]:
            group = slot["clues"]
            bits = "；".join(
                f"{_clue_link(c, (c.get('title') or '')[:24])}（{_clue_highlight(c, limit=40)}）"
                for c in group[:2]
            )
            lines.append(f"- **{disp}** ← {bits}")
        feat_block = _render_warning("特征—公开语境（推测）", lines)
        content = _insert_after_section6_feature_table(content, feat_block)

    # —— L2 补充：术语节 ——
    term_hits: list[str] = []
    sec5 = re.search(r"^##\s*五、专利内术语表([\s\S]*?)(?=^##\s*六、|\Z)", content, re.M)
    if sec5:
        terms = re.findall(r"\|\s*\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", sec5.group(1))
        if not terms:
            # 纯文本术语列（无 wiki link）
            terms = [
                m.group(1).strip()
                for m in re.finditer(
                    r"^\|\s*([^|]+?)\s*\|", sec5.group(1), re.M
                )
                if m.group(1).strip()
                and not re.match(r"^[-:]+$", m.group(1).strip())
                and m.group(1).strip() not in ("术语", "本文含义/位置", "备注")
            ]
        for term in terms[:12]:
            tokens = _term_match_tokens(term)
            for c in clues:
                blob = f"{c.get('title')} {c.get('summary')} {c.get('reason')}"
                if tokens and any(t in blob for t in tokens):
                    term_hits.append(f"- **{term}** ← {_clue_link(c)}")
                    break
    if term_hits:
        term_block = _render_warning(
            "术语·公开语境",
            ["术语与公开材料共现（推测）："] + term_hits[:6],
        )
        content = _insert_before_heading(content, r"^##\s*六、", term_block)

    return content


def render_annotation_callout(clues: list[dict]) -> str:
    matched = [
        c
        for c in clues
        if c.get("related_claims")
        or c.get("related_features")
        or c.get("related_feature_ids")
    ]
    if not matched:
        matched = list(clues)
    if not matched:
        return ""
    lines = [
        "",
        "> [!warning]- 外部线索（推测）",
        "> 下列公开线索与权项/特征有**弱匹配**，仅供理解语境，**不是**说明书依据。",
    ]
    for c in matched:
        bits: list[str] = []
        if c.get("related_claims"):
            bits.append("权" + "、".join(str(n) for n in c["related_claims"]))
        fids = c.get("related_feature_ids") or []
        if fids:
            bits.append("特征 " + "、".join(str(x) for x in fids[:4]))
        elif c.get("related_features"):
            bits.append("特征共现：" + "；".join(c["related_features"][:2]))
        hl = _clue_highlight(c, limit=48)
        lines.append(f"> - {_clue_link(c)} — {' · '.join(bits) if bits else hl}")
    lines.append("")
    return "\n".join(lines)


def render_clue_note(
    clue: dict,
    *,
    pub: str,
    note_link: str = "",
) -> str:
    claims = clue.get("related_claims") or []
    feats = clue.get("related_features") or []
    status = clue.get("status") or "draft"
    fetched_at = clue.get("fetched_at") or ""
    summary = format_summary_for_markdown(
        sanitize_clue_summary(
            clue.get("summary") or "",
            title=clue.get("title") or "",
            reason=clue.get("reason") or "",
        )
    )
    page_title = (clue.get("page_title") or "").strip()
    # 去掉「公司_公司」重复标题噪音
    page_title = re.sub(r"(_[^_]*){2,}$", "", page_title).strip("_") or page_title
    err = (clue.get("fetch_error") or "").strip()
    lines = [
        "---",
        "tags:",
        "  - patent/clue",
        "cssclasses:",
        "  - patent-clue",
        f"pub_number: {pub}",
        f"clue_id: {clue.get('clue_id') or ''}",
        f"confidence: {clue.get('confidence') or '中'}",
        f"status: {status}",
        f"url: {clue.get('url') or ''}",
        "related_claims:",
    ]
    if claims:
        for n in claims:
            lines.append(f"  - {n}")
    else:
        lines.append("  []")
    lines.append("related_features:")
    if feats:
        for f in feats:
            lines.append(f"  - {json.dumps(f, ensure_ascii=False)}")
    else:
        lines.append("  []")
    if fetched_at:
        lines.append(f"fetched_at: {fetched_at}")
    lines.extend(
        [
            "---",
            f"# 线索：{clue.get('title') or '未命名'}",
            "",
            "> [!warning] 推测线索",
            "> 公开网页语境，**不构成法律意见**，也不是说明书/权利要求证据。",
            "",
            "## 元信息",
            "",
            f"- **置信度**：{clue.get('confidence') or '中'}",
            f"- **来源**：[打开原文]({clue.get('url') or ''})",
            f"- **与本案关系**：{clue.get('reason') or '—'}",
            f"- **状态**：{status}",
        ]
    )
    if note_link:
        lines.append(f"- **所属解读**：[[{note_link}|打开解读]]")
    lines.extend(["", "## 页面摘要", ""])
    if page_title:
        lines.append(f"**页面标题**：{page_title}")
        lines.append("")
    if summary:
        # 列表/段落直接写；勿把原始网页整页粘贴进笔记
        lines.append(summary)
        lines.append("")
    elif err:
        lines.append(f"（抓取未成功：{err}。请 Agent 重读该 URL，或启用脚本降级。）")
        lines.append("")
    else:
        lines.append(
            "（暂无摘要。主路径应由 Agent 写入可读短文/要点列表，勿粘贴整页导航。）"
        )
        lines.append("")
    lines.extend(["", "## 可能相关权项 / 特征", ""])
    if claims:
        lines.append("- **权项**：" + "、".join(f"权{n}" for n in claims))
    if feats:
        lines.append("- **特征共现**：" + "；".join(feats))
    if not claims and not feats:
        lines.append("- （弱匹配未命中；仍可作行业语境参考）")
    lines.append("")
    return "\n".join(lines)


def render_clues_index(clues: list[dict], *, pub: str, note_link: str = "") -> str:
    lines = [
        "---",
        "tags:",
        "  - patent/clue-index",
        "---",
        f"# `{pub}` 公开线索索引",
        "",
        "> 推测层材料，可手工追加笔记后在此补链。**不构成法律意见**。",
        "",
    ]
    if note_link:
        lines.append(f"- 解读：[[{note_link}|打开]]")
        lines.append("")
    lines.extend(
        [
            "| 线索 | 置信 | 状态 | 可能相关 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for c in clues:
        fname = c.get("filename") or ""
        stem = Path(fname).stem if fname else c.get("clue_id") or "线索"
        title = c.get("title") or stem
        claims = c.get("related_claims") or []
        rel = "、".join(f"权{n}" for n in claims) if claims else "—"
        lines.append(
            f"| [[clues/{stem}|{title[:40]}]] | {c.get('confidence') or '中'} "
            f"| {c.get('status') or '—'} | {rel} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_appendix_b(clues: list[dict], *, clues_dir_link: str) -> str:
    if not clues:
        return (
            "### B. 公开检索线索\n\n"
            "> [!warning]- 公开检索线索\n"
            ">\n"
            "> 未发现可核验的公开对应，可能为防御性/储备专利。\n"
        )
    lines = [
        "### B. 公开检索线索",
        "",
        "> [!warning]- 公开检索线索",
        ">",
        f"> 详情与抓取摘要见 [[{clues_dir_link}|线索文件夹]]（最多保留高置信条目）。",
        ">",
    ]
    for c in clues:
        stem = Path(c.get("filename") or "x.md").stem
        title = c.get("title") or stem
        conf = c.get("confidence") or "中"
        url = c.get("url") or ""
        reason = (c.get("reason") or "")[:80]
        link = f"[[clues/{stem}|{title}]]"
        src = f"[来源]({url})" if url else "来源：—"
        lines.append(
            f"> - **线索**：{link} — 置信度：{conf} — {src} — 理由：{reason}"
        )
    lines.append("")
    return "\n".join(lines)


def upsert_appendix_b(content: str, section_md: str) -> str:
    section_md = section_md.rstrip() + "\n"
    if APPENDIX_B_RE.search(content):
        return APPENDIX_B_RE.sub(section_md, content, count=1)
    # 插在「十、附录」内、免责之前
    m = re.search(r"^##\s*十、附录[\s\S]*?(?=^##\s*十一、|\Z)", content, re.M)
    if m:
        block = m.group(0)
        if "### B." in block:
            return content
        insert_at = m.end()
        return content[:insert_at].rstrip() + "\n\n" + section_md + "\n" + content[insert_at:]
    return content.rstrip() + "\n\n" + section_md


def materialize_clues(
    clues: list[dict],
    *,
    note_dir: Path,
    pub: str,
    note_rel: str = "",
    claim_summaries: dict[int, str] | None = None,
    feature_rows: list[str] | None = None,
    feature_entries: list[dict] | None = None,
    max_keep: int = DEFAULT_MAX_CLUES,
    fetch_fallback: bool = False,
    fetch: bool | None = None,
) -> tuple[list[dict], str]:
    """筛选→写入 clues/→附录 Markdown。

    摘要主路径应由 Agent 写入 public_clues.json（summary/status=agent_fetched）。
    fetch_fallback=True 时，仅对**缺少 summary** 的条目尝试脚本 HTTP 降级抓取。
    参数 fetch 为旧别名：True/False 映射到 fetch_fallback（兼容调用方）。
    """
    if fetch is not None:
        fetch_fallback = bool(fetch)
    kept, _dropped = filter_clues(clues, max_keep=max_keep)
    clues_dir = note_dir / "clues"
    clues_dir.mkdir(parents=True, exist_ok=True)
    note_link = note_rel[:-3] if note_rel.endswith(".md") else note_rel
    today = date.today().isoformat()
    entries = list(feature_entries or [])
    if not entries and feature_rows:
        entries = [{"id": "", "label": "", "text": r} for r in feature_rows]

    rich: list[dict] = []
    for i, c in enumerate(kept):
        item = normalize_clue(c, index=i)
        # 保留 Agent 已写字段
        for key in (
            "summary",
            "page_title",
            "status",
            "related_claims",
            "related_features",
            "related_feature_ids",
            "fetch_note",
            "fetched_at",
        ):
            if c.get(key) not in (None, "", []):
                item[key] = c[key]
        fname = clue_filename(item.get("title") or "线索", i)
        item["filename"] = fname

        # 无论来源，落盘前清洗摘要（修竖排拆字 / 导航噪音 / > 引用污染）
        if item.get("summary"):
            item["summary"] = sanitize_clue_summary(
                str(item.get("summary") or ""),
                title=item.get("title") or "",
                reason=item.get("reason") or "",
            )

        has_summary = bool(str(item.get("summary") or "").strip())
        status = str(item.get("status") or "").strip()
        if has_summary and not status:
            item["status"] = "agent_fetched"
            item.setdefault("fetched_at", today)
        elif has_summary and status in ("draft", ""):
            item["status"] = "agent_fetched"
            item.setdefault("fetched_at", today)
        elif (
            fetch_fallback
            and item.get("url")
            and not has_summary
            and status
            not in ("agent_fetched", "fetched", "script_fetched", "reviewed")
        ):
            fetched = fetch_url_summary(item["url"])
            item["status"] = (
                "script_fetched" if fetched.get("ok") else "fetch_failed"
            )
            item["summary"] = fetched.get("summary") or ""
            item["page_title"] = fetched.get("page_title") or item.get("page_title") or ""
            item["fetch_error"] = fetched.get("error") or ""
            item["fetch_note"] = (item.get("fetch_note") or "") + (
                " · 脚本降级抓取" if fetched.get("ok") else " · 脚本降级失败"
            )
            if fetched.get("ok"):
                item["fetched_at"] = today
        else:
            item.setdefault("status", status or "draft")

        match = match_clue_to_note(
            item,
            claim_summaries=claim_summaries,
            feature_entries=entries,
        )
        if not item.get("related_claims"):
            item["related_claims"] = match.get("related_claims") or []
        # 特征锚定依赖当前笔记表结构：始终按正文重算，避免 sidecar 残留空号 F1–F6
        item["related_features"] = match.get("related_features") or []
        item["related_feature_ids"] = match.get("related_feature_ids") or []

        body = render_clue_note(item, pub=pub, note_link=note_link)
        (clues_dir / fname).write_text(body, encoding="utf-8")
        rich.append(item)

    index_body = render_clues_index(rich, pub=pub, note_link=note_link)
    (clues_dir / "_线索索引.md").write_text(index_body, encoding="utf-8")

    # 旁路 JSON，供 Canvas / 再入库
    (clues_dir / "clues.json").write_text(
        json.dumps(rich, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    clues_dir_link = "clues/_线索索引"
    appendix = render_appendix_b(rich, clues_dir_link=clues_dir_link)
    return rich, appendix


def load_clues_sidecar(note_dir: Path) -> list[dict]:
    path = note_dir / "clues" / "clues.json"
    if not path.is_file():
        return []
    try:
        return as_clues(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return []


def clue_cards_for_canvas(clues: list[dict], *, note_dir_rel: str = "") -> list[dict]:
    """供 build_canvas 使用的短卡数据。"""
    cards = []
    base = note_dir_rel.replace("\\", "/").rstrip("/")
    for c in clues[: DEFAULT_MAX_CLUES]:
        stem = Path(c.get("filename") or "x.md").stem
        link = f"{base}/clues/{stem}" if base else f"clues/{stem}"
        claims = c.get("related_claims") or []
        fids = c.get("related_feature_ids") or []
        cards.append(
            {
                "id": c.get("clue_id") or stem,
                "title": c.get("title") or stem,
                "confidence": c.get("confidence") or "中",
                "status": c.get("status") or "",
                "link": link,
                "related_claims": claims,
                "related_feature_ids": fids,
                "reason": _clue_highlight(c, limit=72),
            }
        )
    return cards
