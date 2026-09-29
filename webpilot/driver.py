"""浏览器驱动核心（对应 Selenium 的 WebDriver）。

工作原理：
1. 启动本地驱动进程（chromedriver / msedgedriver / geckodriver），监听一个空闲端口
2. POST /session 创建会话，驱动拉起真实浏览器
3. 之后所有操作（导航/点击/输入/截图...）都是发往该端口的 HTTP 请求
4. quit() 时 DELETE /session 并回收驱动进程
"""
from __future__ import annotations

import base64
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import manager
from .by import By
from .element import ELEMENT_KEY, Element, extract_element_id
from .exceptions import NoAlertPresentException, SessionNotCreatedException, WebPilotException
from .logger import get_logger
from .options import ChromeOptions, EdgeOptions, FirefoxOptions, Options
from .session import CommandExecutor

log = get_logger()

_SESSION_START_TIMEOUT = 60.0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Alert:
    """浏览器原生弹窗（alert/confirm/prompt）。"""

    def __init__(self, driver: "Driver"):
        self._driver = driver

    @property
    def text(self) -> str:
        return self._driver._execute("GET", "/alert/text")

    def accept(self) -> None:
        self._driver._execute("POST", "/alert/accept", {})

    def dismiss(self) -> None:
        self._driver._execute("POST", "/alert/dismiss", {})

    def send_keys(self, text: str) -> None:
        self._driver._execute("POST", "/alert/text", {"text": text})


class _SwitchTo:
    """上下文切换：窗口 / iframe / 弹窗。"""

    def __init__(self, driver: "Driver"):
        self._driver = driver

    def window(self, handle_or_name: str) -> None:
        self._driver._execute("POST", "/window", {"handle": handle_or_name})

    def new_window(self, type_hint: str = "tab") -> None:
        """新建标签页（type_hint='window' 则新建窗口）并切换过去。"""
        self._driver._execute("POST", "/window/new", {"type": type_hint})

    def frame(self, frame_reference: Union[int, str, Element]) -> None:
        """切入 iframe，参数可以是索引、name/id 字符串或 iframe 元素。"""
        if isinstance(frame_reference, str):
            frame_reference = self._driver.find_element(By.CSS_SELECTOR, f"iframe#{frame_reference},iframe[name='{frame_reference}']")
        frame_id: Any = frame_reference
        if isinstance(frame_reference, Element):
            frame_id = {ELEMENT_KEY: frame_reference.id}
        self._driver._execute("POST", "/frame", {"id": frame_id})

    def parent_frame(self) -> None:
        self._driver._execute("POST", "/frame/parent", {})

    def default_content(self) -> None:
        """切回主文档。"""
        self._driver._execute("POST", "/frame", {"id": None})

    @property
    def alert(self) -> Alert:
        # 先探测一次，没有弹窗时立即抛 NoAlertPresentException
        self._driver._execute("GET", "/alert/text")
        return Alert(self._driver)


