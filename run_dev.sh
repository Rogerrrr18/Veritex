#!/usr/bin/env bash
set -euo pipefail

# 开发运行脚本：带重载与日志配置
# 使用方式：
#   bash run_dev.sh

export PYTHONUNBUFFERED=1

exec python -m uvicorn backend:app \
  --reload \
  --log-config logging.yaml \
  --log-level debug \
  --access-log

