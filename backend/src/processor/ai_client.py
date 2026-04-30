"""WPS AI Gateway 客户端"""
from __future__ import annotations

import asyncio
import httpx
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIGatewayClient:
    """WPS AI Gateway 客户端，支持 OpenAI 兼容格式

    内置速率控制和重试机制，避免触发 QPS 限制。
    """

    def __init__(self, config: dict, max_concurrent: int = 3):
        self.url = config["url"]
        self.auth = config["auth"]
        self.model = config.get("model", "glm-5.1")
        self.provider = config.get("provider", "zhipu")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 20000)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.auth['token']}",
            "AI-Gateway-Uid": str(self.auth["uid"]),
            "AI-Gateway-Product-Name": self.auth["product_name"],
            "AI-Gateway-Intention-Code": self.auth["intention_code"],
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self, messages: list[dict], max_retries: int = 3
    ) -> str:
        """带重试和速率限制的请求"""
        payload = {
            "stream": True,
            "messages": messages,
            "model": self.model,
            "provider": self.provider,
            "base_llm_arguments": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
        }

        last_error = None
        for attempt in range(max_retries):
            async with self._semaphore:
                # 重试时增加延迟
                if attempt > 0:
                    wait = min(2 ** attempt, 30)
                    logger.info(f"重试第 {attempt} 次，等待 {wait}s")
                    await asyncio.sleep(wait)

                try:
                    async with httpx.AsyncClient(timeout=120) as client:
                        async with client.stream(
                            "POST", self.url,
                            headers=self._headers(),
                            json=payload,
                        ) as resp:
                            if resp.status_code == 429:
                                body = await resp.aread()
                                logger.warning(f"QPS 限制 (尝试 {attempt+1}/{max_retries})")
                                last_error = Exception(f"Rate limit: {resp.status_code}")
                                continue

                            if resp.status_code != 200:
                                body = await resp.aread()
                                logger.error(
                                    f"AI Gateway 请求失败: {resp.status_code} {body.decode()[:200]}"
                                )
                                last_error = Exception(f"AI Gateway error: {resp.status_code}")
                                continue

                            full_text = ""
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                raw = line[len("data:"):].strip()
                                if raw == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(raw)
                                except json.JSONDecodeError:
                                    continue

                                if chunk.get("code") != "Success":
                                    continue

                                for choice in chunk.get("choices", []):
                                    text = choice.get("text", "")
                                    if text:
                                        full_text += text

                            return full_text.strip()

                except (httpx.ConnectError, httpx.ReadTimeout) as e:
                    logger.warning(f"连接错误 (尝试 {attempt+1}/{max_retries}): {e}")
                    last_error = e
                    continue

        raise last_error or Exception("Max retries exceeded")

    async def chat(self, prompt: str, system: str = None) -> str:
        """发送单次对话请求，返回完整回复"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._request_with_retry(messages)

    async def chat_json(self, prompt: str, system: str = None) -> Optional[dict]:
        """发送对话请求，期望返回 JSON"""
        try:
            result = await self.chat(prompt, system)
            # 尝试提取 JSON
            if result.startswith("```"):
                lines = result.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                result = "\n".join(lines)

            # 找到 JSON 数组或对象
            start = result.find("[")
            if start == -1:
                start = result.find("{")

            if start == -1:
                return None

            end = result.rfind("]") if result[start] == "[" else result.rfind("}")
            json_str = result[start:end + 1]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"JSON 解析失败: {e}")
            return None
