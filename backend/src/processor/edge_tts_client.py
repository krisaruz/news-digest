"""Edge TTS 客户端 - 基于 edge-tts 的免费语音合成，支持句级别合成和精确时间轴"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SentenceAudio:
    """单句合成结果"""
    text: str
    path: str = ""
    duration_sec: float = 0.0
    word_count: int = 0
    subtitle_url: str = ""


@dataclass
class SegmentAudio:
    """一个片段（如一条新闻）的合成结果"""
    label: str
    sentences: list[SentenceAudio] = field(default_factory=list)
    combined_path: str = ""

    @property
    def total_duration(self) -> float:
        return sum(s.duration_sec for s in self.sentences)


_FFPROBE_CANDIDATES = [
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffprobe.exe",
    r"C:\Program Files\FFmpeg\bin\ffprobe.exe",
    "ffprobe",
]


def _find_ffprobe() -> Optional[str]:
    for p in _FFPROBE_CANDIDATES:
        if p == "ffprobe":
            if shutil.which(p):
                return p
        elif os.path.exists(p):
            return p
    return None


def _get_audio_duration(filepath: str) -> float:
    """用 ffprobe 获取音频文件的实际时长"""
    probe = _find_ffprobe()
    if not probe:
        return 0.0
    try:
        r = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", filepath],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return 0.0


class EdgeTTSClient:
    """基于 edge-tts 的语音合成客户端

    免费、无需 API key、支持多种中文声音：
    - zh-CN-XiaoxiaoNeural (女声，推荐)
    - zh-CN-YunxiNeural (男声)
    - zh-CN-XiaoyiNeural (女声，温柔)
    """

    DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        volume: str = "+0%",
        output_dir: str = "data/output/audio",
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(5)

    async def synthesize(self, text: str, filename: str) -> Optional[dict]:
        """合成单段语音，返回 {path, duration_sec, word_count}"""
        if len(text.strip()) < 2:
            return None

        import edge_tts

        filepath = self.output_dir / filename

        async with self._semaphore:
            try:
                communicate = edge_tts.Communicate(
                    text, self.voice, rate=self.rate, volume=self.volume,
                )
                await communicate.save(str(filepath))

                duration = _get_audio_duration(str(filepath))
                if duration <= 0:
                    duration = self.estimate_duration(text)

                return {
                    "path": str(filepath),
                    "duration_sec": round(duration, 2),
                    "word_count": len(text),
                }
            except Exception as e:
                logger.error(f"Edge TTS 合成失败: {e}")
                return None

    async def synthesize_sentences(
        self,
        text: str,
        label: str,
        prefix: str = "seg",
    ) -> SegmentAudio:
        """按句子拆分文本并逐句合成，返回带精确时间轴的结果"""
        sentences = self.split_sentences(text)
        segment = SegmentAudio(label=label)

        for i, sentence in enumerate(sentences):
            filename = f"{prefix}-{label}-s{i:03d}.mp3"
            result = await self.synthesize(sentence, filename)

            sa = SentenceAudio(text=sentence)
            if result:
                sa.path = result["path"]
                sa.duration_sec = result["duration_sec"]
                sa.word_count = result["word_count"]
            else:
                sa.duration_sec = max(1.5, len(sentence) * 0.18)

            segment.sentences.append(sa)

        logger.info(
            f"  [{label}] {len(sentences)} 句, "
            f"总时长 {segment.total_duration:.1f}s"
        )
        return segment

    async def synthesize_segments(
        self,
        segments: list[tuple[str, str]],
        prefix: str = "seg",
    ) -> list[SegmentAudio]:
        """批量合成多个片段"""
        results = []
        for label, text in segments:
            seg = await self.synthesize_sentences(text, label, prefix)
            results.append(seg)
        return results

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """按标点符号拆分文本为句子，合并过短的句子"""
        parts = re.split(r'[。！？；\n]+', text)
        sentences = [p.strip() for p in parts if p.strip()]

        merged: list[str] = []
        buf = ""
        for s in sentences:
            if buf and len(buf) < 15:
                buf += "，" + s
            elif buf:
                merged.append(buf)
                buf = s
            else:
                buf = s
        if buf:
            merged.append(buf)

        return merged

    @staticmethod
    def estimate_duration(text: str, chars_per_sec: float = 5.5) -> float:
        """根据字数估算朗读时长"""
        return max(1.5, len(text) / chars_per_sec)
