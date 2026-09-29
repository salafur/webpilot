"""页面元素封装（对应 Selenium 的 WebElement）。"""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, Dict, List

from .by import By

if TYPE_CHECKING:
    from .driver import Driver

# W3C 规范定义的元素引用键
ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
# 旧版 JSON Wire 协议的键，部分驱动仍可能返回
LEGACY_ELEMENT_KEY = "ELEMENT"


def extract_element_id(raw: Dict[str, Any]) -> str:
    if ELEMENT_KEY in raw:
        return raw[ELEMENT_KEY]
    if LEGACY_ELEMENT_KEY in raw:
        return raw[LEGACY_ELEMENT_KEY]
    raise ValueError(f"无法从返回值中解析元素引用: {raw}")


class Element:
    """页面上一个 DOM 元素的引用。属性/文本等都是实时向浏览器查询的。"""

    def __init__(self, driver: "Driver", element_id: str):
        self._driver = driver
        self.id = element_id

    def _cmd(self, method: str, suffix: str = "", body: Dict[str, Any] = None) -> Any:
        return self._driver._execute(method, f"/element/{self.id}{suffix}", body)

    # ---- 交互 ----

    def click(self) -> None:
        """模拟真实鼠标点击（会先滚动到可视区域并检查可交互性）。"""
        self._cmd("POST", "/click", {})

    def clear(self) -> None:
        """清空输入框内容。"""
        self._cmd("POST", "/clear", {})

    def send_keys(self, *values: Any) -> None:
        """模拟键盘输入，可混合文本与 Keys 特殊键：el.send_keys("abc", Keys.ENTER)"""
        text = "".join(str(v) for v in values)
        self._cmd("POST", "/value", {"text": text, "value": list(text)})

    def submit(self) -> None:
        """提交元素所在的 form（W3C 已移除原生 submit，用 JS 实现）。"""
        self._driver.execute_script(
            "var f=arguments[0].form; if(f){f.submit()} else "
            "{arguments[0].dispatchEvent(new Event('submit',{bubbles:true}))}",
            self,
        )

    # ---- 状态与属性 ----

    @property
    def text(self) -> str:
        return self._cmd("GET", "/text")

    @property
    def tag_name(self) -> str:
        return self._cmd("GET", "/name")

    def get_attribute(self, name: str) -> Any:
        """获取 HTML attribute；布尔属性返回 "true"/None。"""
        return self._cmd("GET", f"/attribute/{name}")

    def get_property(self, name: str) -> Any:
        """获取 JS property（如 input.value 的实时值）。"""
        return self._cmd("GET", f"/property/{name}")

    def value_of_css_property(self, name: str) -> str:
        return self._cmd("GET", f"/css/{name}")

    def is_displayed(self) -> bool:
        return bool(self._cmd("GET", "/displayed"))

    def is_enabled(self) -> bool:
        return bool(self._cmd("GET", "/enabled"))

    def is_selected(self) -> bool:
        return bool(self._cmd("GET", "/selected"))

    @property
    def rect(self) -> Dict[str, Any]:
        """返回 {'x','y','width','height'}。"""
        return self._cmd("GET", "/rect")

    @property
    def location(self) -> Dict[str, float]:
        r = self.rect
        return {"x": r["x"], "y": r["y"]}

    @property
    def size(self) -> Dict[str, float]:
        r = self.rect
        return {"width": r["width"], "height": r["height"]}

    # ---- 子元素查找 ----

    def find_element(self, by: str = By.CSS_SELECTOR, value: str = None) -> "Element":
        if value is None:
            value, by = by, By.CSS_SELECTOR
        using, selector = By.to_w3c(by, value)
        raw = self._cmd("POST", "/element", {"using": using, "value": selector})
        return Element(self._driver, extract_element_id(raw))

    def find_elements(self, by: str = By.CSS_SELECTOR, value: str = None) -> List["Element"]:
        if value is None:
            value, by = by, By.CSS_SELECTOR
        using, selector = By.to_w3c(by, value)
        raw_list = self._cmd("POST", "/elements", {"using": using, "value": selector}) or []
        return [Element(self._driver, extract_element_id(r)) for r in raw_list]

    # ---- 截图 ----

    def screenshot_as_base64(self) -> str:
        return self._cmd("GET", "/screenshot")

    def save_screenshot(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.screenshot_as_base64()))

    def __repr__(self) -> str:
        return f"<Element {self.id[:8]}...>"
