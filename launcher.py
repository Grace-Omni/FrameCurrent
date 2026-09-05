"""Offline macOS preflight and safe re-open for the local app. No provider calls."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

import app


LOCAL_URL = "http://127.0.0.1:4173"


def existing_instance() -> str:
    """Return absent/current/other; never follow a local service's redirect."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(LOCAL_URL + "/api/health", timeout=2) as response:
            health = json.loads(response.read(64 * 1024))
        if (health.get("app_id") == app.APP_ID
                and health.get("instance_id") == app.INSTANCE_ID
                and health.get("version") == app.APP_VERSION and health.get("ok") is True):
            return "current"
        return "other"
    except urllib.error.URLError as error:
        return "absent" if isinstance(error.reason, ConnectionRefusedError) else "other"
    except (OSError, ValueError, AttributeError):
        return "other"


def diagnose() -> bool:
    if sys.platform != "darwin" or sys.version_info < (3, 9):
        print("需要 macOS 与 Python 3.9 或更新版本。Windows / Linux 暂不支持。", flush=True)
        return False
    print("检查 Apple 工具与作品目录，首次会编译媒体工具，请稍候（不连接 fal、不收费）…", flush=True)
    try:
        subprocess.run(["/usr/bin/swiftc", "--version"], check=True,
                       capture_output=True, timeout=20)
        app.prepare_media_tools()
    except (OSError, RuntimeError, subprocess.SubprocessError):
        print("检查未通过。请先在终端运行 xcode-select --install，完成后重新检查。\n"
              "若已安装，请确认源码已完整解压到可写文件夹，macOS 已允许终端访问该文件夹。", flush=True)
        return False
    print("环境检查通过：Python、Swift 媒体工具与作品目录可用。", flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="FrameCurrent 本机启动与环境检查")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return 0 if diagnose() else 1
    existing = existing_instance()
    if existing == "current":
        print("连续影像已经运行，正在重新打开网页。原任务不会重启。", flush=True)
        subprocess.run(["/usr/bin/open", LOCAL_URL], check=False)
        return 0
    if existing == "other":
        print("端口 4173 正在被其他程序、旧版本或另一份连续影像使用。\n"
              "请先检查原来的启动终端；若正在生成，先停播并保存作品，再退出旧服务。\n"
              "没有关闭任何进程，也没有提交生成。", flush=True)
        return 1
    if not diagnose():
        return 1
    print("请保持此终端开启。退出前先在网页停止续写并保存作品；Control-C 关闭本机服务。", flush=True)
    import os
    os.execv(sys.executable, [sys.executable, str(app.APP_ROOT / "app.py")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
