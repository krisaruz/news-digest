# 每日 AI 科技简报

全自动每日科技新闻采集-处理-分发系统，支持 RSS 聚合、AI 智能摘要、人工审核、多平台导出与短视频生成。

## 功能

- **RSS 采集**：10 个预设源（Hacker News、TechCrunch、Reddit 等），仅采集 24h 内文章
- **AI 处理**：摘要生成、关键词提取、智能打分、72h 去重、自动分类
- **人工审核**：Web Dashboard 支持浏览/编辑/通过/排除
- **多平台导出**：Markdown、微信公众号 HTML、知乎（含目录）
- **视频生成**：TTS 语音 + 品牌风格 1920×1080 卡片 + ffmpeg 组装

## 架构

```
RSS 源 → 采集 → AI 处理(摘要/关键词/去重/打分) → 人工审核 → 输出(Markdown/HTML/视频)
```

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+（前端可选）
- ffmpeg（视频生成，winget install ffmpeg）
- Chrome（卡片渲染）

### 后端

```bash
cd backend
pip install -r requirements.txt

# 启动服务（默认端口 8000）
cd ..
PYTHONPATH=backend/src uvicorn backend.src.main:app --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000 打开 Dashboard。

### 使用流程

1. **采集**：点击"采集 RSS"，从 10 个源拉取近 24h 文章
2. **处理**：点击"AI 处理"，运行摘要/关键词/打分/去重流水线
3. **审核**：在待审列表中逐篇查看、编辑、通过或排除
4. **生成**：点击"生成简报"，精选 Top 10 条创建新一期
5. **导出**：在"历史期刊"中查看并导出 Markdown / 微信公众号 HTML
6. **视频**：`POST /api/issue/{id}/video` 生成短视频（需 TTS 凭证）

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.8 + FastAPI + feedparser + aiosqlite + APScheduler |
| 前端 | Next.js 15 + React Query + Zustand + Tailwind CSS |
| AI | OpenAI 兼容 API（默认 glm-5.1，可替换任意模型） |
| TTS | MiniMax speech-01-pro（需额外配置 intention code） |
| 视频 | Selenium（HTML→PNG）+ ffmpeg（图片+音频组装） |
| 存储 | SQLite（articles + issues 两张表） |

## 配置

复制 `config.yaml.example` 为 `config.yaml` 并填入你的凭证：

```yaml
ai_gateway:        # 文本 AI Gateway（已配置）
tts_gateway:       # TTS Gateway（Token 已填，需配置 intention code 路由）
collector:
  schedule: "0 8 * * *"     # 每天 8:00 自动采集
  max_age_hours: 24          # 仅采集 24h 内文章
processor:
  score_threshold: 0.3       # AI 打分阈值
  dedup_window_hours: 72     # 72h 去重窗口
  max_items_per_issue: 10    # 每期最多 10 条
```

RSS 源编辑 [backend/src/collector/sources.yaml](backend/src/collector/sources.yaml)。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/collect/trigger` | 手动触发 RSS 采集 |
| POST | `/api/collect/clipper` | 接收 Web Clipper 投稿 |
| GET | `/api/collect/stats` | 采集统计 |
| POST | `/api/process/run` | 运行 AI 处理流水线 |
| GET | `/api/articles/pending` | 获取待审核文章 |
| GET | `/api/articles/{id}` | 获取单篇文章 |
| PUT | `/api/articles/{id}` | 编辑文章 |
| POST | `/api/issue/generate` | 生成新一期简报 |
| GET | `/api/issue/{id}` | 获取期刊详情 |
| GET | `/api/issues` | 列出所有期刊 |
| POST | `/api/issue/{id}/export?platform=wechat` | 导出（wechat/zhihu/markdown） |
| POST | `/api/issue/{id}/publish` | 标记为已发布 |
| POST | `/api/issue/{id}/video` | 生成短视频 |
| POST | `/api/pipeline/run` | 运行完整流水线 |

## TTS 状态

TTS Gateway 需自行配置路由。当前视频流水线已支持优雅降级：

- TTS 失败时使用固定时长静默卡片
- 卡片渲染和 ffmpeg 组装均已验证可用

## 项目结构

```
news-digest/
├── config.yaml                           # 全局配置
├── backend/
│   ├── src/
│   │   ├── main.py                       # FastAPI 入口
│   │   ├── collector/                    # 采集层
│   │   │   ├── rss_feed.py               # RSS 解析（日期过滤+图片提取）
│   │   │   └── sources.yaml              # RSS 源配置
│   │   ├── processor/                    # AI 处理层
│   │   │   ├── ai_client.py              # WPS Gateway 客户端（速率控制+重试）
│   │   │   ├── summarizer.py             # 摘要生成
│   │   │   ├── keyworder.py              # 关键词提取
│   │   │   ├── dedup.py                  # 去重检测
│   │   │   ├── scorer.py                 # 智能打分
│   │   │   ├── categorizer.py            # 自动分类
│   │   │   ├── generator.py              # 内容生成
│   │   │   ├── prompts.yaml              # AI Prompt 模板
│   │   │   ├── tts_client.py             # TTS Gateway 客户端
│   │   │   ├── video_cards.py            # 品牌风格卡片生成
│   │   │   └── video_pipeline.py         # 视频组装流水线
│   │   ├── storage/
│   │   │   └── db.py                     # SQLite 存储
│   │   ├── publisher/
│   │   │   ├── markdown.py               # 多平台导出（微信/知乎/Markdown）
│   │   │   └── wechat.py                 # 微信导出别名
│   │   └── scheduler.py                  # APScheduler 定时任务
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                          # Next.js 页面
│   │   │   ├── page.tsx                  # Dashboard 主页
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── PendingList.tsx           # 待审列表
│   │   │   └── IssueList.tsx             # 历史期刊
│   │   └── lib/
│   │       └── api.ts                    # API 调用
│   └── package.json
└── data/                                 # 运行数据（gitignore）
    ├── digest.db                         # SQLite 数据库
    └── output/                           # 导出文件
        ├── markdown/
        ├── html/
        └── video/
```
