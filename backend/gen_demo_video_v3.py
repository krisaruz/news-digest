"""Demo 视频生成脚本 V3 - 测试 CSS 动画 + edge_tts 管线"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEMO_ARTICLES = [
    {
        "title": "OpenAI 发布 GPT-5：多模态推理能力大幅提升",
        "description": "OpenAI 今日正式发布 GPT-5 模型，在数学推理、代码生成和视觉理解方面均有显著提升。新模型支持百万级上下文窗口，推理速度提升3倍。",
        "source": "OpenAI Blog",
        "category": "AI 相关",
        "keywords": '["GPT-5", "多模态", "推理"]',
        "image_url": "",
    },
    {
        "title": "Google DeepMind 推出 AlphaFold 4 预测蛋白质动态结构",
        "description": "DeepMind 最新发布的 AlphaFold 4 不仅能预测蛋白质静态结构，还能模拟蛋白质在不同条件下的动态变化。",
        "source": "Nature",
        "category": "科技动态",
        "keywords": '["AlphaFold", "蛋白质", "DeepMind"]',
        "image_url": "",
    },
    {
        "title": "Cursor 2.0 发布：AI 编程助手进入自主开发时代",
        "description": "Cursor 发布 2.0 版本，引入后台自主 Agent 模式，支持多文件重构、自动调试和端到端功能开发。开发者可以在描述需求后让 AI 自主完成整个开发流程。",
        "source": "Cursor Blog",
        "category": "工具",
        "keywords": '["Cursor", "AI编程", "Agent"]',
        "image_url": "",
    },
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "output", "video")


async def main():
    from processor.video_pipeline import VideoPipeline

    pipeline = VideoPipeline(
        voice="zh-CN-XiaoxiaoNeural",
        output_dir=OUTPUT_DIR,
    )

    result = await pipeline.generate_video(
        issue_number=99,
        date_str="2026-04-19",
        articles=DEMO_ARTICLES,
    )

    if result:
        print(f"\n[OK] 视频生成成功: {result}")
        size_mb = os.path.getsize(result) / 1024 / 1024
        print(f"     大小: {size_mb:.1f} MB")
    else:
        print("\n[FAIL] 视频生成失败")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
