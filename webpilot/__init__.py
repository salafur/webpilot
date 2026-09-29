"""WebPilot —— 纯 Python 实现的浏览器自动化框架。

不依赖 Selenium，直接实现 W3C WebDriver 协议客户端，
驱动真实 Chrome / Edge / Firefox 执行点击、输入、翻页等用户行为。

快速上手：

    from webpilot import Chrome, By

    with Chrome() as driver:
        driver.get("https://www.bing.com")
        driver.find_element(By.ID, "sb_form_q").send_keys("WebPilot")
        driver.find_element(By.ID, "sb_form_q").submit()
"""

from .actions import ActionChains
from .by import By
from .driver import Alert, Chrome, Driver, Edge, Firefox
from .element import Element
from .exceptions import (
    DriverNotFoundException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    InvalidArgumentException,
    InvalidSelectorException,
    InvalidSessionIdException,
    JavascriptException,
    MoveTargetOutOfBoundsException,
    NoAlertPresentException,
    NoSuchElementException,
    NoSuchFrameException,
    NoSuchWindowException,
    SessionNotCreatedException,
    StaleElementReferenceException,
    TimeoutException,
    WebPilotException,
)
from .keys import Keys
from .options import ChromeOptions, EdgeOptions, FirefoxOptions, Options
from .wait import WebDriverWait
from . import expected_conditions as EC

__version__ = "1.0.0"
__all__ = [
    "Chrome", "Edge", "Firefox", "Driver", "Element", "Alert",
    "By", "Keys", "ActionChains", "WebDriverWait", "EC",
    "Options", "ChromeOptions", "EdgeOptions", "FirefoxOptions",
    "WebPilotException", "NoSuchElementException", "TimeoutException",
    "StaleElementReferenceException", "ElementNotInteractableException",
    "ElementClickInterceptedException", "InvalidSelectorException",
    "InvalidArgumentException", "JavascriptException",
    "MoveTargetOutOfBoundsException", "NoAlertPresentException",
    "NoSuchFrameException", "NoSuchWindowException",
    "SessionNotCreatedException", "InvalidSessionIdException",
    "DriverNotFoundException",
]
