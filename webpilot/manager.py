"""浏览器驱动自动管理（对应 Selenium 4.6+ 的 Selenium Manager）。

策略：
1. 环境变量指定（WEBPILOT_CHROME_DRIVER / WEBPILOT_EDGE_DRIVER / WEBPILOT_FIREFOX_DRIVER）
2. 系统 PATH 中查找
3. 本地缓存 ~/.webpilot/drivers/ 中匹配浏览器大版本
4. 从官方源自动下载：
   - Chrome  : Chrome for Testing 官方 JSON 接口
   - Edge    : Microsoft 官方 msedgedriver.microsoft.com
   - Firefox : geckodriver GitHub Releases
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests

from .exceptions import DriverNotFoundException
from .logger import get_logger

log = get_logger()

_HTTP_TIMEOUT = 30
_DOWNLOAD_TIMEOUT = 180

CHROME_VERSIONS_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
)
EDGE_LATEST_URL = "https://msedgedriver.microsoft.com/LATEST_RELEASE_{major}"
EDGE_DOWNLOAD_URL = "https://msedgedriver.microsoft.com/{version}/edgedriver_{platform}.zip"
GECKO_RELEASES_URL = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"

_EXE = ".exe" if sys.platform == "win32" else ""

DRIVER_NAMES = {
    "chrome": f"chromedriver{_EXE}",
    "edge": f"msedgedriver{_EXE}",
    "firefox": f"geckodriver{_EXE}",
}


def _cache_root() -> Path:
    root = Path.home() / ".webpilot" / "drivers"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _platform_slug() -> str:
    """映射到官方驱动的平台目录名。"""
    system = sys.platform
    machine = platform.machine().lower()
    if system == "win32":
        return "win64" if machine in ("amd64", "x86_64") else "win32"
    if system == "darwin":
        return "mac-arm64" if machine == "arm64" else "mac-x64"
    return "linux64"


# ---------------------------------------------------------------------------
# 浏览器版本检测
# ---------------------------------------------------------------------------

def _run_version(binary: str) -> Optional[str]:
    try:
        out = subprocess.check_output(
            [binary, "--version"], stderr=subprocess.DEVNULL, timeout=10
        ).decode(errors="ignore")
        m = re.search(r"(\d+\.\d+\.\d+[\.\d]*)", out)
        return m.group(1) if m else None
    except Exception:
        return None


def get_browser_version(browser: str) -> Optional[str]:
    """尽最大努力检测本机浏览器版本，失败返回 None。"""
    if sys.platform == "win32":
        return _browser_version_windows(browser)
    if sys.platform == "darwin":
        bins = {
            "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
            "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
            "firefox": ["/Applications/Firefox.app/Contents/MacOS/firefox"],
        }
    else:
        bins = {
            "chrome": ["google-chrome", "google-chrome-stable", "chromium"],
            "edge": ["microsoft-edge", "microsoft-edge-stable"],
            "firefox": ["firefox"],
        }
    for b in bins.get(browser, []):
        ver = _run_version(b)
        if ver:
            return ver
    return None


def _browser_version_windows(browser: str) -> Optional[str]:
    """Windows：优先读注册表，其次找安装目录跑 --version。"""
    import winreg

    reg_paths = {
        "chrome": r"SOFTWARE\Google\Chrome\BLBeacon",
        "edge": r"SOFTWARE\Microsoft\Edge\BLBeacon",
        "firefox": r"SOFTWARE\Mozilla\Mozilla Firefox",
    }
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, reg_paths[browser]) as key:
                value_name = "CurrentVersion" if browser == "firefox" else "version"
                version, _ = winreg.QueryValueEx(key, value_name)
                if version:
                    return str(version)
        except OSError:
            continue

    candidates = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    }
    for path in candidates.get(browser, []):
        if Path(path).exists():
            ver = _run_version(path)
            if ver:
                return ver
    return None


# ---------------------------------------------------------------------------
# 驱动解析与下载
# ---------------------------------------------------------------------------

def ensure_driver(browser: str, driver_path: Optional[str] = None) -> str:
    """返回可用的驱动可执行文件路径，找不到就自动下载。"""
    if driver_path:
        if not Path(driver_path).exists():
            raise DriverNotFoundException(f"指定的驱动不存在: {driver_path}")
        return driver_path

    # 1. 环境变量
    env_key = f"WEBPILOT_{browser.upper()}_DRIVER"
    if os.environ.get(env_key) and Path(os.environ[env_key]).exists():
        log.info("使用环境变量 %s 指定的驱动", env_key)
        return os.environ[env_key]

    # 2. PATH
    on_path = shutil.which(DRIVER_NAMES[browser])
    if on_path:
        log.info("在 PATH 中找到驱动: %s", on_path)
        return on_path

    # 3. 缓存（匹配浏览器大版本）
    browser_version = get_browser_version(browser)
    browser_major = browser_version.split(".")[0] if browser_version else None
    cached = _find_cached(browser, browser_major)
    if cached:
        log.info("使用缓存驱动: %s", cached)
        return cached

    # 4. 自动下载
    log.info("本地没有 %s 驱动，开始自动下载（浏览器版本: %s）", browser, browser_version or "未知")
    return _download_driver(browser, browser_version)


def _find_cached(browser: str, major: Optional[str]) -> Optional[str]:
    root = _cache_root() / browser
    if not root.exists():
        return None
    candidates = sorted(root.iterdir(), reverse=True)
    for version_dir in candidates:
        if major and not version_dir.name.startswith(major + "."):
            continue
        exe = version_dir / DRIVER_NAMES[browser]
        if exe.exists():
            return str(exe)
    return None


def _resolve_chrome_driver_url(browser_major: Optional[str]) -> tuple[str, str]:
    """从 Chrome for Testing 接口挑一个匹配大版本的最新驱动。"""
    data = requests.get(CHROME_VERSIONS_URL, timeout=_HTTP_TIMEOUT).json()
    slug = _platform_slug()
    best = None
    for entry in data["versions"]:
        version = entry["version"]
        if browser_major and not version.startswith(browser_major + "."):
            continue
        for item in entry.get("downloads", {}).get("chromedriver", []):
            if item["platform"] == slug:
                if best is None or _version_key(version) > _version_key(best[0]):
                    best = (version, item["url"])
    if best:
        return best
    raise DriverNotFoundException(
        f"Chrome for Testing 中没有匹配大版本 {browser_major} 的 chromedriver（平台 {slug}）"
    )


def _resolve_edge_driver_url(browser_major: Optional[str]) -> tuple[str, str]:
    slug = _platform_slug()
    # Edge 平台名与 Chrome 不同
    edge_platform = {"win64": "win64", "win32": "win32",
                     "mac-x64": "mac64", "mac-arm64": "mac64_m1",
                     "linux64": "linux64"}.get(slug, slug)
    version = None
    if browser_major:
        try:
            resp = requests.get(EDGE_LATEST_URL.format(major=browser_major), timeout=_HTTP_TIMEOUT)
            resp.encoding = "utf-16"  # 该接口返回 UTF-16 文本
            version = resp.text.strip()
        except Exception as e:
            log.warning("查询 Edge 驱动最新版本失败: %s", e)
    if not version:
        raise DriverNotFoundException(
            f"无法确定 Edge 驱动版本（浏览器大版本: {browser_major}），"
            "请手动下载 msedgedriver 并加入 PATH，或设置 WEBPILOT_EDGE_DRIVER"
        )
    return version, EDGE_DOWNLOAD_URL.format(version=version, platform=edge_platform)


def _resolve_gecko_driver_url() -> tuple[str, str]:
    data = requests.get(GECKO_RELEASES_URL, timeout=_HTTP_TIMEOUT).json()
    version = data["tag_name"]
    slug = _platform_slug()
    for asset in data.get("assets", []):
        name = asset["name"]
        if slug == "win64" and "win64" in name and name.endswith(".zip"):
            return version, asset["browser_download_url"]
        if slug == "win32" and "win32" in name and name.endswith(".zip"):
            return version, asset["browser_download_url"]
        if slug in ("mac-x64", "mac-arm64") and "macos-aarch64" in name and slug == "mac-arm64":
            return version, asset["browser_download_url"]
        if slug == "mac-x64" and "macos.tar.gz" in name:
            return version, asset["browser_download_url"]
        if slug == "linux64" and "linux64" in name:
            return version, asset["browser_download_url"]
    raise DriverNotFoundException(f"geckodriver {version} 没有匹配平台 {slug} 的安装包")


def _download_driver(browser: str, browser_version: Optional[str]) -> str:
    major = browser_version.split(".")[0] if browser_version else None
    if browser == "chrome":
        version, url = _resolve_chrome_driver_url(major)
    elif browser == "edge":
        version, url = _resolve_edge_driver_url(major)
    elif browser == "firefox":
        version, url = _resolve_gecko_driver_url()
    else:
        raise DriverNotFoundException(f"不支持的浏览器: {browser}")

    log.info("下载 %s 驱动 %s: %s", browser, version, url)
    target_dir = _cache_root() / browser / version
    target_dir.mkdir(parents=True, exist_ok=True)
    exe_path = target_dir / DRIVER_NAMES[browser]

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "driver_pkg"
        try:
            with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT) as resp:
                resp.raise_for_status()
                with open(archive, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
        except Exception as e:
            raise DriverNotFoundException(
                f"驱动下载失败: {e}\n可手动下载后放入 PATH，或设置环境变量 "
                f"WEBPILOT_{browser.upper()}_DRIVER 指向驱动路径。"
            )

        if url.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                member = next(m for m in zf.namelist() if m.endswith(DRIVER_NAMES[browser]))
                with zf.open(member) as src, open(exe_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        else:  # tar.gz (geckodriver mac/linux)
            import tarfile
            with tarfile.open(archive) as tf:
                member = next(m for m in tf.getnames() if m.endswith(DRIVER_NAMES[browser]))
                src = tf.extractfile(member)
                with open(exe_path, "wb") as dst:
                    dst.write(src.read())

    if sys.platform != "win32":
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    log.info("驱动已缓存到: %s", exe_path)
    return str(exe_path)


def _version_key(v: str) -> tuple:
    return tuple(int(p) for p in v.split(".") if p.isdigit())
