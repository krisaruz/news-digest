"""TTS 客户端 - 支持句级别合成和精确时间轴"""
from __future__ import annotations

import asyncio
import httpx
import logging
import re
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


class TTSClient:
    """WPS TTS Gateway 客户端 - 支持句级别合成"""

    def __init__(self, config: dict, output_dir: str = "data/output/audio"):
        self.url = config["url"]
        self.auth = config["auth"]
        self.model = config.get("model", "speech-01-pro")
        self.provider = config.get("provider", "minimax")
        self.voice_id = config.get("voice_id", "female-shaonv")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(3)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth['token']}",
            "AI-Gateway-Uid": str(self.auth["uid"]),
            "AI-Gateway-Product-Name": self.auth["product_name"],
            "AI-Gateway-Intention-Code": self.auth["intention_code"],
            "Content-Type": "application/json",
        }

    def _payload(self, text: str) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "text": text,
            "voice_id": self.voice_id,
            "base_tts_arguments": {
                "speed": 1.0,
                "vol": 1.2,
                "pitch": 0,
                "sample_rate": 24000,
            },
            "extended_tts_arguments": {
                "minimax_speech-01-pro": {
                    "timber_weights": [
                        {"voice_id": self.voice_id, "weight": 1}
                    ],
                    "bitrate": 128000,
                }
            },
        }

    async def synthesize(self, text: str, filename: str) -> Optional[dict]:
        """合成语音，返回 {path, duration_sec, subtitle_url, word_count}"""
        if len(text.strip()) < 3:
            return None

        filepath = self.output_dir / filename

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        self.url,
                        headers=self._headers(),
                        json=self._payload(text),
                    )

                    if resp.status_code != 200:
                        logger.error(f"TTS 请求失败: {resp.status_code}")
                        return None

                    result = resp.json()
                    if result.get("code") != "Success":
                        logger.error(f"TTS 失败: {result.get('message')}")
                        return None

                    audio_url = result.get("audio_url", "")
                    extra = result.get("extended_resp_fields", {}).get("extra_info", {})
                    subtitle_url = extra.get("subtitle_file", "")

                    if audio_url:
                        async with httpx.AsyncClient(timeout=30) as dl:
                            audio_resp = await dl.get(audio_url)
                            if audio_resp.status_code == 200:
                                filepath.write_bytes(audio_resp.content)

                    audio_length = extra.get("audio_length", 0)
                    sample_rate = extra.get("audio_sample_rate", 24000)
                    duration_sec = audio_length / sample_rate if sample_rate > 0 else 0

                    return {
                        "path": str(filepath),
                        "duration_sec": round(duration_sec, 2),
                        "subtitle_url": subtitle_url,
                        "word_count": extra.get("word_count", 0),
                    }

            except Exception as e:
                logger.error(f"TTS 合成失败: {e}")
                return None

    async def synthesize_sentences(
        self,
        text: str,
        label: str,
        prefix: str = "seg",
    ) -> SegmentAudio:
        """按句子拆分文本并逐句合成，返回带精确时间轴的结果

        逐句合成方案的核心：每个短句独立合成，以精确计算时长。
        """
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
                sa.subtitle_url = result.get("subtitle_url", "")
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
        """批量合成多个片段（每个片段内部按句子拆分）"""
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
        """根据字数估算朗读时长（不调用 API 时使用）"""
        return max(1.5, len(text) / chars_per_sec)
