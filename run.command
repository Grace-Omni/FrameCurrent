#!/bin/zsh
set -eu

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

echo ""
echo "连续影像 · FrameCurrent"
echo "浏览器将自动打开；终端窗口保持开启即可。"
echo "按 Control-C 停止本地服务。"
echo ""

exec /usr/bin/python3 "$SCRIPT_DIR/app.py"
