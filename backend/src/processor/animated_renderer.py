"""动画卡片渲染器 - Playwright 逐帧截图 + ffmpeg 合成视频片段

核心流程：
1. Playwright 打开 HTML 卡片（含 CSS 动画，animation-play-state: paused）
2. 循环设置 CSS 变量 --t (0~1) 推进动画进度
3. 每帧截图为 PNG
4. ffmpeg 将帧序列合成为 H.264 MP4 片段

这样每张卡片就是一个带动画的视频片段，而非静态图片。
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CARD_WIDTH = 1920
CARD_HEIGHT = 1080
DEFAULT_FPS = 30

_FFMPEG_CANDIDATES = [
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe",
    r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
    "ffmpeg",
]


def _find_ffmpeg() -> Optional[str]:
    for p in _FFMPEG_CANDIDATES:
        if p == "ffmpeg":
            if shutil.which(p):
                return p
        elif os.path.exists(p):
            return p
    return None


class AnimatedCardRenderer:
    """Playwright + ffmpeg 动画卡片渲染器

    用法：
        renderer = AnimatedCardRenderer(output_dir="data/output/cards")
        await renderer.init()
        mp4_path = await renderer.render_animated("title.html", anim_dur=2.0, hold_dur=3.0)
        mp4_path = await renderer.render_animated("item-01.html", anim_dur=1.5, hold_dur=5.0)
        await renderer.close()
    """

    def __init__(
        self,
        output_dir: str = "data/output/cards",
        fps: int = DEFAULT_FPS,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self._browser = None
        self._playwright = None

    async def init(self):
        """启动 Playwright 浏览器"""
        if self._browser:
            return

        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-size={CARD_WIDTH},{CARD_HEIGHT}",
                "--force-device-scale-factor=1",
            ],
        )
        logger.info("Playwright 浏览器已启动")

    async def render_animated(
        self,
        html_path: str,
        anim_dur: float = 1.5,
        hold_dur: float = 5.0,
        output_mp4: Optional[str] = None,
    ) -> Optional[str]:
        """渲染一张动画卡片为 MP4 视频片段。

        Args:
            html_path: HTML 卡片文件路径
            anim_dur: 入场动画时长（秒），动画从 t=0 播放到 t=1
            hold_dur: 动画完成后静态保持时长（秒），供口播阶段使用
            output_mp4: 输出 MP4 路径，默认自动生成

        Returns:
            MP4 文件路径，失败返回 None
        """
        if not self._browser:
            await self.init()

        stem = Path(html_path).stem
        if not output_mp4:
            output_mp4 = str(self.output_dir / f"{stem}.mp4")

        frames_dir = self.output_dir / f"_frames_{stem}"
        frames_dir.mkdir(parents=True, exist_ok=True)

        try:
            anim_frames = int(anim_dur * self.fps)
            hold_frames = int(hold_dur * self.fps)
            total_frames = anim_frames + hold_frames

            page = await self._browser.new_page(
                viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
            )

            abs_path = os.path.abspath(html_path)
            file_url = "file:///" + abs_path.replace("\\", "/")
            await page.goto(file_url, wait_until="networkidle")
            await page.wait_for_timeout(200)

            logger.info(
                f"  [{stem}] 截帧: {anim_frames}帧动画 + {hold_frames}帧保持 = {total_frames}帧"
            )

            for i in range(total_frames):
                if i < anim_frames:
                    t = i / max(anim_frames - 1, 1)
                else:
                    t = 1.0

                await page.evaluate(
                    f"document.documentElement.style.setProperty('--t', '{t}')"
                )

                frame_path = str(frames_dir / f"frame-{i:05d}.png")
                await page.screenshot(path=frame_path)

            await page.close()

            ok = self._frames_to_mp4(frames_dir, output_mp4)

            self._cleanup_frames(frames_dir)

            if ok:
                logger.info(f"  [{stem}] -> {Path(output_mp4).name}")
                return output_mp4
            return None

        except Exception as e:
            logger.error(f"动画渲染失败 {stem}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._cleanup_frames(frames_dir)
            return None

    async def render_static(
        self, html_path: str, output_png: Optional[str] = None
    ) -> Optional[str]:
        """静态截图（兼容模式），设 --t=1 后截一张"""
        if not self._browser:
            await self.init()

        if not output_png:
            output_png = str(self.output_dir / (Path(html_path).stem + ".png"))

        try:
            page = await self._browser.new_page(
                viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
            )
            abs_path = os.path.abspath(html_path)
            await page.goto("file:///" + abs_path.replace("\\", "/"), wait_until="networkidle")
            await page.wait_for_timeout(300)
            await page.evaluate("document.documentElement.style.setProperty('--t', '1')")
            await page.wait_for_timeout(100)
            await page.screenshot(path=output_png)
            await page.close()
            return output_png
        except Exception as e:
            logger.error(f"静态截图失败 {html_path}: {e}")
            return None

    def _frames_to_mp4(self, frames_dir: Path, output_mp4: str) -> bool:
        """用 ffmpeg 将帧序列合成为 MP4"""
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            logger.error("ffmpeg 未找到")
            return False

        pattern = str(frames_dir / "frame-%05d.png")
        cmd = [
            ffmpeg, "-y",
            "-framerate", str(self.fps),
            "-i", pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-preset", "fast",
            "-crf", "20",
            "-movflags", "+faststart",
            output_mp4,
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            logger.error(f"帧合成失败: {r.stderr[-400:]}")
            return False
        return True

    @staticmethod
    def _cleanup_frames(frames_dir: Path):
        """清理帧图片目录"""
        try:
            if frames_dir.exists():
                shutil.rmtree(frames_dir)
        except OSError as e:
            logger.warning(f"清理帧目录失败: {e}")

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
