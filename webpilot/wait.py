"""显式等待（对应 Selenium 的 WebDriverWait）。

轮询调用一个条件函数，直到返回真值或超时。比 time.sleep 可靠得多：
条件满足立即继续，不满足才等到超时。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Tuple, Type

from .exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

# 轮询期间允许吞掉的异常（元素还没渲染出来属于正常中间状态）
_DEFAULT_IGNORED: Tuple[Type[Exception], ...] = (
    NoSuchElementException,
    StaleElementReferenceException,
)


class WebDriverWait:
    def __init__(
        self,
        driver,
        timeout: float = 10.0,
        poll_frequency: float = 0.5,
        ignored_exceptions: Tuple[Type[Exception], ...] = None,
    ):
        self._driver = driver
        self._timeout = timeout
        self._poll = poll_frequency
        self._ignored = ignored_exceptions if ignored_exceptions is not None else _DEFAULT_IGNORED

    def until(self, method: Callable, message: str = "") -> Any:
        """每 poll_frequency 秒调用一次 method(driver)，返回第一个真值。"""
        end_time = time.monotonic() + self._timeout
        while True:
            try:
                value = method(self._driver)
                if value:
                    return value
            except self._ignored:
                pass
            if time.monotonic() > end_time:
                break
            time.sleep(self._poll)
        raise TimeoutException(
            message or f"等待 {self._timeout}s 超时，条件仍未满足: {method!r}"
        )

    def until_not(self, method: Callable, message: str = "") -> Any:
        """与 until 相反：等到 method 返回假值。"""
        end_time = time.monotonic() + self._timeout
        while True:
            try:
                value = method(self._driver)
                if not value:
                    return value
            except self._ignored:
                return True
            if time.monotonic() > end_time:
                break
            time.sleep(self._poll)
        raise TimeoutException(message or f"等待 {self._timeout}s 超时，条件仍然成立")
