## 一、中文说明（完整）

### 1️⃣ 项目简介
本项目是一个 **俄罗斯国标（ГОСТ）学术报告格式审查网站**，用户上传 `.docx` 报告后，系统将根据 ГОСТ 规则进行自动检查，并生成一份 **包含问题定位、错误级别、错误内容及（可选）AI 修改建议** 的审查结果文档。

支持两种模式：
- **纯规则模式（Hard Rules）**：仅基于 ГОСТ 规则检查
- **AI 模式（预留）**：可接入 GPT / DeepSeek / Qwen（当前 MVP 可先关闭）

---

### 2️⃣ 系统架构
```text
Frontend (Vue/Vite)
        ↓ HTTP API
Backend (Django REST)
        ↓
Celery Worker（异步审查）
        ↓
Rules Engine（runtime.json）
        ↓
Result DOCX

gost-mvp/
├── backend/
│   ├── apps/
│   │   ├── jobs/          # 任务（上传 / 状态 / 下载）
│   │   └── checker/       # 规则引擎、DSL、DOCX 解析
│   ├── config/            # Django + Celery 配置
│   ├── requirements.txt
│   └── venv/              # Python 虚拟环境（Python 3.12）
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── get-start.sh           # 一键启动脚本（macOS / Linux）
4️⃣ 启动方式（macOS / Linux）
✅ 前置条件

macOS / Linux

Homebrew（macOS）

Git

✅ 一键启动（推荐）
chmod +x get-start.sh
./get-start.sh


脚本将自动完成：

安装 Python 3.12

创建 / 校验 venv（强制使用 3.12）

安装后端依赖（增量）

编译 ГОСТ DSL → runtime.json

启动 Redis / Celery / Django

启动前端 Vite

自动打开浏览器

5️⃣ 启动方式（Windows）

⚠️ Windows 不支持直接运行 get-start.sh

推荐方式（PowerShell + 手动）：

安装 Python 3.12（官方）

创建虚拟环境

cd backend
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt


编译 DSL

python apps\checker\engine\compile_dsl.py ^
  apps\checker\standards\gost_7_32_2017.yaml ^
  apps\checker\standards\gost_7_32_2017.runtime.json


启动后端

python manage.py migrate
python manage.py runserver


启动 Celery（新终端）

celery -A config.celery_app worker -l info -P solo


启动前端

cd frontend
npm install
npm run dev

6️⃣ 修改项目路径的位置

在 get-start.sh 顶部修改：

PROJECT_ROOT="/你的/本地/项目/绝对路径/gost-mvp"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

7️⃣ 数据库说明
✅ 默认数据库（推荐）

SQLite

无需配置，自动创建

适合 MVP / 课程设计 / 单机运行

🔁 可选 MySQL（高级）

启动前设置环境变量：

export USE_MYSQL=1
export DB_NAME=gost_checker
export DB_USER=gost
export DB_PASSWORD=StrongPass123!
export DB_HOST=127.0.0.1
export DB_PORT=3306

8️⃣ 接口说明（简要）

POST /api/jobs/：上传 .docx 创建审查任务

GET /api/jobs/{id}/：查询任务状态与进度

GET /api/jobs/{id}/download/：下载审查结果 DOCX

