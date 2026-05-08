#!/usr/bin/env bash
set -euo pipefail

# 开发运行脚本：带重载与日志配置
# 使用方式：
#   bash run_dev.sh

export PYTHONUNBUFFERED=1

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

UVICORN_ARGS=(
  backend:app
  --app-dir "$ROOT_DIR"
  --reload
  --log-level debug
  --access-log
)

if [[ -f "$ROOT_DIR/logging.yaml" ]]; then
  UVICORN_ARGS+=(--log-config "$ROOT_DIR/logging.yaml")
fi

python -m uvicorn "${UVICORN_ARGS[@]}" "$@"
