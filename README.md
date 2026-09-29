# WebPilot 🌐

纯 Python 实现的浏览器自动化框架 —— **不依赖 Selenium**，自己实现 W3C WebDriver 协议客户端，用代码驱动真实的 Chrome / Edge / Firefox 执行点击、输入、滚动、翻页等用户行为。

## 为什么写这个框架

Selenium 的本质并不是魔法，它就是一套 **HTTP 协议客户端**：

```
你的代码  ──HTTP(REST)──▶  chromedriver / msedgedriver / geckodriver  ──▶  真实浏览器
         ◀──── JSON ─────  (本地 9515 等端口，实现 W3C WebDriver 协议)
```

WebPilot 把这一层自己实现了一遍：启动驱动进程、创建会话、发 HTTP 命令、解析响应、映射异常。API 风格与 Selenium 保持一致，便于对照学习。

## 特性

- ✅ **三浏览器支持**：Chrome / Edge / Firefox，同一套 API
- ✅ **驱动自动管理**：自动检测浏览器版本，从官方源下载匹配的驱动并缓存（类似 Selenium Manager）
- ✅ **完整元素操作**：点击、输入、清空、属性/状态查询、子元素查找、元素截图
- ✅ **显式等待**：`WebDriverWait` + 17 个常用 `expected_conditions`
- ✅ **动作链**：`ActionChains` 基于 W3C Actions API，支持鼠标移动/双击/右键/拖拽/滚轮/组合键
- ✅ **JS 注入**：`execute_script` / `execute_async_script`，元素参数自动序列化
- ✅ **浏览器导航**：前进、后退、刷新、窗口/标签页/iframe/弹窗切换
- ✅ **Cookie 管理**、**页面/元素截图**、**隐式等待**、**上下文管理器**
- ✅ 仅依赖 `requests`，零重型依赖

## 快速开始

```bash
pip install -r requirements.txt
```

```python
from webpilot import Chrome, By, WebDriverWait
from webpilot import expected_conditions as EC

with Chrome() as driver:                      # 自动下载匹配的 chromedriver
    driver.get("https://quotes.toscrape.com/login")
    driver.find_element(By.ID, "username").send_keys("demo")
    driver.find_element(By.ID, "password").send_keys("demo")
    driver.find_element(By.CSS_SELECTOR, "input[type=submit]").click()

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".quote")))
    for q in driver.find_elements(By.CSS_SELECTOR, ".quote .text")[:5]:
        print(q.text)

    driver.find_element(By.CSS_SELECTOR, "li.next > a").click()   # 翻页
    driver.back()                                                 # 后退
    driver.save_screenshot("result.png")
# with 块结束自动 quit()，浏览器与驱动进程一并回收
```

跑示例（首次运行会自动下载驱动，缓存到 `~/.webpilot/drivers/`）：

```bash
python examples/demo_quotes.py      # 登录 + 表单输入 + 翻页 + 截图
python examples/demo_saucedemo.py   # 电商登录 + 动作链加购 + Cookie
```

跑测试：

```bash
pytest tests/ -v
```

## 常用 API

### 创建浏览器

```python
from webpilot import Chrome, Edge, Firefox, ChromeOptions

driver = Chrome(headless=True)                 # 无头模式
driver = Edge()                                # 有界面模式
driver = Firefox(driver_path="/path/to/geckodriver")  # 手动指定驱动

options = ChromeOptions()
options.add_argument("--window-size=1280,800")
options.add_argument("--disable-blink-features=AutomationControlled")  # 反爬常用
options.add_experimental_option("prefs", {"download.default_directory": r"D:\dl"})
driver = Chrome(options=options)
```

### 元素操作

```python
from webpilot import By, Keys

el = driver.find_element(By.ID, "kw")              # 找不到抛 NoSuchElementException
el = driver.find_element("#kw")                    # 简写，默认 CSS 选择器
els = driver.find_elements(By.XPATH, "//li")       # 找不到返回 []

el.click()                # 真实鼠标点击（自动滚动到可视区域）
el.send_keys("hello", Keys.ENTER)
el.clear()
el.text                   # 可见文本
el.get_attribute("href")  # HTML attribute
el.get_property("value")  # JS property（输入框实时值）
el.is_displayed()         # 可见性 / is_enabled() / is_selected()
el.rect                   # {'x','y','width','height'}
```

### 显式等待

```python
from webpilot import WebDriverWait
from webpilot import expected_conditions as EC

wait = WebDriverWait(driver, timeout=10)
btn = wait.until(EC.element_to_be_clickable((By.ID, "submit")))
wait.until(EC.title_contains("结果"))
wait.until(EC.url_contains("/search"))
```

### 动作链（模拟复杂用户行为）

```python
from webpilot import ActionChains

actions = ActionChains(driver)
actions.move_to_element(menu).pause(0.5).click(submenu).perform()   # 悬停菜单
actions.context_click(el).perform()                                 # 右键
actions.double_click(el).perform()                                  # 双击
actions.drag_and_drop(source, target).perform()                     # 拖拽
actions.scroll_by_amount(0, 600).perform()                          # 滚轮滚动
actions.scroll_to_element(footer).perform()                         # 滚到元素
actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()  # Ctrl+A
```

### 导航 / 窗口 / 弹窗 / Cookie

```python
driver.back(); driver.forward(); driver.refresh()     # 翻页
driver.switch_to.new_window("tab")                    # 新标签页
driver.switch_to.window(driver.window_handles[-1])    # 切换标签页
driver.switch_to.frame("iframe-name")                 # 切入 iframe
driver.switch_to.default_content()                    # 切回主文档
driver.switch_to.alert.accept()                       # 处理弹窗
driver.add_cookie({"name": "token", "value": "abc"})
driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
```

## 项目结构

```
webpilot/
├── webpilot/
│   ├── driver.py               # Driver 核心：进程管理、会话、全部命令
│   ├── session.py              # W3C WebDriver 协议 HTTP 客户端
│   ├── element.py              # 元素封装（WebElement）
│   ├── actions.py              # ActionChains（W3C Actions API）
│   ├── wait.py                 # WebDriverWait 显式等待
│   ├── expected_conditions.py  # 17 个常用等待条件
│   ├── manager.py              # 驱动自动下载/缓存管理
│   ├── options.py              # Chrome/Edge/Firefox 启动选项
│   ├── by.py / keys.py         # 定位策略 / 特殊按键
│   ├── exceptions.py           # 异常体系（协议错误码 -> 异常类）
│   └── logger.py               # WEBPILOT_LOG=DEBUG 可看协议请求日志
├── examples/                   # 可运行示例
└── tests/                      # pytest 端到端测试（本地 HTML 页面，不依赖外网）
```

## 与 Selenium 的对照

| 能力 | Selenium | WebPilot |
|---|---|---|
| 底层 | W3C WebDriver 协议 | W3C WebDriver 协议（自己实现 HTTP 客户端） |
| 创建驱动 | `webdriver.Chrome()` | `Chrome()` |
| 查找元素 | `find_element(By.ID, "x")` | 相同 |
| 显式等待 | `WebDriverWait` + `expected_conditions` | 相同 |
| 动作链 | `ActionChains` | 相同 |
| 驱动管理 | Selenium Manager | `manager.py` 自动下载 |

## 调试

设置环境变量 `WEBPILOT_LOG=DEBUG` 可以看到每一条发往驱动的 HTTP 请求与响应：

```
[12:00:01] DEBUG webpilot: >> POST /session {'capabilities': ...}
[12:00:02] DEBUG webpilot: << {'sessionId': 'a1b2...', 'capabilities': {...}}
```

## License

MIT
