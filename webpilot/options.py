"""浏览器启动选项（对应 Selenium 的 Options）。

最终会被序列化成 W3C capabilities，随 POST /session 发给驱动。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class Options:
    """通用选项基类。厂商私有配置放在 <vendor>:<name>Options 键下。"""

    browser_name: Optional[str] = None
    vendor_key: Optional[str] = None  # 如 "goog:chromeOptions"

    def __init__(self) -> None:
        self._arguments: List[str] = []
        self._binary: Optional[str] = None
        self._vendor_options: Dict[str, Any] = {}

    # ---- 链式 API ----

    def add_argument(self, argument: str) -> "Options":
        """添加命令行启动参数，如 "--window-size=1280,800"。"""
        self._arguments.append(argument)
        return self

    @property
    def binary_location(self) -> Optional[str]:
        return self._binary

    @binary_location.setter
    def binary_location(self, path: str) -> None:
        self._binary = path

    @property
    def headless(self) -> bool:
        return any("headless" in a for a in self._arguments)

    @headless.setter
    def headless(self, enabled: bool) -> None:
        if enabled and not self.headless:
            self.add_argument(self._headless_arg())
        elif not enabled and self.headless:
            self._arguments = [a for a in self._arguments if "headless" not in a]

    def _headless_arg(self) -> str:
        return "--headless"

    def set_vendor_option(self, key: str, value: Any) -> "Options":
        """设置厂商私有选项（对应 Selenium 的 experimental option）。"""
        self._vendor_options[key] = value
        return self

    # ---- 序列化 ----

    def to_capabilities(self) -> Dict[str, Any]:
        caps: Dict[str, Any] = {}
        if self.browser_name:
            caps["browserName"] = self.browser_name
        vendor: Dict[str, Any] = dict(self._vendor_options)
        if self._arguments:
            vendor["args"] = list(self._arguments)
        if self._binary:
            vendor["binary"] = self._binary
        if vendor and self.vendor_key:
            caps[self.vendor_key] = vendor
        return caps


class ChromeOptions(Options):
    browser_name = "chrome"
    vendor_key = "goog:chromeOptions"

    def _headless_arg(self) -> str:
        return "--headless=new"

    def add_experimental_option(self, key: str, value: Any) -> "ChromeOptions":
        """如 prefs（下载目录）、excludeSwitches、debuggerAddress 等。"""
        return self.set_vendor_option(key, value)


class EdgeOptions(Options):
    browser_name = "MicrosoftEdge"
    vendor_key = "ms:edgeOptions"

    def _headless_arg(self) -> str:
        return "--headless=new"

    def add_experimental_option(self, key: str, value: Any) -> "EdgeOptions":
        return self.set_vendor_option(key, value)


class FirefoxOptions(Options):
    browser_name = "firefox"
    vendor_key = "moz:firefoxOptions"

    def _headless_arg(self) -> str:
        return "-headless"

    def add_preference(self, name: str, value: Any) -> "FirefoxOptions":
        prefs = self._vendor_options.setdefault("prefs", {})
        prefs[name] = value
        return self
