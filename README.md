# VidPull - 万能视频下载网站

基于 yt-dlp 的万能视频下载工具，支持 1800+ 平台，手机端可用。

## 技术栈

- **前端**：Vue 3 + Vite + Tailwind CSS + Vue Router + Pinia
- **后端**：Python 3.11 + FastAPI + yt-dlp
- **核心**：yt-dlp（GitHub 14w+ Star，支持 1800+ 网站）

## 快速开始

### 1. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

## 功能

- 单视频下载（粘贴链接 -> 解析 -> 选格式 -> 下载）
- 智能下载策略（直链重定向 / 代理下载 / 流式传输自动选择）
- 批量下载（VIP）
- AI 视频总结（VIP，规划中）
- 字幕翻译（VIP，规划中）

## 文档

- [需求分析](docs/requirements.md)
- [方案设计](docs/design.md)
