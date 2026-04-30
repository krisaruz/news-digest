"""HTML 卡片生成器 V3 - CSS 动画驱动的动效新闻卡片 1920x1080

核心机制:
- 所有元素入场动画由 CSS @keyframes 定义
- animation-play-state: paused + animation-delay: calc(var(--t) * -Xs) 冻结到指定时刻
- 外部通过设置 CSS 变量 --t (0~1) 来推进动画进度
- Playwright 逐帧截取 → ffmpeg 合成视频片段

动画时间轴:
- 标题卡:   2s (背景→标题弹入→期号滑入→统计浮入→关键词逐个弹出→环脉冲)
- 新闻卡:   1.5s (装饰淡入→序号弹入→标题滑入→描述淡入→进度条→来源)
- 总结卡:   2s (标题→关键词stagger→底部淡入)
- 结尾卡:   2s (环扩展→文字弹入→分割线展开→社交标签弹出)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CARD_WIDTH = 1920
CARD_HEIGHT = 1080

ANIM_DUR_TITLE = 2.0
ANIM_DUR_ITEM = 1.5
ANIM_DUR_SUMMARY = 2.0
ANIM_DUR_END = 2.0

COLORS = {
    "bg_primary": "#0a0e1a",
    "bg_accent": "#0ea5e9",
    "bg_gradient_end": "#8b5cf6",
    "text_primary": "#f8fafc",
    "text_secondary": "#cbd5e1",
    "text_muted": "#64748b",
    "border": "rgba(255,255,255,0.10)",
    "tag_text": "#38bdf8",
}

CATEGORY_PALETTE = {
    "AI 相关": {"accent": "#0ea5e9", "bg": "rgba(14,165,233,0.18)", "icon": "\U0001f916"},
    "工具": {"accent": "#10b981", "bg": "rgba(16,185,129,0.18)", "icon": "\U0001f527"},
    "科技动态": {"accent": "#f59e0b", "bg": "rgba(245,158,11,0.18)", "icon": "\U0001f4e1"},
    "文章推荐": {"accent": "#8b5cf6", "bg": "rgba(139,92,246,0.18)", "icon": "\U0001f4dd"},
    "资源": {"accent": "#ec4899", "bg": "rgba(236,72,153,0.18)", "icon": "\U0001f4e6"},
    "其他": {"accent": "#6366f1", "bg": "rgba(99,102,241,0.18)", "icon": "\U0001f4a1"},
}

# ---------- 基础 CSS ----------

_BASE = f"""* {{ margin: 0; padding: 0; box-sizing: border-box; }}
:root {{ --t: 0; }}
body {{
  width: {CARD_WIDTH}px; height: {CARD_HEIGHT}px;
  background: {COLORS['bg_primary']};
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  color: {COLORS['text_primary']};
  overflow: hidden; position: relative;
}}"""

_CORNERS_CSS = """.corner {
  position: absolute; width: 50px; height: 50px;
  border-color: rgba(14,165,233,0.25); border-style: solid;
}
.corner-tl { top: 32px; left: 32px; border-width: 2px 0 0 2px; }
.corner-tr { top: 32px; right: 32px; border-width: 2px 2px 0 0; }
.corner-bl { bottom: 32px; left: 32px; border-width: 0 0 2px 2px; }
.corner-br { bottom: 32px; right: 32px; border-width: 0 2px 2px 0; }"""

_CORNERS_HTML = '<div class="corner corner-tl"></div><div class="corner corner-tr"></div><div class="corner corner-bl"></div><div class="corner corner-br"></div>'


def _grid(op: float = 0.035) -> str:
    return f"position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,{op}) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,{op}) 1px,transparent 1px);background-size:60px 60px;"


# ---------- 动画辅助 ----------

def _anim(name: str, total_dur: float, start: float, dur: float, fill: str = "both") -> str:
    """生成 paused + delay-driven 动画声明。

    通过 --t (0~1) 控制进度：
      animation-delay = var(--t) * -total_dur
    加上 animation-delay 偏移 start，实现错开入场。
    """
    return (
        f"animation: {name} {dur}s ease-out {fill};"
        f"animation-play-state: paused;"
        f"animation-delay: calc(var(--t) * -{total_dur}s + {start}s);"
    )


def _anim_infinite(name: str, total_dur: float, dur: float) -> str:
    """循环动画（如脉冲），同样受 --t 控制。"""
    return (
        f"animation: {name} {dur}s ease-in-out infinite;"
        f"animation-play-state: paused;"
        f"animation-delay: calc(var(--t) * -{total_dur}s);"
    )


# ---------- 通用 @keyframes ----------

_KEYFRAMES = """
@keyframes fadeIn {
  from { opacity: 0; } to { opacity: 1; }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(40px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInLeft {
  from { opacity: 0; transform: translateX(-60px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes fadeInRight {
  from { opacity: 0; transform: translateX(60px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.75); }
  to   { opacity: 1; transform: scale(1); }
}
@keyframes popIn {
  0%   { opacity: 0; transform: scale(0.5); }
  70%  { opacity: 1; transform: scale(1.08); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes expandWidth {
  from { width: 0; } to { width: 100%; }
}
@keyframes expandFromCenter {
  from { width: 0; left: 50%; } to { width: 100%; left: 0; }
}
@keyframes pulse {
  0%, 100% { opacity: 0.12; transform: scale(1); }
  50%      { opacity: 0.25; transform: scale(1.05); }
}
@keyframes ringExpand {
  from { opacity: 0; transform: translate(-50%,-50%) scale(0.6); }
  to   { opacity: 1; transform: translate(-50%,-50%) scale(1); }
}
@keyframes drawLine {
  from { transform: scaleX(0); } to { transform: scaleX(1); }
}
@keyframes fillBar {
  from { width: 0%; }
}
@keyframes gradientShift {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
"""


# ---------- 装饰模板 ----------

def _deco_a(accent: str) -> tuple[str, str]:
    css = f""".deco-bar {{
  position:absolute; left:0; top:0; width:8px; height:100%;
  background: linear-gradient(180deg, {accent}, {COLORS['bg_gradient_end']});
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0, 0.4)}
}}
.deco-glow {{
  position:absolute; width:600px; height:600px; border-radius:50%;
  top:-200px; right:-150px;
  background: radial-gradient(circle, {accent} 0%, transparent 65%);
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0.1, 0.5)}
}}"""
    html = '<div class="deco-bar"></div><div class="deco-glow"></div>'
    return css, html


def _deco_b(accent: str) -> tuple[str, str]:
    css = f""".deco-stripe {{
  position:absolute; bottom:0; left:0; width:100%; height:140px;
  background: repeating-linear-gradient(-45deg, transparent, transparent 18px, {accent}08 18px, {accent}08 20px);
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0, 0.4)}
}}
.deco-blob {{
  position:absolute; width:400px; height:400px; border-radius:50%;
  bottom:-200px; left:-100px;
  background: radial-gradient(circle, {accent} 0%, transparent 60%);
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0.1, 0.5)}
}}"""
    html = '<div class="deco-stripe"></div><div class="deco-blob"></div>'
    return css, html


def _deco_c(accent: str) -> tuple[str, str]:
    css = f""".deco-arc {{
  position:absolute; width:500px; height:1000px; border-radius:500px 0 0 500px;
  right:-250px; top:50%; transform:translateY(-50%);
  border-left: 3px solid {accent}20;
  background: linear-gradient(90deg, {accent}06, transparent);
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0, 0.4)}
}}
.deco-dots {{
  position:absolute; top:40px; left:40px; width:180px; height:180px;
  background-image: radial-gradient({accent}25 2px, transparent 2px);
  background-size: 18px 18px;
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0.1, 0.5)}
}}"""
    html = '<div class="deco-arc"></div><div class="deco-dots"></div>'
    return css, html


def _deco_d(accent: str) -> tuple[str, str]:
    css = f""".deco-diag {{
  position:absolute; inset:0;
  background: linear-gradient(135deg, {accent}0a 0%, transparent 40%, transparent 60%, {COLORS['bg_gradient_end']}08 100%);
  opacity: 0; {_anim('fadeIn', ANIM_DUR_ITEM, 0, 0.4)}
}}
.deco-sp {{
  position:absolute; width:10px; height:10px; border-radius:50%;
  background: {accent}; opacity:0;
  box-shadow: 0 0 30px 8px {accent}30;
  {_anim('fadeIn', ANIM_DUR_ITEM, 0.15, 0.4)}
}}
.sp1 {{ top:60px; left:60px; }} .sp2 {{ top:60px; right:60px; }}
.sp3 {{ bottom:60px; left:60px; }} .sp4 {{ bottom:60px; right:60px; }}"""
    html = '<div class="deco-diag"></div><div class="deco-sp sp1"></div><div class="deco-sp sp2"></div><div class="deco-sp sp3"></div><div class="deco-sp sp4"></div>'
    return css, html


_DECO_FUNCS = [_deco_a, _deco_b, _deco_c, _deco_d]


class CardGenerator:
    """生成带 CSS 动画的新闻卡片 HTML"""

    def __init__(self, output_dir: str = "data/output/cards"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ================================================================
    # 标题卡  (ANIM_DUR_TITLE = 2s)
    # ================================================================
    def generate_title_card(
        self,
        issue_number: int,
        date_str: str,
        total_articles: int = 10,
        keywords: list[str] | None = None,
        filename: str = "title.html",
    ) -> str:
        T = ANIM_DUR_TITLE

        kw_items = ""
        if keywords:
            for ki, k in enumerate(keywords[:6]):
                delay = 1.0 + ki * 0.1
                kw_items += f'<span class="kw" style="{_anim("popIn", T, delay, 0.35)}">{k}</span>\n'
            kw_items = f'<div class="kw-row">{kw_items}</div>'

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_BASE}
{_KEYFRAMES}
.bg {{
  position:absolute; inset:0;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(14,165,233,0.12) 0%, transparent 55%),
    radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.10) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 90%, rgba(14,165,233,0.06) 0%, transparent 40%);
  opacity: 0; {_anim('fadeIn', T, 0, 0.4)}
}}
.grid {{ {_grid(0.03)} opacity: 0; {_anim('fadeIn', T, 0, 0.5)} }}
.ring {{
  position:absolute; border-radius:50%;
  border: 1.5px solid rgba(14,165,233,0.12);
  top:50%; left:50%; transform:translate(-50%,-50%) scale(0.6);
  opacity:0;
}}
.r1 {{ width:400px; height:400px; {_anim('ringExpand', T, 1.5, 0.5)} }}
.r2 {{ width:600px; height:600px; {_anim('ringExpand', T, 1.6, 0.5)} }}
.r3 {{ width:800px; height:800px; {_anim('ringExpand', T, 1.7, 0.5)} }}
.glow1 {{
  position:absolute; width:700px; height:700px; border-radius:50%;
  top:50%; left:50%; transform:translate(-50%,-50%);
  background: radial-gradient(circle, rgba(14,165,233,0.08), transparent 60%);
  {_anim_infinite('pulse', T, 3.0)}
}}
{_CORNERS_CSS}
.corner {{ opacity:0; {_anim('fadeIn', T, 0.2, 0.4)} }}
.wrap {{
  position:absolute; inset:0;
  display:flex; align-items:center; justify-content:center; z-index:10;
}}
.inner {{ text-align:center; max-width:1000px; }}
.badge {{
  display:inline-block;
  padding:10px 36px; margin-bottom:40px;
  border:1px solid rgba(14,165,233,0.35); border-radius:30px;
  font-size:15px; letter-spacing:6px;
  color:{COLORS['tag_text']};
  background:rgba(14,165,233,0.08);
  text-transform:uppercase;
  opacity:0; {_anim('fadeInUp', T, 0.1, 0.5)}
}}
.hero {{
  font-size:96px; font-weight:900; line-height:1.1;
  background: linear-gradient(135deg, #0ea5e9 0%, #8b5cf6 50%, #0ea5e9 100%);
  background-size:200% 200%;
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text; letter-spacing:4px;
  opacity:0; {_anim('scaleIn', T, 0.2, 0.6)}
}}
.line {{
  width:140px; height:2px; margin:28px auto;
  background: linear-gradient(90deg, transparent, {COLORS['bg_accent']}, transparent);
  transform-origin:center; transform:scaleX(0);
  {_anim('drawLine', T, 0.5, 0.4)}
}}
.sub {{
  font-size:28px; color:{COLORS['text_secondary']}; letter-spacing:2px;
  opacity:0; {_anim('fadeInLeft', T, 0.5, 0.5)}
}}
.date {{
  font-size:18px; color:{COLORS['text_muted']}; margin-top:14px; letter-spacing:4px;
  opacity:0; {_anim('fadeInLeft', T, 0.6, 0.4)}
}}
.stats {{
  margin-top:32px; display:flex; gap:36px; justify-content:center;
}}
.stat {{
  padding:12px 28px;
  background:rgba(255,255,255,0.04);
  border:1px solid {COLORS['border']};
  border-radius:14px;
  font-size:15px; color:{COLORS['text_secondary']};
  opacity:0;
}}
.stat:nth-child(1) {{ {_anim('fadeInUp', T, 0.7, 0.4)} }}
.stat:nth-child(2) {{ {_anim('fadeInUp', T, 0.8, 0.4)} }}
.stat:nth-child(3) {{ {_anim('fadeInUp', T, 0.9, 0.4)} }}
.stat b {{ color:{COLORS['tag_text']}; font-size:22px; margin-right:6px; }}
.kw-row {{
  margin-top:28px; display:flex; gap:12px; justify-content:center; flex-wrap:wrap;
}}
.kw {{
  padding:6px 18px;
  background:rgba(14,165,233,0.08);
  border:1px solid rgba(14,165,233,0.20);
  border-radius:8px;
  font-size:13px; color:{COLORS['tag_text']};
  letter-spacing:1px;
  opacity:0;
}}
</style></head>
<body>
<div class="bg"></div><div class="grid"></div>
<div class="glow1"></div>
<div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div>
{_CORNERS_HTML}
<div class="wrap"><div class="inner">
  <div class="badge">AI Daily Briefing</div>
  <div class="hero">AI \u65e9\u62a5</div>
  <div class="line"></div>
  <div class="sub">\u7b2c {issue_number} \u671f</div>
  <div class="date">{date_str}</div>
  <div class="stats">
    <div class="stat"><b>{total_articles}</b>\u6761\u8d44\u8baf</div>
    <div class="stat"><b>AI</b>\u79d1\u6280\u524d\u6cbf</div>
    <div class="stat"><b>60s</b>\u901f\u89c8</div>
  </div>
  {kw_items}
</div></div>
</body></html>"""
        return self._save(filename, html)

    # ================================================================
    # 新闻条目卡  (ANIM_DUR_ITEM = 1.5s)
    # ================================================================
    def generate_item_card(
        self,
        index: int,
        total: int,
        title: str,
        description: str,
        image_url: str = "",
        source: str = "",
        category: str = "AI \u76f8\u5173",
        filename: Optional[str] = None,
    ) -> str:
        if not filename:
            filename = f"item-{index:02d}.html"

        T = ANIM_DUR_ITEM
        pal = CATEGORY_PALETTE.get(category, CATEGORY_PALETTE["\u5176\u4ed6"])
        accent = pal["accent"]
        accent_bg = pal["bg"]
        icon = pal["icon"]
        progress_pct = (index / total) * 100

        deco_fn = _DECO_FUNCS[(index - 1) % len(_DECO_FUNCS)]
        deco_css, deco_html = deco_fn(accent)

        if image_url:
            content_css = f""".content {{ flex:1; display:flex; gap:48px; align-items:center; }}
.txt {{ flex:1.2; display:flex; flex-direction:column; gap:20px; }}
.img-side {{ flex:0.8; display:flex; align-items:center; justify-content:center; opacity:0; {_anim('fadeIn', T, 0.6, 0.5)} }}
.img-frame {{
  width:100%; max-width:500px; aspect-ratio:16/10;
  border-radius:18px; overflow:hidden;
  border:1px solid {COLORS['border']};
  background:rgba(255,255,255,0.02);
  box-shadow: 0 16px 48px rgba(0,0,0,0.3);
}}
.img-frame img {{ width:100%; height:100%; object-fit:cover; }}"""
            content_html = f"""<div class="content">
  <div class="txt">
    <div class="title">{title}</div>
    <div class="divider-wrap"><div class="divider"></div></div>
    <div class="desc">{description}</div>
  </div>
  <div class="img-side"><div class="img-frame"><img src="{image_url}" alt=""></div></div>
</div>"""
        else:
            content_css = f""".content {{ flex:1; display:flex; gap:0; align-items:center; position:relative; }}
.txt {{ flex:1; display:flex; flex-direction:column; gap:22px; max-width:1200px; }}
.emoji-deco {{
  position:absolute; right:60px; top:50%; transform:translateY(-50%);
  font-size:140px; opacity:0;
  filter: blur(1px);
  {_anim('fadeIn', T, 0.4, 0.6)}
}}
.accent-block {{
  position:absolute; right:0; top:0; bottom:0; width:350px;
  background: linear-gradient(135deg, {accent}06, {accent}12, {COLORS['bg_gradient_end']}08);
  border-radius: 24px 0 0 24px;
  border-left: 2px solid {accent}15;
  opacity:0; {_anim('fadeIn', T, 0.1, 0.5)}
}}"""
            content_html = f"""<div class="content">
  <div class="accent-block"></div>
  <div class="emoji-deco">{icon}</div>
  <div class="txt">
    <div class="title">{title}</div>
    <div class="divider-wrap"><div class="divider"></div></div>
    <div class="desc">{description}</div>
  </div>
</div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_BASE}
{_KEYFRAMES}
.grid {{ {_grid(0.03)} opacity:0; {_anim('fadeIn', T, 0, 0.3)} }}
{deco_css}
.card {{
  position:relative; z-index:10;
  width:100%; height:100%;
  display:flex; flex-direction:column;
  padding:44px 68px;
}}
.top {{
  display:flex; align-items:center; justify-content:space-between;
  margin-bottom:28px;
}}
.left {{ display:flex; align-items:center; gap:18px; }}
.num {{
  width:60px; height:60px;
  background: linear-gradient(135deg, {accent}, {COLORS['bg_gradient_end']});
  border-radius:16px;
  display:flex; align-items:center; justify-content:center;
  font-size:28px; font-weight:900; color:#fff;
  box-shadow: 0 8px 28px {accent}50;
  opacity:0; {_anim('popIn', T, 0.1, 0.35)}
}}
.cat {{
  padding:8px 22px;
  background:{accent_bg};
  border:1px solid {accent}35;
  border-radius:20px;
  font-size:14px; color:{accent}; font-weight:600;
  box-shadow: 0 0 20px {accent}15;
  opacity:0; {_anim('fadeInLeft', T, 0.2, 0.35)}
}}
.prog {{ display:flex; align-items:center; gap:14px; opacity:0; {_anim('fadeIn', T, 0.8, 0.4)} }}
.prog-track {{
  width:160px; height:5px;
  background:rgba(255,255,255,0.08);
  border-radius:3px; overflow:hidden;
}}
.prog-fill {{
  height:100%; border-radius:3px;
  background: linear-gradient(90deg, {accent}, {COLORS['bg_gradient_end']});
  width:0; {_anim('fillBar', T, 0.8, 0.5)}
  animation-fill-mode: forwards;
}}
.prog-text {{
  font-size:13px; color:{COLORS['text_muted']};
  font-variant-numeric:tabular-nums;
}}
{content_css}
.title {{
  font-size:40px; font-weight:800; line-height:1.35;
  color:{COLORS['text_primary']};
  opacity:0; {_anim('fadeInUp', T, 0.3, 0.45)}
}}
.divider-wrap {{ overflow:hidden; }}
.divider {{
  width:60px; height:3px;
  background: linear-gradient(90deg, {accent}, transparent);
  border-radius:2px;
  transform-origin:left; transform:scaleX(0);
  {_anim('drawLine', T, 0.45, 0.3)}
}}
.desc {{
  font-size:23px; line-height:1.85;
  color:{COLORS['text_secondary']};
  opacity:0; {_anim('fadeIn', T, 0.5, 0.5)}
}}
.bot {{
  display:flex; align-items:center; justify-content:space-between;
  padding-top:18px;
  border-top:1px solid {COLORS['border']};
  opacity:0; {_anim('fadeIn', T, 1.0, 0.4)}
}}
.src {{ display:flex; align-items:center; gap:8px; font-size:14px; color:{COLORS['text_muted']}; }}
.src-dot {{ width:7px; height:7px; border-radius:50%; background:{accent}; box-shadow:0 0 8px {accent}60; }}
.brand {{ font-size:13px; color:{COLORS['text_muted']}50; letter-spacing:2px; }}
</style></head>
<body>
<div class="grid"></div>
{deco_html}
<div class="card">
  <div class="top">
    <div class="left">
      <div class="num">{index}</div>
      <div class="cat">{icon} {category}</div>
    </div>
    <div class="prog">
      <div class="prog-track"><div class="prog-fill" style="width:{progress_pct:.0f}%"></div></div>
      <span class="prog-text">{index} / {total}</span>
    </div>
  </div>
  {content_html}
  <div class="bot">
    <div class="src"><span class="src-dot"></span>{source}</div>
    <div class="brand">AI \u65e9\u62a5</div>
  </div>
</div>
</body></html>"""
        return self._save(filename, html)

    # ================================================================
    # 分类过渡卡
    # ================================================================
    def generate_category_card(
        self,
        category: str,
        article_count: int,
        filename: str = "category.html",
    ) -> str:
        T = 1.5
        pal = CATEGORY_PALETTE.get(category, CATEGORY_PALETTE["\u5176\u4ed6"])
        accent = pal["accent"]
        icon = pal["icon"]

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_BASE}
{_KEYFRAMES}
body {{ display:flex; align-items:center; justify-content:center; }}
.bg {{
  position:absolute; inset:0;
  background: radial-gradient(ellipse at 50% 50%, {accent}14 0%, transparent 55%);
  opacity:0; {_anim('fadeIn', T, 0, 0.4)}
}}
.grid {{ {_grid(0.03)} opacity:0; {_anim('fadeIn', T, 0, 0.5)} }}
.wrap {{ position:relative; z-index:10; text-align:center; }}
.emoji {{ font-size:80px; margin-bottom:28px; opacity:0; {_anim('popIn', T, 0.2, 0.4)} }}
.cat {{
  font-size:56px; font-weight:800;
  background: linear-gradient(135deg, {accent}, {COLORS['bg_gradient_end']});
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text;
  opacity:0; {_anim('scaleIn', T, 0.3, 0.5)}
}}
.line {{
  width:80px; height:2px; margin:24px auto;
  background: linear-gradient(90deg, transparent, {accent}, transparent);
  transform-origin:center; transform:scaleX(0);
  {_anim('drawLine', T, 0.6, 0.3)}
}}
.count {{ font-size:20px; color:{COLORS['text_secondary']}; letter-spacing:2px; opacity:0; {_anim('fadeInUp', T, 0.7, 0.4)} }}
</style></head>
<body>
<div class="bg"></div><div class="grid"></div>
<div class="wrap">
  <div class="emoji">{icon}</div>
  <div class="cat">{category}</div>
  <div class="line"></div>
  <div class="count">{article_count} \u6761\u8d44\u8baf</div>
