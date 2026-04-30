"""视频模块端到端测试

分三级测试：
  Level 1: 纯 Python 逻辑（不依赖外部服务）
  Level 2: HTML 卡片生成 + 渲染（需要 Chrome）
  Level 3: 完整流水线（需要 TTS API + ffmpeg）

运行方式:
  cd backend
  python test_video.py           # 只跑 Level 1
  python test_video.py --level 2 # 跑到 Level 2
  python test_video.py --level 3 # 跑完整流水线
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

SAMPLE_ARTICLES = [
    {
        "id": "test-001",
        "title": "OpenAI 发布 GPT-5：多模态推理能力大幅提升",
        "summary": "OpenAI 正式发布 GPT-5，支持原生图像、音频和视频理解，推理速度提升 3 倍，在多项基准测试中刷新纪录。",
        "description": "OpenAI 正式发布了备受期待的 GPT-5 模型。这次更新带来了原生多模态能力，可以直接理解图像、音频和视频输入。在 MMLU-Pro 测试中得分 92.1%，较 GPT-4o 提升 8 个百分点。推理速度也提升了 3 倍，API 价格保持不变。",
        "url": "https://example.com/gpt5",
        "source": "TechCrunch AI",
        "category": "AI 相关",
        "keywords": '["GPT-5", "OpenAI", "多模态"]',
        "score": 0.95,
        "image_url": "",
    },
    {
        "id": "test-002",
        "title": "Anthropic Claude 4 开放 API：编程能力超越人类基准",
        "summary": "Anthropic 发布 Claude 4，在 SWE-bench 上首次超过人类工程师平均水平，支持 100 万 token 上下文窗口。",
        "description": "Anthropic 今日发布 Claude 4 模型。在 SWE-bench Verified 测试中，Claude 4 得分 78.2%，首次超过人类软件工程师的平均水平。新模型还将上下文窗口扩展到 100 万 token，可以处理整个代码库。",
        "url": "https://example.com/claude4",
        "source": "The Verge",
        "category": "AI 相关",
        "keywords": '["Claude 4", "Anthropic", "编程"]',
        "score": 0.92,
        "image_url": "",
    },
    {
        "id": "test-003",
        "title": "DeepSeek V4 开源：千亿参数 MoE 模型完全免费",
        "summary": "DeepSeek 开源 V4 模型，2000 亿参数 MoE 架构，MIT 许可证，性能对标 GPT-4o。",
        "description": "中国 AI 创业公司 DeepSeek 发布并完全开源了 V4 模型。该模型采用 MoE 架构，总参数量 2000 亿，激活参数 370 亿，在中英文任务上性能对标 GPT-4o。采用 MIT 许可证，可自由商用。",
        "url": "https://example.com/deepseek-v4",
        "source": "Hacker News AI",
        "category": "AI 相关",
        "keywords": '["DeepSeek", "开源", "MoE"]',
        "score": 0.90,
        "image_url": "",
    },
    {
        "id": "test-004",
        "title": "Cursor 完成 30 亿美元融资，估值突破 200 亿",
        "summary": "AI 编程工具 Cursor 完成新一轮 30 亿美元融资，估值达到 200 亿美元，成为 AI 编程赛道最大独角兽。",
        "description": "AI 编程工具 Cursor 宣布完成 30 亿美元 D 轮融资，投后估值 200 亿美元。Cursor 目前拥有超过 500 万开发者用户，ARR 突破 10 亿美元。本轮融资由 a16z 领投，将用于扩大团队和提升模型能力。",
        "url": "https://example.com/cursor-funding",
        "source": "TechCrunch AI",
        "category": "科技动态",
        "keywords": '["Cursor", "融资", "AI编程"]',
        "score": 0.85,
        "image_url": "",
    },
    {
        "id": "test-005",
        "title": "Meta 发布 Llama 4：首个原生多模态开源大模型",
        "summary": "Meta 开源 Llama 4 系列模型，包含 Scout、Maverick 和 Behemoth 三个版本，首次原生支持多模态。",
        "description": "Meta 正式发布 Llama 4 系列。Scout 版本 17B 参数，适合边缘部署；Maverick 版本 400B MoE，性能对标 GPT-4o；Behemoth 版本 2T 参数，训练中。全系列原生支持文本、图像和视频输入。",
        "url": "https://example.com/llama4",
        "source": "Reddit LocalLLaMA",
        "category": "AI 相关",
        "keywords": '["Llama 4", "Meta", "开源"]',
        "score": 0.88,
        "image_url": "",
    },
]


def _ok(msg: str):
    print(f"  [PASS] {msg}")


def _fail(msg: str):
    print(f"  [FAIL] {msg}")


def _info(msg: str):
    print(f"  [INFO] {msg}")


# ============================================================
# Level 1: 纯 Python 逻辑测试
# ============================================================

def test_sentence_split():
    """测试句子拆分"""
    from processor.tts_client import TTSClient
    text = "今天AI领域有三大新闻。第一条是OpenAI发布了GPT-5！第二条是DeepSeek开源V4；第三条是Cursor融资30亿"
    sentences = TTSClient.split_sentences(text)
    assert len(sentences) >= 3, f"期望 >= 3 句, 实际 {len(sentences)}"
    assert "GPT-5" in " ".join(sentences), "句子应包含 GPT-5"
    _ok(f"句子拆分: {len(sentences)} 句 → {sentences}")


def test_duration_estimate():
    """测试时长估算"""
    from processor.tts_client import TTSClient
    dur = TTSClient.estimate_duration("这是一段测试文字，大概有二十个字左右。")
    assert 2.0 < dur < 8.0, f"时长不合理: {dur}s"
    _ok(f"时长估算: {dur:.1f}s")


def test_srt_generation():
    """测试 SRT 字幕生成"""
    from processor.tts_client import SegmentAudio, SentenceAudio
    from processor.subtitle import generate_srt

    segs = [
        SegmentAudio(
            label="title",
            sentences=[
                SentenceAudio(text="大家好，欢迎收看今天的AI早报", duration_sec=3.5),
            ],
        ),
        SegmentAudio(
            label="item-01",
            sentences=[
                SentenceAudio(text="第一条新闻，OpenAI发布了GPT-5", duration_sec=3.0),
                SentenceAudio(text="这次更新带来了原生多模态能力", duration_sec=2.5),
            ],
        ),
        SegmentAudio(
            label="end",
            sentences=[
                SentenceAudio(text="感谢观看，我们明天再见", duration_sec=2.0),
            ],
        ),
    ]

    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
        tmp_path = f.name

    try:
        generate_srt(segs, tmp_path)
        content = Path(tmp_path).read_text(encoding="utf-8")
        assert "00:00:00,000" in content, "SRT 应以 00:00:00 开头"
        assert "GPT-5" in content, "SRT 应包含新闻内容"
        lines = [l for l in content.split("\n") if "-->" in l]
        assert len(lines) == 4, f"期望 4 条字幕, 实际 {len(lines)}"
        _ok(f"SRT 生成: {len(lines)} 条字幕")
    finally:
        os.unlink(tmp_path)


def test_timeline_build():
    """测试时间轴构建"""
    from processor.tts_client import SegmentAudio, SentenceAudio
    from processor.subtitle import build_timeline

    segs = [
        SegmentAudio(label="title", sentences=[
            SentenceAudio(text="开场", duration_sec=3.0)
        ]),
        SegmentAudio(label="item-01", sentences=[
            SentenceAudio(text="句1", duration_sec=2.0),
            SentenceAudio(text="句2", duration_sec=3.0),
        ]),
        SegmentAudio(label="end", sentences=[
            SentenceAudio(text="结尾", duration_sec=2.0)
        ]),
    ]

    tl = build_timeline(segs, transition_dur=0.5)
    assert len(tl) == 3
    assert tl[0]["start"] == 0.0
    assert tl[0]["duration"] == 3.0
    assert tl[1]["start"] == 3.5
    assert tl[1]["duration"] == 5.0
    _ok(f"时间轴: {json.dumps(tl, indent=2)}")


def test_card_generator():
    """测试 HTML 卡片生成"""
    from processor.video_cards import CardGenerator

    with tempfile.TemporaryDirectory() as tmp:
        gen = CardGenerator(output_dir=tmp)

        title_html = gen.generate_title_card(
            issue_number=99, date_str="2026年4月19日",
            total_articles=5, filename="title.html",
        )
        assert Path(title_html).exists(), "标题卡片文件不存在"
        content = Path(title_html).read_text(encoding="utf-8")
        assert "1920" in content, "宽度应为 1920"
        assert "第 99 期" in content
        assert '<style>' in content and '</style>' in content
        style_block = content[content.index('<style>'):content.index('</style>')]
        assert '<div' not in style_block, "style 块内不应有 HTML 元素"
        _ok("标题卡片 HTML 合法")

        item_html = gen.generate_item_card(
            index=1, total=5,
            title="GPT-5 发布", description="测试描述",
            source="Test", category="AI 相关",
            filename="item-01.html",
        )
        content = Path(item_html).read_text(encoding="utf-8")
        assert "1 / 5" in content, "进度条文字应在 body 中"
        style_block = content[content.index('<style>'):content.index('</style>')]
        assert 'prog-fill' not in style_block or 'class=' not in style_block, \
            "进度条 HTML 不应在 style 块内"
        _ok("新闻卡片 HTML（进度条）合法")

        summary_html = gen.generate_summary_card(
            date_str="2026年4月19日",
            topics=["GPT-5", "Claude 4", "DeepSeek V4"],
            filename="summary.html",
        )
        assert Path(summary_html).exists()
        _ok("关键词卡片 HTML 合法")

        cat_html = gen.generate_category_card(
            category="AI 相关", article_count=3,
            filename="category.html",
        )
        assert Path(cat_html).exists()
        _ok("分类过渡卡片 HTML 合法")

        end_html = gen.generate_end_card(issue_number=99, filename="end.html")
        assert Path(end_html).exists()
        _ok("结尾卡片 HTML 合法")


def test_broadcast_script_fallback():
    """测试口播稿回退生成（不需要 AI）"""

    async def _run():
        from processor.broadcast_writer import BroadcastWriter

        writer = BroadcastWriter(
            client=None,
            broadcast_prompt="",
            item_prompt="",
        )
        script = await writer._generate_fallback(
            SAMPLE_ARTICLES, "2026年4月19日"
        )
        assert "opening" in script
        assert "items" in script
        assert "closing" in script
        assert len(script["items"]) == len(SAMPLE_ARTICLES)
        for item in script["items"]:
            assert "title" in item
            assert "script" in item
        _ok(f"口播稿回退: opening={len(script['opening'])}字, "
            f"{len(script['items'])} 条, closing={len(script['closing'])}字")

    asyncio.run(_run())


def run_level1():
    print("\n=== Level 1: Python 逻辑测试 ===\n")
    tests = [
        test_sentence_split,
        test_duration_estimate,
        test_srt_generation,
        test_timeline_build,
        test_card_generator,
        test_broadcast_script_fallback,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            _fail(f"{t.__name__}: {e}")
            failed += 1
    print(f"\n  Level 1 结果: {passed} 通过, {failed} 失败")
    return failed == 0


# ============================================================
# Level 2: HTML 渲染测试（需要 Chrome）
# ============================================================

def run_level2():
    print("\n=== Level 2: HTML 卡片渲染测试 ===\n")

    async def _run():
        from processor.video_cards import CardGenerator, CardRenderer

        with tempfile.TemporaryDirectory() as tmp:
            gen = CardGenerator(output_dir=tmp)
            renderer = CardRenderer(output_dir=tmp)

            title_html = gen.generate_title_card(
                issue_number=99, date_str="2026年4月19日",
                total_articles=5,
            )

            png = await renderer.render(title_html)
            renderer.close()

            if png and Path(png).exists():
                size = Path(png).stat().st_size
                _ok(f"标题卡片渲染成功: {size / 1024:.0f} KB")

                items = []
                for i, article in enumerate(SAMPLE_ARTICLES):
                    html = gen.generate_item_card(
                        index=i + 1, total=len(SAMPLE_ARTICLES),
                        title=article["title"],
                        description=article["description"],
                        source=article["source"],
                        category=article["category"],
                    )
                    items.append(html)
                _ok(f"生成 {len(items)} 张新闻卡片 HTML")

                renderer2 = CardRenderer(output_dir=tmp)
                pngs = await renderer2.render_all(items)
                renderer2.close()
                _ok(f"渲染 {len(pngs)} 张 PNG")
                return True
            else:
                _fail("渲染失败（可能 Chrome 未安装）")
                return False

    return asyncio.run(_run())


# ============================================================
# Level 3: 完整流水线测试（需要 TTS + ffmpeg）
# ============================================================

def run_level3():
    print("\n=== Level 3: 完整视频流水线测试 ===\n")

    if not shutil.which("ffmpeg") and not os.path.exists(
        r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
    ):
        _fail("ffmpeg 未找到，跳过 Level 3")
        return False

    import yaml
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        _fail("config.yaml 不存在")
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tts_config = config.get("tts_gateway")
    if not tts_config:
        _fail("tts_gateway 未配置")
        return False

    async def _run():
        from processor.video_pipeline import VideoPipeline

        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VideoPipeline(
                tts_config=tts_config,
                output_dir=tmp,
            )

            video_path = await pipeline.generate_video(
                issue_number=99,
                date_str="2026年4月19日",
                articles=SAMPLE_ARTICLES,
            )

            if video_path and Path(video_path).exists():
                size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                _ok(f"视频生成成功: {size_mb:.1f} MB → {video_path}")

                srt_files = list(Path(tmp).rglob("*.srt"))
                if srt_files:
                    _ok(f"SRT 字幕已生成: {srt_files[0].name}")

                return True
            else:
                _fail("视频生成失败")
                return False

    return asyncio.run(_run())


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="视频模块测试")
    parser.add_argument(
        "--level", type=int, default=1, choices=[1, 2, 3],
        help="测试级别: 1=Python逻辑, 2=+HTML渲染, 3=+完整流水线"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  News Digest 视频模块测试")
    print("=" * 60)

    ok = run_level1()
    if not ok:
        print("\n⛔ Level 1 未通过，停止测试")
        sys.exit(1)

    if args.level >= 2:
        ok2 = run_level2()
        if not ok2:
            print("\n⚠️  Level 2 未通过（Chrome 可能未安装）")
            if args.level >= 3:
                print("    跳过 Level 3")
                sys.exit(0)

    if args.level >= 3:
        ok3 = run_level3()
        if not ok3:
            print("\n⚠️  Level 3 未通过（TTS/ffmpeg 可能不可用）")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
