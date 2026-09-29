"""WebPilot 异常体系。

所有异常都继承自 WebPilotException，并携带 WebDriver 服务端返回的
error 码（如 "no such element"），方便精确捕获与排查。
"""
from __future__ import annotations

from typing import Optional


class WebPilotException(Exception):
    """WebPilot 所有异常的基类。"""

    def __init__(self, message: str = "", error: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error = error

    def __str__(self) -> str:
        if self.error:
            return f"[{self.error}] {self.message}"
        return self.message


# ---- 协议层错误（由服务端 error 码映射而来） ----

class NoSuchElementException(WebPilotException):
    """找不到元素。"""


class NoSuchWindowException(WebPilotException):
    """找不到窗口 / 标签页。"""


class NoSuchFrameException(WebPilotException):
    """找不到 iframe。"""


class NoAlertPresentException(WebPilotException):
    """当前没有弹窗（alert）。"""


class StaleElementReferenceException(WebPilotException):
    """元素引用已失效（页面刷新或 DOM 重建后旧引用不可用）。"""


class ElementNotInteractableException(WebPilotException):
    """元素不可交互（隐藏、禁用或被遮挡）。"""


class ElementClickInterceptedException(WebPilotException):
    """点击被其他元素拦截（通常是被弹层遮挡）。"""


class InvalidSelectorException(WebPilotException):
    """定位表达式非法（如 XPath 语法错误）。"""


class InvalidArgumentException(WebPilotException):
    """传给驱动的参数非法。"""


class JavascriptException(WebPilotException):
    """execute_script 注入的 JS 执行报错。"""


class MoveTargetOutOfBoundsException(WebPilotException):
    """鼠标移动目标超出可视区域。"""


# ---- 框架层错误（由 WebPilot 自身抛出） ----

class TimeoutException(WebPilotException):
    """显式等待超时。"""


class SessionNotCreatedException(WebPilotException):
    """创建浏览器会话失败（驱动未启动、版本不匹配等）。"""


class InvalidSessionIdException(WebPilotException):
    """会话已失效（浏览器被关闭后继续操作）。"""


class DriverNotFoundException(WebPilotException):
    """找不到浏览器驱动，且自动下载失败。"""


# W3C WebDriver 规范 error 码 -> 异常类 映射表
ERROR_MAP = {
    "no such element": NoSuchElementException,
    "no such window": NoSuchWindowException,
    "no such frame": NoSuchFrameException,
    "no such alert": NoAlertPresentException,
    "stale element reference": StaleElementReferenceException,
    "element not interactable": ElementNotInteractableException,
    "element click intercepted": ElementClickInterceptedException,
    "invalid selector": InvalidSelectorException,
    "invalid argument": InvalidArgumentException,
    "javascript error": JavascriptException,
    "move target out of bounds": MoveTargetOutOfBoundsException,
    "timeout": TimeoutException,
    "session not created": SessionNotCreatedException,
    "invalid session id": InvalidSessionIdException,
    "unable to locate element": NoSuchElementException,
}