</div>
</body></html>"""
        return self._save(filename, html)

    # ================================================================
    # 关键词总结卡  (ANIM_DUR_SUMMARY = 2s)
    # ================================================================
    def generate_summary_card(
        self,
        date_str: str,
        topics: list[str],
        total_articles: int = 10,
        filename: str = "summary.html",
    ) -> str:
        T = ANIM_DUR_SUMMARY
        palette = ["#0ea5e9", "#8b5cf6", "#10b981", "#f59e0b", "#ec4899", "#6366f1", "#14b8a6", "#f43f5e"]
        rows = ""
        for i, t in enumerate(topics):
            c = palette[i % len(palette)]
            delay = 0.4 + i * 0.15
            rows += f'<span class="topic" style="border-color:{c}30;background:{c}10;color:{c};{_anim("popIn", T, delay, 0.35)}">{t}</span>\n'

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_BASE}
{_KEYFRAMES}
body {{ display:flex; align-items:center; justify-content:center; }}
.bg {{
  position:absolute; inset:0;
  background:
    radial-gradient(ellipse at 30% 40%, rgba(139,92,246,0.10) 0%, transparent 55%),
    radial-gradient(ellipse at 70% 60%, rgba(14,165,233,0.10) 0%, transparent 55%);
  opacity:0; {_anim('fadeIn', T, 0, 0.4)}
}}
.grid {{ {_grid(0.03)} opacity:0; {_anim('fadeIn', T, 0, 0.5)} }}
{_CORNERS_CSS}
.corner {{ opacity:0; {_anim('fadeIn', T, 0.1, 0.3)} }}
.wrap {{ position:relative; z-index:10; text-align:center; max-width:1100px; }}
.badge {{
  display:inline-block;
  padding:8px 28px; margin-bottom:28px;
  border:1px solid rgba(14,165,233,0.25); border-radius:30px;
  font-size:14px; color:{COLORS['tag_text']};
  letter-spacing:4px; text-transform:uppercase;
  background:rgba(14,165,233,0.06);
  opacity:0; {_anim('fadeInUp', T, 0.1, 0.4)}
}}
.title {{
  font-size:52px; font-weight:800; margin-bottom:16px;
  background: linear-gradient(135deg, #0ea5e9, #8b5cf6);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text;
  opacity:0; {_anim('scaleIn', T, 0.15, 0.45)}
}}
.stat {{ font-size:18px; color:{COLORS['text_muted']}; margin-bottom:40px; opacity:0; {_anim('fadeIn', T, 0.3, 0.3)} }}
.stat b {{ color:{COLORS['tag_text']}; }}
.topics {{ display:flex; flex-wrap:wrap; gap:16px; justify-content:center; }}
.topic {{
  padding:16px 32px;
  border:1px solid;
  border-radius:14px;
  font-size:20px; font-weight:600;
  opacity:0;
}}
.meta {{ margin-top:48px; font-size:15px; color:{COLORS['text_muted']}; letter-spacing:4px; opacity:0; {_anim('fadeIn', T, 1.6, 0.4)} }}
</style></head>
<body>
<div class="bg"></div><div class="grid"></div>
{_CORNERS_HTML}
<div class="wrap">
  <div class="badge">Today's Topics</div>
  <div class="title">\u4eca\u65e5 AI \u5173\u952e\u8bcd</div>
  <div class="stat">\u5171 <b>{total_articles}</b> \u6761\u8d44\u8baf</div>
  <div class="topics">{rows}</div>
  <div class="meta">{date_str}</div>
</div>
</body></html>"""
        return self._save(filename, html)

    # ================================================================
    # 结尾卡  (ANIM_DUR_END = 2s)
    # ================================================================
    def generate_end_card(
        self,
        issue_number: int,
        filename: str = "end.html",
    ) -> str:
        T = ANIM_DUR_END

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_BASE}
{_KEYFRAMES}
body {{ display:flex; align-items:center; justify-content:center; }}
.bg {{
  position:absolute; inset:0;
  background: radial-gradient(ellipse at 50% 50%, rgba(14,165,233,0.10) 0%, transparent 55%);
  opacity:0; {_anim('fadeIn', T, 0, 0.4)}
}}
.ring {{
  position:absolute; border-radius:50%;
  border:1.5px solid rgba(14,165,233,0.12);
  top:50%; left:50%;
  opacity:0;
}}
.r1 {{ width:300px; height:300px; {_anim('ringExpand', T, 0, 0.5)} }}
.r2 {{ width:500px; height:500px; {_anim('ringExpand', T, 0.15, 0.5)} }}
.r3 {{ width:700px; height:700px; {_anim('ringExpand', T, 0.3, 0.5)} }}
.glow {{
  position:absolute; width:500px; height:500px; border-radius:50%;
  top:50%; left:50%; transform:translate(-50%,-50%);
  background: radial-gradient(circle, rgba(14,165,233,0.06), transparent 60%);
  {_anim_infinite('pulse', T, 3.0)}
}}
{_CORNERS_CSS}
.corner {{ opacity:0; {_anim('fadeIn', T, 0.3, 0.3)} }}
.wrap {{ position:relative; z-index:10; text-align:center; }}
.title {{
  font-size:68px; font-weight:800;
  background: linear-gradient(135deg, #0ea5e9, #8b5cf6);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text;
  opacity:0; {_anim('scaleIn', T, 0.3, 0.5)}
}}
.line {{
  width:100px; height:2px; margin:28px auto;
  background: linear-gradient(90deg, transparent, rgba(14,165,233,0.6), transparent);
  transform-origin:center; transform:scaleX(0);
  {_anim('drawLine', T, 0.7, 0.4)}
}}
.sub {{
  font-size:24px; color:{COLORS['text_secondary']}; letter-spacing:2px;
  opacity:0; {_anim('fadeInUp', T, 0.9, 0.4)}
}}
.sub2 {{
  font-size:18px; color:{COLORS['text_muted']}; margin-top:14px; letter-spacing:4px;
  opacity:0; {_anim('fadeInUp', T, 1.0, 0.4)}
}}
.social {{
  margin-top:40px; display:flex; gap:20px; justify-content:center;
}}
.social span {{
  padding:8px 22px;
  background:rgba(255,255,255,0.04);
  border:1px solid {COLORS['border']};
  border-radius:10px;
  font-size:14px; color:{COLORS['text_muted']};
  opacity:0;
}}
.social span:nth-child(1) {{ {_anim('popIn', T, 1.1, 0.3)} }}
.social span:nth-child(2) {{ {_anim('popIn', T, 1.2, 0.3)} }}
.social span:nth-child(3) {{ {_anim('popIn', T, 1.3, 0.3)} }}
</style></head>
<body>
<div class="bg"></div><div class="glow"></div>
<div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div>
{_CORNERS_HTML}
<div class="wrap">
  <div class="title">\u611f\u8c22\u89c2\u770b</div>
  <div class="line"></div>
  <div class="sub">AI \u65e9\u62a5 \u00b7 \u7b2c {issue_number} \u671f</div>
  <div class="sub2">\u6211\u4eec\u660e\u5929\u89c1</div>
  <div class="social">
    <span>\u516c\u4f17\u53f7</span><span>B\u7ad9</span><span>\u77e5\u4e4e</span>
  </div>
</div>
</body></html>"""
        return self._save(filename, html)

    def _save(self, filename: str, html: str) -> str:
        filepath = self.output_dir / filename
        filepath.write_text(html, encoding="utf-8")
        return str(filepath)
