#!/bin/zsh
set -eu
PROJECT_DIR="${0:A:h}"
if ! /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  print "需要 Python 3.9 或更新版本。请运行 xcode-select --install，安装完成后重试。"
  exit 1
fi
exec /usr/bin/python3 "$PROJECT_DIR/launcher.py" --check
