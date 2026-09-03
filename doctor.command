#!/bin/zsh
set -u

PROJECT_DIR="${0:A:h}"
missing=0

echo ""
echo "连续影像 · FrameCurrent 环境检查"
echo "项目：$PROJECT_DIR"
echo ""

for tool_path in /usr/bin/python3 /usr/bin/swiftc /usr/bin/sips /usr/bin/avmediainfo /usr/bin/open; do
  if [[ -x "$tool_path" ]]; then
    echo "✓ $tool_path"
  else
    echo "✗ 缺少 $tool_path"
    missing=1
  fi
done

echo ""
/usr/bin/python3 --version 2>&1 || true
/usr/bin/swiftc --version 2>&1 | /usr/bin/head -n 1 || true

if [[ "$missing" -ne 0 ]]; then
  echo ""
  echo "环境不完整。请先安装或更新 Xcode Command Line Tools。"
  exit 1
fi

echo ""
echo "环境检查通过。可以双击 run.command 启动。"
