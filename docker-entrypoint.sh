#!/bin/bash
set -e

# 启动Xvfb虚拟显示服务器
Xvfb :99 -screen 0 1280x1024x24 -ac &

# 确保app/static/screenshots目录存在
mkdir -p app/static/screenshots/thumbnails
mkdir -p app/static/screenshots/html

# 等待Xvfb启动
sleep 2

# 执行传递给脚本的命令
exec "$@" 