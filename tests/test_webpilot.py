"""WebPilot 端到端测试。

用本地 HTML 文件（file:// 协议）做被测页面，不依赖外网。
需要一个可用的浏览器（自动按 Chrome -> Edge -> Firefox 顺序探测），
都没有则整体 skip。

运行: pytest tests/ -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webpilot import ActionChains, By, Chrome, Driver, Edge, Firefox, Keys, WebDriverWait
from webpilot import expected_conditions as EC
from webpilot.exceptions import NoSuchElementException, WebPilotException

TEST_PAGE = """
<!DOCTYPE html>
<html>
<head><title>WebPilot Test Page</title></head>
<body>
  <h1 id="title">Hello WebPilot</h1>
  <input id="name" name="username" type="text" placeholder="type here">
  <button id="btn" onclick="document.getElementById('output').textContent =
      'clicked:' + document.getElementById('name').value">Click Me</button>
  <div id="output"></div>
  <a id="link" href="#anchor">Jump to anchor</a>
  <ul class="items">
    <li>item-1</li><li>item-2</li><li>item-3</li>
  </ul>
  <div style="height:2000px"></div>
  <p id="anchor">bottom</p>
  <script>
    setTimeout(function() {
      var d = document.createElement('div');
      d.id = 'lazy'; d.textContent = 'lazy loaded';
      document.body.appendChild(d);
    }, 800);
  </script>
</body>
</html>
"""


@pytest.fixture(scope="session")
def test_page_url(tmp_path_factory):
    page = tmp_path_factory.mktemp("pages") / "test.html"
    page.write_text(TEST_PAGE, encoding="utf-8")
    return page.as_uri()


@pytest.fixture(scope="session")
def driver():
    instance = None
    errors = []
    for cls in (Chrome, Edge, Firefox):
        try:
            instance = cls(headless=True)
            break
        except WebPilotException as e:
            errors.append(f"{cls.__name__}: {e}")
    if instance is None:
        pytest.skip("没有可用的浏览器/驱动:\n" + "\n".join(errors))
    instance.set_window_size(1024, 768)
    yield instance
    instance.quit()


class TestNavigation:
    def test_get_and_title(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        assert driver.title == "WebPilot Test Page"
        assert driver.current_url.startswith("file://")

    def test_back_forward(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        driver.get("about:blank")
        driver.back()
        assert "test.html" in driver.current_url
        driver.forward()
        assert driver.current_url == "about:blank"


class TestElementInteraction:
    def test_type_and_click(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        driver.find_element(By.ID, "name").send_keys("荣淏")
        driver.find_element(By.ID, "btn").click()
        assert driver.find_element(By.ID, "output").text == "clicked:荣淏"

    def test_send_special_keys(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        box = driver.find_element(By.ID, "name")
        box.send_keys("abc", Keys.BACKSPACE)
        assert box.get_property("value") == "ab"

    def test_clear(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        box = driver.find_element(By.ID, "name")
        box.send_keys("something")
        box.clear()
        assert box.get_property("value") == ""

    def test_find_elements_and_text(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        items = driver.find_elements(By.CSS_SELECTOR, ".items li")
        assert [i.text for i in items] == ["item-1", "item-2", "item-3"]

    def test_no_such_element(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        with pytest.raises(NoSuchElementException):
            driver.find_element(By.ID, "not-exist")
        assert driver.find_elements(By.ID, "not-exist") == []

    def test_xpath(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        h1 = driver.find_element(By.XPATH, "//h1[@id='title']")
        assert h1.text == "Hello WebPilot"

    def test_element_state(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        btn = driver.find_element(By.ID, "btn")
        assert btn.is_displayed() and btn.is_enabled()
        assert btn.tag_name == "button"


class TestWaits:
    def test_explicit_wait_for_lazy_element(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        wait = WebDriverWait(driver, timeout=5, poll_frequency=0.2)
        lazy = wait.until(EC.presence_of_element_located((By.ID, "lazy")))
        assert lazy.text == "lazy loaded"


class TestActions:
    def test_scroll_to_element(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        anchor = driver.find_element(By.ID, "anchor")
        ActionChains(driver).scroll_to_element(anchor).perform()
        y = driver.execute_script("return window.scrollY")
        assert y > 500

    def test_execute_script(self, driver: Driver, test_page_url):
        driver.get(test_page_url)
        result = driver.execute_script("return 1 + 2")
        assert result == 3
        el = driver.execute_script("return document.getElementById('title')")
        assert el.text == "Hello WebPilot"


class TestScreenshot:
    def test_save_screenshot(self, driver: Driver, test_page_url, tmp_path):
        driver.get(test_page_url)
        out = tmp_path / "shot.png"
        driver.save_screenshot(out)
        assert out.exists() and out.stat().st_size > 1000
        assert out.read_bytes()[:4] == b"\x89PNG"
