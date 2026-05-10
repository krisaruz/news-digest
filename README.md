# News Digest

> RSS 聚合 + AI 摘要/去重/打分 + 人工审核面板 + 多平台导出 + 视频生成，端到端的科技早报自动化系统。

## 项目简介

News Digest 是一个面向个人或小团队的每日 AI 与科技新闻自动化系统。核心流程：从 10+ 个 RSS 源并发采集，用 LLM 完成摘要、关键词提取、相似度去重和价值打分，通过 Next.js Dashboard 进行人工审核，最终一键导出 Markdown / 微信公众号 HTML / 短视频等多种格式。

不是简单的 RSS 阅读器——系统把"信息筛选"拆成五个独立阶段，每个阶段有明确的质量闸门：采集层控时效与去重，处理层用 AI 做内容理解，审核层保留人工判断，期刊层自动分类聚合，发布层适配不同平台格式。

## 核心架构

```
RSS 源(10+) → 并发采集 → AI 处理(摘要/关键词/去重/打分) → 阈值过滤 → 人工审核 → 期刊生成 → 多平台导出
```

### 数据源

约 10 个 RSS 源覆盖中英文 AI 与科技领域：

| 来源 | 方向 |
|------|------|
| Hacker News | 技术社区热点 |
| Reddit LocalLLaMA | 开源大模型动态 |
| VentureBeat AI | 行业报道 |
| TechCrunch AI | 创业与融资 |
| Ars Technica AI | 深度技术分析 |
| 机器之心 | 中文 AI 资讯 |
| 36kr AI | 中文科技商业 |
| GitHub Trending | 开源项目趋势 |
| Product Hunt | 新产品发现 |

支持 `max_age_hours` 时效控制和 URL 唯一去重。额外提供 `/api/collect/clipper` 接口，支持浏览器剪藏式投稿。

### AI 处理管线

五步串联，通过同一个 Gateway 客户端统一调用：

| 步骤 | 机制 | 产物 |
|------|------|------|
| 摘要 | LLM 对原文截断后提炼 | 50 字以内精要 |
| 关键词 | LLM + 已有词表辅助一致性 | 3-5 个标签 |
| 去重 | 标题规范化 + AI 语义判断 | 标记 DUPLICATE |
| 打分 | LLM 对标题+摘要评 0-1 分 | 价值分数 |
| 分类 | 规则引擎（关键词表+来源映射） | 类别标签 |

分类刻意使用规则而非 LLM，省成本、可控、确定性高。

### 审核面板

Next.js 15 + React 19 + TanStack Query + Zustand 构建的 Dashboard：

- **待审核列表** — 可编辑标题/摘要/分类，通过或驳回
- **历史期刊** — 浏览已生成的期刊，弹窗预览
- **一键导出** — Markdown / 微信 HTML / 知乎格式

### 期刊生成

从 `approved` 文章按分数排序取 Top N，按 `category` 自动分组，写入 `issues` 表。支持：

- 按类别聚合的结构化 JSON
- 自动编号的期次管理
- 分组后的 Markdown / HTML 渲染

### 视频管线

完整的短视频生成流水线：

```
期刊内容 → AI 口播稿 → Edge TTS 句级音频 → CSS 动画卡片 → Playwright 帧采集 → ffmpeg 转场拼接 + 字幕烧录
```

| 模块 | 技术 |
|------|------|
| 口播稿 | LLM 生成整期 + 分条脚本 |
| 语音 | Edge TTS，句级时间轴 |
| 画面 | HTML 品牌卡片 + CSS 动画 |
| 渲染 | Playwright 逐帧导出 |
| 合成 | ffmpeg 多种转场 + SRT 字幕 |

## 工程设计

| 设计决策 | 解决的问题 |
|---------|-----------|
| 五阶段管线（采集→处理→审核→期刊→发布） | 每个阶段有独立质量闸门 |
| 规则分类 vs LLM 分类 | 省成本、确定性高、可调试 |
| 信号量限并发 + 429 重试 | 对 API 友好，不触发限流 |
| URL 唯一 + AI 语义双重去重 | 消除跨源重复报道 |
| SQLite 两表设计（articles + issues） | 零运维，单文件部署 |
| 人工审核闸门 | 保留编辑判断，不完全依赖 AI |
| 多平台导出器 | 同一套数据适配不同发布渠道 |

## 技术栈

**后端**
- Python 3.8+ / FastAPI / Uvicorn
- feedparser + httpx（RSS 采集）
- aiosqlite（存储）
- LLM Gateway（兼容 OpenAI，流式）
- Edge TTS + Playwright + ffmpeg（视频管线）

**前端**
- Next.js 15 / React 19
- TanStack Query + Zustand
- Tailwind CSS

**配置**
- YAML 驱动（`config.yaml` + `prompts.yaml` + `sources.yaml`）

## 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
cp config.yaml.example config.yaml
# 填入 LLM API 配置
uvicorn src.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000` 进入审核面板。

## API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/collect/rss` | 触发 RSS 采集 |
| `POST /api/collect/clipper` | 浏览器剪藏投稿 |
| `POST /api/process` | 运行 AI 处理管线 |
| `GET /api/articles` | 查询文章列表 |
| `PUT /api/articles/{id}` | 编辑/审核文章 |
| `POST /api/issues/generate` | 生成期刊 |
| `GET /api/issues` | 查询期刊列表 |
| `GET /api/issues/{id}/export` | 导出指定格式 |
| `POST /api/pipeline/run` | 一键全流程 |

## 源码

GitHub: [krisaruz/news-digest](https://github.com/krisaruz/news-digest)
