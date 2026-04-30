"""视频生成流水线 V3 - CSS 动画帧捕获 + edge_tts + 多转场

升级自 V2，关键变化：
1. 卡片从静态截图升级为 CSS 动画逐帧捕获（AnimatedCardRenderer）
2. TTS 从 WPS Gateway 切换为免费的 edge-tts
3. 去掉 Ken Burns（动画卡片自带动效）
4. 转场类型多样化：fade / slideright / smoothup / radial / wipeleft 轮换
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .broadcast_writer import BroadcastWriter
from .subtitle import generate_srt, build_timeline
from .edge_tts_client import EdgeTTSClient, SegmentAudio, SentenceAudio
from .video_cards import (
    CardGenerator, CARD_WIDTH, CARD_HEIGHT,
    ANIM_DUR_TITLE, ANIM_DUR_ITEM, ANIM_DUR_SUMMARY, ANIM_DUR_END,
)
from .animated_renderer import AnimatedCardRenderer

logger = logging.getLogger(__name__)

# ---------- ffmpeg 路径 ----------

_FFMPEG_CANDIDATES = [
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe",
    r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
    "ffmpeg",
]
_FFPROBE_CANDIDATES = [
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffprobe.exe",
    r"C:\Program Files\FFmpeg\bin\ffprobe.exe",
    "ffprobe",
]


def _find_bin(candidates: list[str]) -> Optional[str]:
    for p in candidates:
        if p in ("ffmpeg", "ffprobe"):
            if shutil.which(p):
                return p
        elif os.path.exists(p):
            return p
    return None


# ---------- 转场类型轮换 ----------

TRANSITIONS = ["fade", "slideright", "smoothup", "radial", "wipeleft", "slideleft", "smoothdown"]


class VideoPipeline:
    """视频生成流水线 V3

    完整流程:
        generate_video()
        +----- 1. BroadcastWriter 生成口播稿
        +----- 2. CardGenerator 生成 HTML 卡片（含 CSS 动画）
        +----- 3. AnimatedCardRenderer 逐帧截图 → MP4 片段
        +----- 4. EdgeTTSClient 句级别合成 → 精确时间轴
        +----- 5. subtitle.generate_srt() 生成字幕
        +----- 6. ffmpeg 组装
                +----- 多转场拼接
                +----- 音频合并
                +----- SRT 字幕烧录
    """

    TRANS_DUR = 0.6

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        ai_client=None,
        prompts: Optional[dict] = None,
        output_dir: str = "data/output/video",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.tts = EdgeTTSClient(
            voice=voice,
            output_dir=str(self.output_dir / "audio"),
        )
        self.cards = CardGenerator(output_dir=str(self.output_dir / "cards"))
        self.renderer = AnimatedCardRenderer(
            output_dir=str(self.output_dir / "cards"),
        )

        self.writer: Optional[BroadcastWriter] = None
        if ai_client and prompts:
            self.writer = BroadcastWriter(
                client=ai_client,
                broadcast_prompt=prompts.get("generate_broadcast_script", ""),
                item_prompt=prompts.get("generate_item_script", ""),
            )

    async def generate_video(
        self,
        issue_number: int,
        date_str: str,
        articles: list[dict],
    ) -> Optional[str]:
        """生成完整视频"""
        work = self.output_dir / f"issue-{issue_number}"
        work.mkdir(parents=True, exist_ok=True)

        n = len(articles)
        logger.info(f"=== 视频生成开始: 第 {issue_number} 期, {n} 条新闻 ===")

        # ---- Step 1: 口播稿 ----
        script = await self._get_broadcast_script(articles, date_str)

        # ---- Step 2: HTML 卡片 ----
        card_slots = self._generate_cards(issue_number, date_str, articles)

        # ---- Step 3: 动画渲染为 MP4 片段 ----
        logger.info("动画渲染 HTML 卡片为视频片段...")
        await self.renderer.init()
        for slot in card_slots:
            mp4 = await self.renderer.render_animated(
                slot["html"],
                anim_dur=slot["anim_dur"],
                hold_dur=slot.get("fallback_dur", 5.0),
            )
            slot["mp4"] = mp4
        await self.renderer.close()

        card_slots = [s for s in card_slots if s.get("mp4")]
        if not card_slots:
            logger.error("所有卡片渲染失败")
            return None

        # ---- Step 4: 句级 TTS ----
        logger.info("Edge TTS 合成...")
        tts_segments = await self._synthesize_all(script, issue_number, n)

        seg_map = {seg.label: seg for seg in tts_segments}
        for slot in card_slots:
            label = slot["label"]
            if label in seg_map:
                slot["segment"] = seg_map[label]
                slot["duration"] = max(seg_map[label].total_duration, 2.0)
            else:
                slot["duration"] = slot.get("fallback_dur", 3.0)
                slot["segment"] = SegmentAudio(
                    label=label,
                    sentences=[SentenceAudio(
                        text="",
                        duration_sec=slot["duration"],
                    )],
                )

        # ---- Step 5: SRT 字幕 ----
        ordered_segs = [s["segment"] for s in card_slots]
        srt_path = str(work / f"issue-{issue_number}.srt")
        generate_srt(ordered_segs, srt_path)

        # ---- Step 6: ffmpeg 组装 ----
        logger.info("ffmpeg 组装视频...")
        output_path = str(self.output_dir / f"issue-{issue_number}.mp4")
        ok = await self._assemble(card_slots, srt_path, output_path, work)

        if ok and Path(output_path).exists():
            self._cleanup(work)
            size_mb = Path(output_path).stat().st_size / 1024 / 1024
            logger.info(f"=== 视频生成完成: {output_path} ({size_mb:.1f}MB) ===")
            return output_path

        logger.error("视频组装失败")
        return None

    # ================================================================
    # 内部方法
    # ================================================================

    async def _get_broadcast_script(
        self, articles: list[dict], date_str: str
    ) -> dict:
        if self.writer:
            try:
                return await self.writer.generate_full_script(articles, date_str)
            except Exception as e:
                logger.warning(f"AI 口播稿生成失败: {e}")

        opening = (
            f"大家好，欢迎收看今天的AI早报。"
            f"今天是{date_str}，"
            f"我们为大家精选了{len(articles)}条AI科技领域的最新资讯。"
        )
        items = []
        for a in articles:
            text = a.get("summary") or a.get("description") or a.get("title", "")
            items.append({"title": a.get("title", ""), "script": text})
        closing = "以上就是今天的全部内容，感谢观看，我们明天再见！"
        return {"opening": opening, "items": items, "closing": closing}

    def _generate_cards(
        self,
        issue_number: int,
        date_str: str,
        articles: list[dict],
    ) -> list[dict]:
        n = len(articles)
        slots: list[dict] = []

        keywords = self._extract_keywords(articles)
        html = self.cards.generate_title_card(
            issue_number, date_str,
            total_articles=n,
            keywords=keywords,
            filename="title.html",
        )
        slots.append({
            "label": "title", "html": html,
            "anim_dur": ANIM_DUR_TITLE,
            "fallback_dur": 4.0,
        })

        for i, article in enumerate(articles):
            desc = article.get("description") or article.get("summary", "")
            if len(desc) > 220:
                desc = desc[:217] + "..."

            html = self.cards.generate_item_card(
                index=i + 1,
                total=n,
                title=article.get("title", ""),
                description=desc,
                image_url=article.get("image_url", ""),
                source=article.get("source", ""),
                category=article.get("category", "AI 相关"),
                filename=f"item-{i + 1:02d}.html",
            )
            slots.append({
                "label": f"item-{i + 1:02d}",
                "html": html,
                "anim_dur": ANIM_DUR_ITEM,
                "fallback_dur": 8.0,
            })

        keywords = self._extract_keywords(articles)
        if keywords:
            html = self.cards.generate_summary_card(
                date_str, keywords,
                total_articles=n,
                filename="summary.html",
            )
            slots.append({
                "label": "summary", "html": html,
                "anim_dur": ANIM_DUR_SUMMARY,
                "fallback_dur": 4.0,
            })

        html = self.cards.generate_end_card(issue_number, filename="end.html")
        slots.append({
            "label": "end", "html": html,
            "anim_dur": ANIM_DUR_END,
            "fallback_dur": 4.0,
        })

        return slots

    async def _synthesize_all(
        self,
        script: dict,
        issue_number: int,
        total_items: int,
    ) -> list[SegmentAudio]:
        prefix = f"i{issue_number}"
        segments: list[SegmentAudio] = []

        seg = await self.tts.synthesize_sentences(
            script["opening"], label="title", prefix=prefix
        )
        segments.append(seg)

        items = script.get("items", [])
        for i, item in enumerate(items):
            text = item.get("script") or item.get("title", "")
            label = f"item-{i + 1:02d}"
            seg = await self.tts.synthesize_sentences(
                text, label=label, prefix=prefix
            )
            segments.append(seg)

        seg = await self.tts.synthesize_sentences(
            script["closing"], label="end", prefix=prefix
        )
        segments.append(seg)

        return segments

    async def _assemble(
        self,
        slots: list[dict],
        srt_path: str,
        output_path: str,
        work_dir: Path,
    ) -> bool:
        ffmpeg = _find_bin(_FFMPEG_CANDIDATES)
        if not ffmpeg:
            logger.error("ffmpeg 未安装")
            return False

        try:
            seg_files = self._collect_segments(slots)
            if not seg_files:
                return False

            video_only = str(work_dir / "video_only.mp4")
            ok = self._concat_segments(ffmpeg, seg_files, video_only, work_dir)
            if not ok:
                return False

            audio_only = str(work_dir / "audio_merged.mp3")
            self._merge_audio(ffmpeg, slots, audio_only, work_dir)

            return self._final_merge(
                ffmpeg, video_only, audio_only, srt_path, output_path
            )

        except Exception as e:
            logger.error(f"组装异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _collect_segments(self, slots: list[dict]) -> list[tuple[str, float]]:
        """收集所有已渲染的 MP4 片段及其时长"""
        results: list[tuple[str, float]] = []
        ffprobe = _find_bin(_FFPROBE_CANDIDATES)

        for slot in slots:
            mp4 = slot.get("mp4")
            if not mp4 or not Path(mp4).exists():
                continue

            dur = slot.get("duration", 5.0)
            if ffprobe:
                try:
                    r = subprocess.run(
                        [ffprobe, "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", mp4],
                        capture_output=True, text=True, timeout=10,
                    )
                    dur = float(r.stdout.strip())
                except (ValueError, subprocess.TimeoutExpired):
                    pass

            results.append((mp4, dur))
            logger.info(f"  片段 {slot['label']}: {dur:.1f}s")

        return results

    def _concat_segments(
        self,
        ffmpeg: str,
        seg_files: list[tuple[str, float]],
        output: str,
        work_dir: Path,
    ) -> bool:
        """使用 xfade 多转场拼接视频片段"""
        if len(seg_files) <= 1:
            if seg_files:
                shutil.copy(seg_files[0][0], output)
            return bool(seg_files)

        files = [f for f, _ in seg_files]
        durs = [d for _, d in seg_files]

        n = len(files)
        trans = self.TRANS_DUR
        parts = []
        cum = durs[0]

        for i in range(n - 1):
            offset = max(0, cum - trans)

            trans_type = TRANSITIONS[i % len(TRANSITIONS)]

            prev = "v01" if i <= 1 else f"v{i-1}{i}"
            src_left = "[0:v]" if i == 0 else f"[{prev}]"
            out_label = f"v{i}{i+1}"
            parts.append(
                f"{src_left}[{i+1}:v]xfade="
                f"transition={trans_type}:"
                f"duration={trans}:offset={offset:.3f}[{out_label}]"
            )
            cum += durs[i + 1] - trans

        final_label = f"v{n-2}{n-1}" if n > 2 else "v01"
        parts.append(f"[{final_label}]format=yuv420p[outv]")
        fc = ";".join(parts)

        cmd = [ffmpeg, "-y"]
        for f in files:
            cmd.extend(["-i", f])
        cmd.extend([
            "-filter_complex", fc,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-preset", "fast",
            "-crf", "20",
            "-movflags", "+faststart",
            output,
        ])

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            logger.warning(f"xfade 拼接失败，回退简单拼接: {r.stderr[-400:]}")
            return self._simple_concat(ffmpeg, files, output, work_dir)
        return True

    def _simple_concat(
        self, ffmpeg: str, files: list[str], output: str, work_dir: Path
    ) -> bool:
        lst = work_dir / "concat.txt"
        lst.write_text(
            "\n".join(f"file '{f.replace(chr(92), '/')}'" for f in files),
            encoding="utf-8",
        )
        r = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c", "copy", output],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            logger.error(f"简单拼接失败: {r.stderr[-200:]}")
            return False
        return True

    def _merge_audio(
        self,
        ffmpeg: str,
        slots: list[dict],
        output: str,
        work_dir: Path,
    ):
        audio_files: list[str] = []
        for slot in slots:
            seg: Optional[SegmentAudio] = slot.get("segment")
            if seg:
                for sa in seg.sentences:
                    if sa.path and Path(sa.path).exists():
                        audio_files.append(sa.path)

        if not audio_files:
            logger.warning("无可用音频文件")
            return

        lst = work_dir / "audio_list.txt"
        lst.write_text(
            "\n".join(f"file '{f.replace(chr(92), '/')}'" for f in audio_files),
            encoding="utf-8",
        )
        r = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c", "copy", output],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            logger.error(f"音频合并失败: {r.stderr[-200:]}")

    def _final_merge(
        self,
        ffmpeg: str,
        video: str,
        audio: str,
        srt: str,
        output: str,
    ) -> bool:
        has_audio = Path(audio).exists() and Path(audio).stat().st_size > 0
        has_srt = Path(srt).exists() and Path(srt).stat().st_size > 0

        srt_esc = srt.replace("\\", "/").replace(":", "\\:")

        sub_style = (
            "FontName=Microsoft YaHei,"
            "FontSize=22,"
            "PrimaryColour=&Hffffff,"
            "OutlineColour=&H40000000,"
            "BackColour=&H80000000,"
            "Outline=2,"
            "Shadow=0,"
            "MarginV=50,"
            "Alignment=2,"
            "BorderStyle=4"
        )

        vf_parts = []
        if has_srt:
            vf_parts.append(
                f"subtitles='{srt_esc}':force_style='{sub_style}'"
            )

        cmd = [ffmpeg, "-y", "-i", video]
        if has_audio:
            cmd.extend(["-i", audio])

        if vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        cmd.extend(["-c:v", "libx264", "-crf", "20"])

        if has_audio:
            cmd.extend([
                "-c:a", "aac", "-b:a", "128k",
                "-map", "0:v:0", "-map", "1:a:0",
            ])

        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
            output,
        ])

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            logger.warning(f"字幕合并失败，尝试无字幕版: {r.stderr[-300:]}")
            return self._merge_no_subtitle(ffmpeg, video, audio, output)
        return True

    def _merge_no_subtitle(
        self, ffmpeg: str, video: str, audio: str, output: str
    ) -> bool:
        has_audio = Path(audio).exists() and Path(audio).stat().st_size > 0
        cmd = [ffmpeg, "-y", "-i", video]
        if has_audio:
            cmd.extend(["-i", audio, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "128k", "-shortest"])
        else:
            cmd.extend(["-c", "copy"])
        cmd.append(output)

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            logger.error(f"无字幕合并也失败: {r.stderr[-200:]}")
            if Path(video).exists():
                shutil.copy(video, output)
            return Path(output).exists()
        return True

    @staticmethod
    def _extract_keywords(articles: list[dict]) -> list[str]:
        kw_set: list[str] = []
        seen = set()
        for a in articles:
            try:
                kws = json.loads(a.get("keywords", "[]"))
            except (json.JSONDecodeError, TypeError):
                kws = []
            for k in kws:
                if k not in seen:
                    seen.add(k)
                    kw_set.append(k)
        return kw_set[:8]

    @staticmethod
    def _cleanup(work_dir: Path):
        for pattern in ["video_only.mp4", "audio_merged.mp3",
                        "concat.txt", "audio_list.txt"]:
            for f in work_dir.glob(pattern):
                try:
                    f.unlink()
                except OSError:
                    pass
