"""SRT 字幕生成器 - 根据句级别时间轴生成 SRT 文件"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .edge_tts_client import SegmentAudio

logger = logging.getLogger(__name__)


def _fmt_ts(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(
    segments: list[SegmentAudio],
    output_path: str,
    gap: float = 0.1,
) -> str:
    """根据 SegmentAudio 列表生成 SRT 字幕文件

    Args:
        segments: 按顺序排列的片段列表（标题、逐条新闻、结尾等）
        output_path: SRT 文件保存路径
        gap: 字幕之间的间隔（秒）
    """
    lines: list[str] = []
    idx = 1
    cursor = 0.0

    for seg in segments:
        for sa in seg.sentences:
            if not sa.text.strip():
                continue

            start = cursor
            end = cursor + sa.duration_sec

            lines.append(str(idx))
            lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")

            text = _wrap_text(sa.text, max_chars=28)
            lines.append(text)
            lines.append("")

            cursor = end + gap
            idx += 1

    content = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"SRT 字幕已生成: {output_path} ({idx - 1} 条)")
    return output_path


def _wrap_text(text: str, max_chars: int = 30) -> str:
    """中文字幕自动折行，不拆断英文单词

    优先级:
    1. 在中文标点处折行
    2. 在空格处折行（英文单词边界）
    3. 在中文字与中文字之间折行
    绝不在英文单词中间折行。
    """
    if len(text) <= max_chars:
        return text

    mid = len(text) // 2
    search_range = min(12, mid)

    breakable = set("，、；：。！？ ,;:!? ")

    for offset in range(search_range):
        for pos in [mid + offset, mid - offset]:
            if 0 < pos < len(text) and text[pos] in breakable:
                return text[:pos + 1].rstrip() + "\n" + text[pos + 1:].lstrip()

    for offset in range(search_range):
        for pos in [mid + offset, mid - offset]:
            if 0 < pos < len(text):
                prev_ch = text[pos - 1]
                curr_ch = text[pos]
                prev_is_ascii = prev_ch.isascii() and prev_ch.isalpha()
                curr_is_ascii = curr_ch.isascii() and curr_ch.isalpha()
                if not (prev_is_ascii and curr_is_ascii):
                    return text[:pos] + "\n" + text[pos:]

    return text


def build_timeline(
    segments: list[SegmentAudio],
    transition_dur: float = 0.0,
) -> list[dict]:
    """构建完整视频时间轴

    返回:
        [{"label": str, "start": float, "end": float, "duration": float}, ...]
    """
    timeline: list[dict] = []
    cursor = 0.0

    for seg in segments:
        dur = seg.total_duration if seg.total_duration > 0 else 3.0
        entry = {
            "label": seg.label,
            "start": cursor,
            "end": cursor + dur,
            "duration": dur,
        }
        timeline.append(entry)
        cursor += dur + transition_dur

    return timeline
