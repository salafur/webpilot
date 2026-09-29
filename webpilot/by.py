"""元素定位策略。

W3C WebDriver 协议原生只支持 5 种定位方式：
css selector / xpath / link text / partial link text / tag name。
ID、NAME、CLASS_NAME 在客户端被翻译成等价的 CSS 选择器。
"""
from __future__ import annotations

from typing import Tuple


class By:
    """定位策略常量，用法与 Selenium 保持一致：driver.find_element(By.ID, "kw")"""

    ID = "id"
    XPATH = "xpath"
    LINK_TEXT = "link text"
    PARTIAL_LINK_TEXT = "partial link text"
    NAME = "name"
    TAG_NAME = "tag name"
    CLASS_NAME = "class name"
    CSS_SELECTOR = "css selector"

    _W3C_STRATEGIES = {XPATH, LINK_TEXT, PARTIAL_LINK_TEXT, CSS_SELECTOR}

    @staticmethod
    def to_w3c(by: str, value: str) -> Tuple[str, str]:
        """把用户友好的定位方式翻译成 W3C 协议要求的 (using, value)。"""
        if by == By.ID:
            return By.CSS_SELECTOR, f'[id="{value}"]'
        if by == By.NAME:
            return By.CSS_SELECTOR, f'[name="{value}"]'
        if by == By.CLASS_NAME:
            return By.CSS_SELECTOR, f".{value}"
        if by == By.TAG_NAME:
            return By.CSS_SELECTOR, value
        if by in By._W3C_STRATEGIES:
            return by, value
        raise ValueError(
            f"不支持的定位方式: {by!r}，可选: id/xpath/link text/"
            f"partial link text/name/tag name/class name/css selector"
        )
