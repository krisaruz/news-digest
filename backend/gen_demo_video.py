"""生成一个 demo 视频到 data/output/video/ 目录"""
import asyncio
import os
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from processor.video_pipeline import VideoPipeline

ARTICLES = [
    {
        "id": "demo-001",
        "title": "OpenAI 发布 GPT-5：多模态推理能力大幅提升",
        "summary": "OpenAI 正式发布 GPT-5，支持原生多模态，推理速度提升 3 倍。",
        "description": "OpenAI 正式发布了 GPT-5 模型，带来原生多模态能力，可以直接理解图像、音频和视频。MMLU-Pro 得分 92.1%，推理速度提升 3 倍，API 价格不变。",
        "source": "TechCrunch AI",
        "category": "AI 相关",
        "keywords": '["GPT-5", "OpenAI", "多模态"]',
        "score": 0.95,
        "image_url": "",
    },
    {
        "id": "demo-002",
        "title": "Anthropic Claude 4 开放 API：编程能力超越人类",
        "summary": "Claude 4 在 SWE-bench 首次超过人类工程师，支持百万 token 上下文。",
        "description": "Anthropic 发布 Claude 4，在 SWE-bench Verified 得分 78.2%，首次超过人类工程师平均水平。上下文窗口扩展到 100 万 token。",
        "source": "The Verge",
        "category": "AI 相关",
        "keywords": '["Claude 4", "Anthropic"]',
        "score": 0.92,
        "image_url": "",
    },
    {
        "id": "demo-003",
        "title": "DeepSeek V4 开源：千亿参数 MoE 完全免费",
        "summary": "DeepSeek 开源 V4，2000 亿参数 MoE，MIT 许可，性能对标 GPT-4o。",
        "description": "DeepSeek 发布并完全开源 V4 模型，MoE 架构总参数 2000 亿，激活参数 370 亿。MIT 许可证可自由商用。",
        "source": "Hacker News AI",
        "category": "AI 相关",
        "keywords": '["DeepSeek", "开源", "MoE"]',
        "score": 0.90,
        "image_url": "",
    },
    {
        "id": "demo-004",
        "title": "Cursor 完成 30 亿美元融资 估值 200 亿",
        "summary": "AI 编程工具 Cursor 完成 D 轮 30 亿融资，成为 AI 编程最大独角兽。",
        "description": "Cursor 宣布完成 30 亿美元 D 轮融资，估值 200 亿美元，用户超 500 万，ARR 破 10 亿。",
        "source": "TechCrunch AI",
        "category": "科技动态",
        "keywords": '["Cursor", "融资", "AI编程"]',
        "score": 0.85,
        "image_url": "",
    },
    {
        "id": "demo-005",
        "title": "Meta Llama 4：首个原生多模态开源大模型",
        "summary": "Meta 开源 Llama 4 系列，Scout/Maverick/Behemoth，原生支持多模态。",
        "description": "Meta 发布 Llama 4 系列。Scout 17B 适合边缘部署；Maverick 400B MoE 对标 GPT-4o；Behemoth 2T 训练中。全系列原生支持多模态。",
        "source": "Reddit LocalLLaMA",
        "category": "AI 相关",
        "keywords": '["Llama 4", "Meta", "开源"]',
        "score": 0.88,
        "image_url": "",
    },
]


async def main():
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    output_dir = str(Path(__file__).parent.parent / "data" / "output" / "video")
    os.makedirs(output_dir, exist_ok=True)

    pipeline = VideoPipeline(
        tts_config=config["tts_gateway"],
        output_dir=output_dir,
    )

    path = await pipeline.generate_video(
        issue_number=99,
        date_str="2026年4月19日",
        articles=ARTICLES,
    )

    if path:
        size_mb = Path(path).stat().st_size / (1024 * 1024)
        print(f"\n{'='*50}")
        print(f"  视频已生成: {path}")
        print(f"  文件大小: {size_mb:.1f} MB")
        print(f"{'='*50}")
    else:
        print("视频生成失败")


if __name__ == "__main__":
    asyncio.run(main())
