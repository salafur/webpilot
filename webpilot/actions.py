"""动作链（对应 Selenium 的 ActionChains）。

基于 W3C Actions API：把鼠标/键盘/滚轮事件按时间轴编排后一次性
POST /actions 发给浏览器，浏览器按顺序回放，模拟真实用户操作。
支持链式调用：

    ActionChains(driver).move_to_element(menu).pause(0.5).click(item).perform()
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .element import ELEMENT_KEY, Element

_POINTER_BUTTONS = {"left": 0, "middle": 1, "right": 2}


class ActionChains:
    def __init__(self, driver, duration: int = 250):
        self._driver = driver
        self._duration = duration  # 指针移动耗时（毫秒），让轨迹更像真人
        self._pointer: Dict[str, Any] = {
            "type": "pointer",
            "id": "mouse",
            "parameters": {"pointerType": "mouse"},
            "actions": [],
        }
        self._key: Dict[str, Any] = {"type": "key", "id": "keyboard", "actions": []}
        self._wheel: Dict[str, Any] = {"type": "wheel", "id": "wheel", "actions": []}

    # ---- 指针（鼠标） ----

    def _origin(self, element: Optional[Element]) -> Any:
        return {ELEMENT_KEY: element.id} if element is not None else "viewport"

    def move_to_element(self, element: Element) -> "ActionChains":
        """把鼠标移动到元素中心。"""
        self._pointer["actions"].append(
            {"type": "pointerMove", "duration": self._duration,
             "origin": self._origin(element), "x": 0, "y": 0}
        )
        return self

    def move_by_offset(self, xoffset: int, yoffset: int) -> "ActionChains":
        self._pointer["actions"].append(
            {"type": "pointerMove", "duration": self._duration,
             "origin": "pointer", "x": xoffset, "y": yoffset}
        )
        return self

    def click(self, element: Optional[Element] = None) -> "ActionChains":
        if element is not None:
            self.move_to_element(element)
        self._pointer["actions"].append({"type": "pointerDown", "button": 0})
        self._pointer["actions"].append({"type": "pointerUp", "button": 0})
        return self

    def click_and_hold(self, element: Optional[Element] = None) -> "ActionChains":
        if element is not None:
            self.move_to_element(element)
        self._pointer["actions"].append({"type": "pointerDown", "button": 0})
        return self

    def release(self) -> "ActionChains":
        self._pointer["actions"].append({"type": "pointerUp", "button": 0})
        return self

    def double_click(self, element: Optional[Element] = None) -> "ActionChains":
        if element is not None:
            self.move_to_element(element)
        for _ in range(2):
            self._pointer["actions"].append({"type": "pointerDown", "button": 0})
            self._pointer["actions"].append({"type": "pointerUp", "button": 0})
        return self

    def context_click(self, element: Optional[Element] = None) -> "ActionChains":
        """右键点击。"""
        if element is not None:
            self.move_to_element(element)
        self._pointer["actions"].append({"type": "pointerDown", "button": 2})
        self._pointer["actions"].append({"type": "pointerUp", "button": 2})
        return self

    def drag_and_drop(self, source: Element, target: Element) -> "ActionChains":
        return (
            self.move_to_element(source)
            .click_and_hold()
            .move_to_element(target)
            .release()
        )

    def drag_and_drop_by_offset(self, source: Element, xoffset: int, yoffset: int) -> "ActionChains":
        return (
            self.move_to_element(source)
            .click_and_hold()
            .move_by_offset(xoffset, yoffset)
            .release()
        )

    # ---- 键盘 ----

    def key_down(self, value: str, element: Optional[Element] = None) -> "ActionChains":
        if element is not None:
            self.click(element)
        self._key["actions"].append({"type": "keyDown", "value": value})
        return self

    def key_up(self, value: str) -> "ActionChains":
        self._key["actions"].append({"type": "keyUp", "value": value})
        return self

    def send_keys(self, keys: str) -> "ActionChains":
        for ch in keys:
            self._key["actions"].append({"type": "keyDown", "value": ch})
            self._key["actions"].append({"type": "keyUp", "value": ch})
        return self

    def send_keys_to_element(self, element: Element, keys: str) -> "ActionChains":
        return self.click(element).send_keys(keys)

    # ---- 滚轮 ----

    def scroll_by_amount(self, delta_x: int, delta_y: int) -> "ActionChains":
        """滚动页面（像素）。"""
        self._wheel["actions"].append(
            {"type": "scroll", "x": 0, "y": 0,
             "deltaX": delta_x, "deltaY": delta_y, "origin": "viewport", "duration": self._duration}
        )
        return self

    def scroll_to_element(self, element: Element) -> "ActionChains":
        """滚动直到元素可见。"""
        self._wheel["actions"].append(
            {"type": "scroll", "x": 0, "y": 0,
             "deltaX": 0, "deltaY": 0, "origin": self._origin(element), "duration": self._duration}
        )
        return self

    def scroll_from_origin(self, element: Element, delta_x: int, delta_y: int) -> "ActionChains":
        """以元素位置为原点滚动。"""
        self._wheel["actions"].append(
            {"type": "scroll", "x": 0, "y": 0,
             "deltaX": delta_x, "deltaY": delta_y,
             "origin": self._origin(element), "duration": self._duration}
        )
        return self

    # ---- 通用 ----

    def pause(self, seconds: float) -> "ActionChains":
        ms = int(seconds * 1000)
        for device in (self._pointer, self._key, self._wheel):
            device["actions"].append({"type": "pause", "duration": ms})
        return self

    def perform(self) -> None:
        """把编排好的动作一次性发给浏览器执行，执行后清空队列。"""
        payload: List[Dict[str, Any]] = [
            d for d in (self._pointer, self._key, self._wheel) if d["actions"]
        ]
        if payload:
            self._driver._execute("POST", "/actions", {"actions": payload})
        self.reset_actions()

    def reset_actions(self) -> None:
        """清空本地队列并释放浏览器端的按键状态。"""
        for device in (self._pointer, self._key, self._wheel):
            device["actions"] = []
        try:
            self._driver._execute("DELETE", "/actions")
        except Exception:
            pass
