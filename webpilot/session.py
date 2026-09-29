"""W3C WebDriver 协议 HTTP 客户端。

WebDriver 的本质就是一个 REST 服务：chromedriver / msedgedriver /
geckodriver 启动后在本地监听一个端口，客户端按规范发 HTTP 请求，
驱动再把指令翻译成浏览器操作。本模块就是这个 REST 客户端。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from .exceptions import ERROR_MAP, WebPilotException
from .logger import get_logger

log = get_logger()


class CommandExecutor:
    """负责把命令序列化成 HTTP 请求发给驱动，并把错误码映射成异常。"""

    def __init__(self, remote_url: str, timeout: float = 120.0):
        self.remote_url = remote_url.rstrip("/")
        self.timeout = timeout
        # 注意：这里刻意不用 requests.Session()。
        # 实测 chromedriver 的 HTTP 服务在复用 keep-alive 连接时，
        # 第二条命令会解析错乱并返回 400 "unhandled request"，
        # 每条命令独立建连（requests.request 一次性请求）可以稳定规避。
        self._default_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
        }

    def execute(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        url = self.remote_url + path
        log.debug(">> %s %s %s", method, path, body if body is not None else "")

        try:
            resp = requests.request(
                method, url, json=body, headers=self._default_headers,
                timeout=self.timeout,
            )
        except requests.ConnectionError as e:
            raise WebPilotException(f"无法连接 WebDriver 服务: {url}，驱动进程可能已退出: {e}")
        except requests.Timeout:
            raise WebPilotException(f"请求超时: {method} {path}")

        try:
            payload = resp.json()
        except ValueError:
            raise WebPilotException(
                f"驱动返回了非 JSON 响应 (HTTP {resp.status_code}): {resp.text[:300]}"
            )

        value = payload.get("value")
        log.debug("<< %s", str(value)[:300])

        if resp.status_code >= 400 or (isinstance(value, dict) and "error" in value):
            error, message = "unknown error", str(value)
            if isinstance(value, dict):
                error = value.get("error", error)
                message = value.get("message", message)
            exc_cls = ERROR_MAP.get(error, WebPilotException)
            raise exc_cls(message, error=error)

        return value

    def close(self) -> None:
        """保留给调用方的清理钩子（当前实现无线程/连接资源）。"""

