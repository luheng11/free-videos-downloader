# 万能视频下载网站 - 方案设计文档

## 1. 技术栈

### 前端
- Vue 3 + Vite + Tailwind CSS
- Vue Router（多页面路由）
- Pinia（状态管理）
- axios（API 调用）

### 后端
- Python 3.11 + FastAPI
- yt-dlp（pip 包，直接调用 Python API）
- httpx（直链探测）
- 无数据库，内存任务队列（asyncio + dict）

### 外部依赖
- FFmpeg（格式合并/字幕嵌入，yt-dlp 合并音视频流时需要）

### 核心能力
- yt-dlp：GitHub 14w+ Star，支持 1800+ 网站

## 2. 项目结构

```
d:\code_ai\
├── frontend/                  # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── views/             # 页面
│   │   │   ├── Home.vue       # 首页（下载页）
│   │   │   ├── Batch.vue      # 批量下载
│   │   │   ├── Tools.vue      # AI 工具
│   │   │   └── Vip.vue        # 会员中心
│   │   ├── components/
│   │   │   ├── NavBar.vue     # 导航栏
│   │   │   ├── FooterBar.vue  # 页脚
│   │   │   └── DownloadCard.vue # 视频卡片
│   │   ├── stores/
│   │   │   └── download.ts    # 下载状态管理
│   │   ├── router/
│   │   │   └── index.ts       # 路由配置
│   │   ├── api/
│   │   │   └── index.ts       # API 封装
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css          # Tailwind + 全局样式
│   ├── index.html
│   ├── vite.config.ts         # Vite 配置（含 API 代理）
│   └── tailwind.config.js     # Tailwind 主题配置
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口 + 路由
│   ├── services/
│   │   ├── downloader.py      # yt-dlp 封装（解析+下载+直链）
│   │   ├── download_service.py # 智能下载策略
│   │   ├── task_queue.py      # 内存任务队列
│   │   └── cleanup.py         # 定时清理临时文件
│   ├── downloads/             # 临时下载目录
│   └── requirements.txt
├── docs/                      # 文档
│   ├── requirements.md        # 需求分析
│   └── design.md              # 方案设计（本文件）
└── README.md
```

## 3. 后端 API 设计

### 3.1 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/parse` | 解析视频元数据（不下载） |
| POST | `/api/download` | 智能下载（自动选择策略） |
| POST | `/api/task` | 提交后台下载任务 |
| GET | `/api/task/{id}` | 查询任务状态 |
| GET | `/api/tasks` | 列出最近任务 |
| GET | `/api/file/{id}` | 获取已下载文件链接 |

### 3.2 扩展接口（阶段 5+）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/batch` | 批量下载 |
| POST | `/api/ai/summary` | AI 视频总结 |
| POST | `/api/ai/translate` | 字幕翻译 |
| GET | `/api/quota` | 查询剩余次数 |

### 3.3 智能下载策略流程

```
用户请求 /api/download
    ↓
1. 调用 get_direct_url() 获取直链
    ↓
2. is_url_accessible() 探测直链可访问性（HEAD 请求，6s 超时）
    ↓
直链可用？
├── 是 → 302 重定向到直链（不占服务器资源）
└── 否 → 3. download_video() 代理下载到本地
            ↓
         文件 > 500MB？
         ├── 是 → StreamingResponse 流式传输
         └── 否 → FileResponse 直接返回
```

### 3.4 yt-dlp 封装核心代码

```python
from yt_dlp import YoutubeDL

# 解析（不下载）
def parse_video(url):
    opts = {'quiet': True, 'skip_download': True, 'no_warnings': True, 'noplaylist': True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        info = ydl.sanitize_info(info)  # 确保 JSON 可序列化
        return { 'title': ..., 'formats': ..., ... }

# 代理下载
def download_video(url, format_id, task_id):
    opts = {'format': format_id, 'outtmpl': f'downloads/{task_id}.%(ext)s', ...}
    with YoutubeDL(opts) as ydl:
        ydl.download([url])

# 获取直链
def get_direct_url(url, format_id):
    opts = {'skip_download': True, 'format': format_id, ...}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('requested_formats', [{}])[0].get('url') or info.get('url')
```

### 3.5 文件清理

- 临时下载文件存放在 `backend/downloads/`
- 后台协程每 2 分钟扫描一次
- 超过 10 分钟的文件自动删除

## 4. 前端设计

### 4.1 页面规划

| 页面 | 路由 | 说明 |
|------|------|------|
| 首页 | `/` | URL 输入 -> 解析 -> 视频卡片 -> 格式选择 -> 下载 |
| 批量下载 | `/batch` | 多行链接输入，批量下载（VIP） |
| AI 工具 | `/tools` | 视频总结、字幕翻译（VIP） |
| 会员中心 | `/vip` | 权益对比、套餐选择 |

### 4.2 状态管理（Pinia）

`stores/download.ts` 管理以下状态：
- `loading` - 解析中
- `error` - 错误信息
- `videoInfo` - 解析结果
- `downloading` - 下载中
- `history` - 下载历史（localStorage）

核心方法：
- `parse(url)` - 调用 /api/parse
- `download(url, formatId)` - 调用 /api/download（智能策略）
- `downloadViaTask(url, formatId)` - 通过任务队列下载（带进度）

### 4.3 UI 主题

```js
// tailwind.config.js
colors: {
  brand: {
    DEFAULT: "#1777FF",   // 亮蓝主色
    dark: "#0F172A",      // 深蓝
    light: "#E8F2FF",     // 浅蓝背景
  }
}
```

- 主按钮：`bg-brand text-white rounded-full`（胶囊形）
- 次按钮：`bg-white rounded-xl2 border shadow-sm`
- 卡片：`bg-white rounded-xl2 border shadow-sm hover:shadow-md`

## 5. 开发阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段 1 | FastAPI 后端 + yt-dlp 封装，3 个核心 API | ✅ 完成 |
| 阶段 2 | Vue 3 + Vite + Tailwind 前端骨架 | ✅ 完成 |
| 阶段 3 | 前后端联调，完整下载流程 | ✅ 完成 |
| 阶段 4 | UI 精雕 + VIP 引导 + 平台展示 + 额度控制 | 待开始 |
| 阶段 5 | 扩展功能：字幕、进度、历史、移动端 | 待开始 |

## 6. 启动方式

### 后端
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

前端开发服务器 `http://localhost:5173`，API 请求自动代理到后端 `http://localhost:8000`。
