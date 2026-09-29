"""常用等待条件（对应 Selenium 的 expected_conditions）。

每个条件都是一个可调用对象，配合 WebDriverWait 使用：

    wait = WebDriverWait(driver, 10)
    el = wait.until(EC.element_to_be_clickable((By.ID, "submit")))
    el.click()
"""
from __future__ import annotations

from typing import List, Tuple

from .by import By
from .element import Element
from .exceptions import NoAlertPresentException, StaleElementReferenceException

Locator = Tuple[str, str]


class presence_of_element_located:
    """元素存在于 DOM（不要求可见）。"""

    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver):
        return driver.find_element(*self.locator)


class presence_of_all_elements_located:
    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver) -> List[Element]:
        return driver.find_elements(*self.locator)


class visibility_of_element_located:
    """元素存在且可见。"""

    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver):
        el = driver.find_element(*self.locator)
        return el if el.is_displayed() else False


class invisibility_of_element_located:
    """元素不可见或已从 DOM 移除。"""

    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver):
        try:
            el = driver.find_element(*self.locator)
            return not el.is_displayed()
        except Exception:
            return True


class element_to_be_clickable:
    """元素可见且可用（可以点击）。"""

    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver):
        el = driver.find_element(*self.locator)
        return el if (el.is_displayed() and el.is_enabled()) else False


class element_to_be_selected:
    def __init__(self, element: Element):
        self.element = element

    def __call__(self, driver):
        return self.element.is_selected()


class text_to_be_present_in_element:
    def __init__(self, locator: Locator, text: str):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        return self.text in driver.find_element(*self.locator).text


class text_to_be_present_in_element_value:
    def __init__(self, locator: Locator, text: str):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        value = driver.find_element(*self.locator).get_property("value")
        return isinstance(value, str) and self.text in value


class title_is:
    def __init__(self, title: str):
        self.title = title

    def __call__(self, driver):
        return driver.title == self.title


class title_contains:
    def __init__(self, title: str):
        self.title = title

    def __call__(self, driver):
        return self.title in driver.title


class url_contains:
    def __init__(self, url: str):
        self.url = url

    def __call__(self, driver):
        return self.url in driver.current_url


class url_to_be:
    def __init__(self, url: str):
        self.url = url

    def __call__(self, driver):
        return driver.current_url == self.url


class number_of_windows_to_be:
    def __init__(self, num: int):
        self.num = num

    def __call__(self, driver):
        return len(driver.window_handles) == self.num


class alert_is_present:
    def __call__(self, driver):
        try:
            return driver.switch_to.alert
        except NoAlertPresentException:
            return False


class staleness_of:
    """等待元素引用失效（常用于等待旧页面卸载）。"""

    def __init__(self, element: Element):
        self.element = element

    def __call__(self, driver):
        try:
            self.element.is_enabled()
            return False
        except StaleElementReferenceException:
            return True


class frame_to_be_available_and_switch_to_it:
    def __init__(self, locator: Locator):
        self.locator = locator

    def __call__(self, driver):
        try:
            driver.switch_to.frame(driver.find_element(*self.locator))
            return True
        except Exception:
            return False