class Driver:
    """浏览器会话。不要直接实例化，使用 Chrome() / Edge() / Firefox()。"""

    browser_name: str = ""
    _options_class = Options

    def __init__(
        self,
        options: Optional[Options] = None,
        driver_path: Optional[str] = None,
        port: Optional[int] = None,
    ):
        options = options or self._options_class()
        executable = manager.ensure_driver(self.browser_name, driver_path)

        self._port = port or _free_port()
        self._process = self._start_service(executable, self._port)
        self._executor = CommandExecutor(f"http://127.0.0.1:{self._port}")
        self.session_id: Optional[str] = None
        self.capabilities: Dict[str, Any] = {}

        try:
            self._create_session(options)
        except Exception:
            self._kill_service()
            raise

    # ------------------------------------------------------------------
    # 服务进程管理
    # ------------------------------------------------------------------

    @staticmethod
    def _start_service(executable: str, port: int) -> subprocess.Popen:
        cmd = [executable, f"--port={port}"]
        log.info("启动驱动服务: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        # 等服务就绪
        import requests
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise SessionNotCreatedException(
                    f"驱动进程启动后立即退出 (exit={proc.returncode}): {executable}"
                )
            try:
                requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
                return proc
            except requests.RequestException:
                time.sleep(0.15)
        proc.kill()
        raise SessionNotCreatedException(f"驱动服务 15s 内未就绪: {executable}")

    def _create_session(self, options: Options) -> None:
        caps = options.to_capabilities()
        body = {"capabilities": {"alwaysMatch": caps}}
        value = self._executor.execute("POST", "/session", body)
        if not isinstance(value, dict) or "sessionId" not in value:
            raise SessionNotCreatedException(f"创建会话失败，驱动返回: {value}")
        self.session_id = value["sessionId"]
        self.capabilities = value.get("capabilities", {})
        log.info("会话已创建: %s (%s)", self.session_id,
                 self.capabilities.get("browserVersion", "?"))

    def _kill_service(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    # ------------------------------------------------------------------
    # 命令执行（所有请求都带 sessionId）
    # ------------------------------------------------------------------

    def _execute(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        return self._executor.execute(method, f"/session/{self.session_id}{path}", body)

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------

    def get(self, url: str) -> None:
        """打开 URL（会阻塞到页面 load 事件触发）。"""
        if not url.startswith(("http://", "https://", "file://", "data:", "about:")):
            url = "https://" + url
        self._execute("POST", "/url", {"url": url})

    def back(self) -> None:
        """后退一页。"""
        self._execute("POST", "/back", {})

    def forward(self) -> None:
        """前进一页。"""
        self._execute("POST", "/forward", {})

    def refresh(self) -> None:
        """刷新当前页。"""
        self._execute("POST", "/refresh", {})

    @property
    def title(self) -> str:
        return self._execute("GET", "/title")

    @property
    def current_url(self) -> str:
        return self._execute("GET", "/url")

    @property
    def page_source(self) -> str:
        return self._execute("GET", "/source")

    # ------------------------------------------------------------------
    # 元素查找
    # ------------------------------------------------------------------

    def find_element(self, by: str = By.CSS_SELECTOR, value: Optional[str] = None) -> Element:
        """查找单个元素，找不到抛 NoSuchElementException。

        简写：find_element("#kw") 等价于 find_element(By.CSS_SELECTOR, "#kw")。
        """
        if value is None:
            value, by = by, By.CSS_SELECTOR
        using, selector = By.to_w3c(by, value)
        raw = self._execute("POST", "/element", {"using": using, "value": selector})
        return Element(self, extract_element_id(raw))

    def find_elements(self, by: str = By.CSS_SELECTOR, value: Optional[str] = None) -> List[Element]:
        """查找所有匹配元素，找不到返回空列表（不抛异常）。"""
        if value is None:
            value, by = by, By.CSS_SELECTOR
        using, selector = By.to_w3c(by, value)
        raw_list = self._execute("POST", "/elements", {"using": using, "value": selector}) or []
        return [Element(self, extract_element_id(r)) for r in raw_list]

    # ------------------------------------------------------------------
    # JS 执行
    # ------------------------------------------------------------------

    def execute_script(self, script: str, *args: Any) -> Any:
        """在当前页面执行同步 JS，元素会被自动序列化/反序列化。

        driver.execute_script("arguments[0].scrollIntoView()", el)
        """
        return self._convert_result(
            self._execute("POST", "/execute/sync",
                          {"script": script, "args": [self._convert_arg(a) for a in args]})
        )

    def execute_async_script(self, script: str, *args: Any) -> Any:
        """执行异步 JS（脚本最后需调用 arguments[arguments.length-1] 回调）。"""
        return self._convert_result(
            self._execute("POST", "/execute/async",
                          {"script": script, "args": [self._convert_arg(a) for a in args]})
        )

    @staticmethod
    def _convert_arg(arg: Any) -> Any:
        if isinstance(arg, Element):
            return {ELEMENT_KEY: arg.id}
        if isinstance(arg, (list, tuple)):
            return [Driver._convert_arg(a) for a in arg]
        if isinstance(arg, dict):
            return {k: Driver._convert_arg(v) for k, v in arg.items()}
        return arg

    def _convert_result(self, value: Any) -> Any:
        if isinstance(value, dict):
            if ELEMENT_KEY in value:
                return Element(self, value[ELEMENT_KEY])
            return {k: self._convert_result(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._convert_result(v) for v in value]
        return value

    # ------------------------------------------------------------------
    # 截图
    # ------------------------------------------------------------------

    def save_screenshot(self, path: Union[str, Path]) -> None:
        """整页可视区域截图，保存为 PNG。"""
        data = self._execute("GET", "/screenshot")
        Path(path).write_bytes(base64.b64decode(data))

    def get_screenshot_as_base64(self) -> str:
        return self._execute("GET", "/screenshot")

    # ------------------------------------------------------------------
    # 窗口
    # ------------------------------------------------------------------

    def set_window_size(self, width: int, height: int) -> None:
        self._execute("POST", "/window/rect", {"width": width, "height": height})

    def get_window_size(self) -> Dict[str, int]:
        rect = self._execute("GET", "/window/rect")
        return {"width": rect["width"], "height": rect["height"]}

    def maximize_window(self) -> None:
        self._execute("POST", "/window/maximize", {})

    def minimize_window(self) -> None:
        self._execute("POST", "/window/minimize", {})

    def fullscreen_window(self) -> None:
        self._execute("POST", "/window/fullscreen", {})

    @property
    def current_window_handle(self) -> str:
        return self._execute("GET", "/window")

    @property
    def window_handles(self) -> List[str]:
        return self._execute("GET", "/window/handles")

    @property
    def switch_to(self) -> _SwitchTo:
        return _SwitchTo(self)

    def close(self) -> None:
        """关闭当前标签页（浏览器进程可能仍然存活）。"""
        self._execute("DELETE", "/window")

    # ------------------------------------------------------------------
    # Cookie / 超时
    # ------------------------------------------------------------------

    def get_cookies(self) -> List[Dict[str, Any]]:
        return self._execute("GET", "/cookie")

    def get_cookie(self, name: str) -> Optional[Dict[str, Any]]:
        return self._execute("GET", f"/cookie/{name}")

    def add_cookie(self, cookie: Dict[str, Any]) -> None:
        self._execute("POST", "/cookie", {"cookie": cookie})

    def delete_cookie(self, name: str) -> None:
        self._execute("DELETE", f"/cookie/{name}")

    def delete_all_cookies(self) -> None:
        self._execute("DELETE", "/cookie")

    def implicitly_wait(self, seconds: float) -> None:
        """隐式等待：find_element 找不到时最多重试这么久。"""
        self._execute("POST", "/timeouts", {"implicit": int(seconds * 1000)})

    def set_page_load_timeout(self, seconds: float) -> None:
        self._execute("POST", "/timeouts", {"pageLoad": int(seconds * 1000)})

    def set_script_timeout(self, seconds: float) -> None:
        self._execute("POST", "/timeouts", {"script": int(seconds * 1000)})

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """关闭浏览器并销毁会话、回收驱动进程。"""
        if self.session_id:
            try:
                self._executor.execute("DELETE", f"/session/{self.session_id}")
            except Exception as e:
                log.warning("销毁会话时出错（忽略）: %s", e)
            self.session_id = None
        self._executor.close()
        self._kill_service()

    def __enter__(self) -> "Driver":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.quit()

    def __del__(self):
        try:
            self.quit()
        except Exception:
            pass


class Chrome(Driver):
    """谷歌浏览器。

    driver = Chrome()                        # 自动下载匹配的 chromedriver
    driver = Chrome(headless=True)           # 无头模式
    driver = Chrome(options=ChromeOptions()) # 自定义选项
    """

    browser_name = "chrome"
    _options_class = ChromeOptions

    def __init__(self, options: Optional[ChromeOptions] = None,
                 driver_path: Optional[str] = None, headless: bool = False):
        options = options or ChromeOptions()
        if headless:
            options.headless = True
        super().__init__(options, driver_path)


class Edge(Driver):
    """微软 Edge 浏览器，用法同 Chrome。"""

    browser_name = "edge"
    _options_class = EdgeOptions

    def __init__(self, options: Optional[EdgeOptions] = None,
                 driver_path: Optional[str] = None, headless: bool = False):
        options = options or EdgeOptions()
        if headless:
            options.headless = True
        super().__init__(options, driver_path)


class Firefox(Driver):
    """火狐浏览器，用法同 Chrome。"""

    browser_name = "firefox"
    _options_class = FirefoxOptions

    def __init__(self, options: Optional[FirefoxOptions] = None,
                 driver_path: Optional[str] = None, headless: bool = False):
        options = options or FirefoxOptions()
        if headless:
            options.headless = True
        super().__init__(options, driver_path)
