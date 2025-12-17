#!/bin/bash
set -euo pipefail
# important you have to change to your root path !!!
PROJECT_ROOT="/Users/micheal/Documents/codes/iu6/大三上/学期作业/Check-gost-mvp/gost-mvp"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

DJANGO_PORT=8000
VITE_PORT=5173

green() { echo -e "\033[1;32m$1\033[0m"; }
yellow() { echo -e "\033[1;33m$1\033[0m"; }
red() { echo -e "\033[1;31m$1\033[0m"; }

if [ ! -d "$BACKEND_DIR" ]; then red "❌ BACKEND_DIR 不存在: $BACKEND_DIR"; exit 1; fi
if [ ! -d "$FRONTEND_DIR" ]; then red "❌ FRONTEND_DIR 不存在: $FRONTEND_DIR"; exit 1; fi

# ---------- brew deps ----------
if ! command -v brew &> /dev/null; then
  yellow "🧩 安装 Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  green "✅ Homebrew 已安装"
fi

# ---------- Python 3.12 (force, global) ----------
PY312="/opt/homebrew/opt/python@3.12/bin/python3.12"
if [ ! -x "$PY312" ]; then
  yellow "🐍 安装 Python 3.12..."
  brew install python@3.12
fi
green "✅ Python(3.12): $("$PY312" --version)"

# ---------- Node.js ----------
if ! command -v node &> /dev/null; then
  yellow "📦 安装 Node.js..."
  brew install node
fi
green "✅ Node: $(node -v)"

# ---------- Redis ----------
if ! command -v redis-server &> /dev/null; then
  yellow "💬 安装 Redis..."
  brew install redis
fi
brew services start redis >/dev/null 2>&1 || true
green "✅ Redis 服务已启动"

# ---------- venv (force 3.12) ----------
cd "$BACKEND_DIR"

VENV_DIR="$BACKEND_DIR/venv"

NEED_REBUILD=0
if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
  NEED_REBUILD=1
else
  VENV_VER="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
  if [ "${VENV_VER:-}" != "3.12" ]; then
    yellow "⚠️ 检测到 venv Python=${VENV_VER:-unknown}，将重建为 3.12"
    NEED_REBUILD=1
  fi
fi

if [ "$NEED_REBUILD" = "1" ]; then
  rm -rf "$VENV_DIR"
  yellow "🪄 使用 Python 3.12 创建 venv..."
  "$PY312" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

PY="$VENV_DIR/bin/python"
PIP="$PY -m pip"

# 强制校验：全程必须是 3.12
PY_OK="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PY_OK" != "3.12" ]; then
  red "❌ 运行时 Python 不是 3.12，而是 $PY_OK（拒绝启动）"
  exit 1
fi

green "✅ venv 已激活: $VENV_DIR ($("$PY" --version))"
$PIP install --upgrade pip setuptools wheel >/dev/null

# ---------- backend deps (install only when requirements changed) ----------
REQ_FILE="$BACKEND_DIR/requirements.txt"
REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"

hash_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    "$PY" - "$1" <<'PY'
import hashlib, sys
p=sys.argv[1]
h=hashlib.sha256(open(p,'rb').read()).hexdigest()
print(h)
PY
  fi
}

yellow "📦 检查后端依赖是否需要安装..."
CUR_HASH="$(hash_file "$REQ_FILE")"
OLD_HASH=""
[ -f "$REQ_HASH_FILE" ] && OLD_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || true)"

if [ "$CUR_HASH" != "$OLD_HASH" ]; then
  yellow "📦 requirements 发生变化，开始安装/更新依赖..."
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
  $PIP install --upgrade pip setuptools wheel >/dev/null
  $PIP install -r "$REQ_FILE"
  echo "$CUR_HASH" > "$REQ_HASH_FILE"
  green "✅ 后端依赖已同步（hash 已更新）"
else
  green "✅ requirements 未变化，跳过 pip install"
fi

# ---------- optional: MySQL ----------
USE_MYSQL="${USE_MYSQL:-0}"
if [ "$USE_MYSQL" = "1" ]; then
  yellow "🗄️ 启用 MySQL 模式"

  if ! command -v mysql &> /dev/null; then
    yellow "安装 MySQL..."
    brew install mysql
  fi
  brew services start mysql >/dev/null 2>&1 || true
  green "✅ MySQL 服务已启动"

  # 依赖：PyMySQL（你目前走这条路线）
  $PIP install pymysql >/dev/null

  # 环境变量（你的 settings.py 若读取 env，就能无侵入切换）
  export DB_ENGINE="mysql"
  export DB_NAME="${DB_NAME:-gost_checker}"
  export DB_USER="${DB_USER:-gost}"
  export DB_PASSWORD="${DB_PASSWORD:-StrongPass123!}"
  export DB_HOST="${DB_HOST:-127.0.0.1}"
  export DB_PORT="${DB_PORT:-3306}"
fi

# ---------- compile DSL ----------
yellow "🔧 编译 DSL -> runtime.json..."
"$PY" "$BACKEND_DIR/apps/checker/engine/compile_dsl.py" \
  "$BACKEND_DIR/apps/checker/standards/gost_7_32_2017.yaml" \
  "$BACKEND_DIR/apps/checker/standards/gost_7_32_2017.runtime.json"
green "✅ runtime.json 已生成"

# ---------- kill old ----------
yellow "🧹 清理旧进程 + 释放端口..."
pkill -f "manage.py runserver" >/dev/null 2>&1 || true
pkill -f "celery" >/dev/null 2>&1 || true
pkill -f "vite" >/dev/null 2>&1 || true
sleep 1

if lsof -i :$DJANGO_PORT >/dev/null 2>&1; then kill -9 $(lsof -ti :$DJANGO_PORT) >/dev/null 2>&1 || true; fi
if lsof -i :$VITE_PORT >/dev/null 2>&1; then kill -9 $(lsof -ti :$VITE_PORT) >/dev/null 2>&1 || true; fi
green "✅ 清理完成"

# ---------- migrate (do NOT swallow errors) ----------
yellow "⚙️ 执行数据库迁移..."
"$PY" manage.py makemigrations
"$PY" manage.py migrate
green "✅ migrate 完成"

# ---------- start celery/django ----------
yellow "🚀 启动 Celery..."
nohup "$PY" -m celery -A config.celery_app worker -l info -P solo > "$BACKEND_DIR/celery.log" 2>&1 &
sleep 2
green "✅ Celery 已启动（$BACKEND_DIR/celery.log）"

yellow "🌐 启动 Django..."
nohup "$PY" manage.py runserver 0.0.0.0:$DJANGO_PORT > "$BACKEND_DIR/django.log" 2>&1 &
sleep 2
green "✅ Django 已启动（$BACKEND_DIR/django.log）"

# ---------- frontend deps (install only when lock changed) ----------
cd "$FRONTEND_DIR"
LOCK_FILE=""
[ -f package-lock.json ] && LOCK_FILE="package-lock.json"
[ -f pnpm-lock.yaml ] && LOCK_FILE="pnpm-lock.yaml"
[ -f yarn.lock ] && LOCK_FILE="yarn.lock"

if [ -n "$LOCK_FILE" ]; then
  FRONT_HASH_FILE="$FRONTEND_DIR/.deps.sha256"
  CUR_FHASH="$(hash_file "$FRONTEND_DIR/$LOCK_FILE")"
  OLD_FHASH=""
  [ -f "$FRONT_HASH_FILE" ] && OLD_FHASH="$(cat "$FRONT_HASH_FILE" 2>/dev/null || true)"

  if [ "$CUR_FHASH" != "$OLD_FHASH" ] || [ ! -d node_modules ]; then
    yellow "📦 前端依赖需要更新（lock 变化或 node_modules 缺失）..."
    npm install
    echo "$CUR_FHASH" > "$FRONT_HASH_FILE"
    green "✅ 前端依赖已同步"
  else
    green "✅ 前端依赖未变化，跳过 npm install"
  fi
else
  if [ ! -d node_modules ]; then
    yellow "📦 安装前端依赖..."
    npm install
  fi
fi

yellow "🚀 启动 Vite..."
nohup npm run dev -- --host 0.0.0.0 --port $VITE_PORT > "$FRONTEND_DIR/frontend.log" 2>&1 &
sleep 2
green "✅ 前端已启动（$FRONTEND_DIR/frontend.log）"

open "http://localhost:$VITE_PORT" >/dev/null 2>&1 || true
green "🎉 启动完成：前端 http://localhost:$VITE_PORT  后端 http://127.0.0.1:$DJANGO_PORT/api/"
