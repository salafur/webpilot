# WebPilot · 产品文档说明报告

> 项目名称：WebPilot — 纯 Python 实现的浏览器自动化框架
> 文档版本：v1.0（基于 2026-09-29 源码逐行梳理）
> 项目路径：`C:\Users\Administrator\WorkBuddy\2026-09-29-19-58-12\webpilot`
> 许可证：MIT

---

## 1. 项目定位：一句话说清它是干嘛的

**不依赖 Selenium，自己实现 W3C WebDriver 协议客户端，用纯 Python + requests 驱动真实的 Chrome / Edge / Firefox 执行点击、输入、滚动、翻页等用户行为。API 风格与 Selenium 保持一致。**

一句话的本质：**把 Selenium 的底层原理自己写了一遍**。

## 2. 为什么写这个项目（动机）

Selenium 不是魔法，它就是一套 **HTTP 协议客户端**：

```
你的代码  ──HTTP(REST)──▶  chromedriver / msedgedriver / geckodriver  ──▶  真实浏览器
         ◀──── JSON ─────  (本地 9515 等端口，实现 W3C WebDriver 协议)
```

中间的驱动程序（chromedriver 等）是个本地 REST 服务：启动后监听端口，接收 `POST /session`、`POST /element`、`POST /click` 这类 HTTP 命令，翻译成浏览器操作，返回 JSON。WebPilot 把"你的代码"这一侧完整实现了一遍——**启动驱动进程、创建会话、发 HTTP 命令、解析响应、映射异常**。

这个项目的技术含金量在于证明：**你能独立实现一个工业级协议的客户端**——这正是"框架"和"工具"的区别在 UI 自动化领域的体现。

## 3. 特性清单

| 能力 | 说明 |
|------|------|
| 三浏览器支持 | Chrome / Edge / Firefox，同一套 API |
| 驱动自动管理 | 检测浏览器版本 → 官方源下载匹配驱动 → 缓存（对标 Selenium Manager） |
| 完整元素操作 | 点击、输入、清空、属性/状态查询、子元素查找、元素截图 |
| 显式等待 | `WebDriverWait` + 17 个 `expected_conditions` |
| 动作链 | `ActionChains`（W3C Actions API）：悬停/双击/右键/拖拽/滚轮/组合键 |
| JS 注入 | `execute_script` / `execute_async_script`，元素参数自动序列化 |
| 导航与上下文 | 前进/后退/刷新、窗口/标签页/iframe/弹窗切换 |
| Cookie 管理 | 增删查改全套 |
| 截图 | 整页 + 单元素 |
| 依赖 | **仅 `requests`**，零重型依赖 |

## 4. 架构与模块拆解（逐文件）

### 4.1 `session.py` — W3C 协议 HTTP 客户端（地基）

`CommandExecutor`：把命令序列化成 HTTP 请求发给驱动，把错误码映射成异常。

两个关键细节：

1. **刻意不用 `requests.Session()`**——注释里记着真实踩坑："实测 chromedriver 的 HTTP 服务在复用 keep-alive 连接时，第二条命令会解析错乱并返回 400 'unhandled request'，每条命令独立建连可以稳定规避。"这是协议层逆向调试的经验结晶。
2. **错误码 → 异常映射**：HTTP ≥400 或响应体含 `error` 字段时，查 `ERROR_MAP` 抛出对应的异常类。

### 4.2 `exceptions.py` — 异常体系

- 基类 `WebPilotException`，携带驱动返回的 error 码
- **协议层异常 11 个**：`NoSuchElementException`、`StaleElementReferenceException`、`ElementClickInterceptedException`……与 Selenium 命名一致
- **框架层异常 4 个**：`TimeoutException`、`SessionNotCreatedException`、`InvalidSessionIdException`、`DriverNotFoundException`
- `ERROR_MAP`：W3C 规范 error 码字符串 → 异常类的映射表（如 `"no such element"` → `NoSuchElementException`）

### 4.3 `driver.py` — 驱动核心（对应 Selenium 的 WebDriver）

`Driver` 类是整个框架的中枢，生命周期：

```
Chrome() 实例化
  ├─ manager.ensure_driver()      拿到驱动可执行文件路径
  ├─ _free_port()                 挑一个空闲端口
  ├─ _start_service()             启动驱动进程，轮询 /status 等就绪（15s）
  └─ _create_session()            POST /session 建会话，拿 sessionId
所有操作
  └─ _execute()                   统一加 /session/{id} 前缀发命令
quit()
  ├─ DELETE /session/{id}         销毁会话（浏览器关闭）
  └─ _kill_service()              terminate 驱动进程
```

API 面（全部走 `_execute` → HTTP）：
- **导航**：`get/back/forward/refresh`、`title`、`current_url`、`page_source`
- **元素查找**：`find_element`（找不到抛异常）/ `find_elements`（返回列表，含简写 `find_element("#kw")` 默认 CSS）
- **JS 执行**：`execute_script` / `execute_async_script`——元素参数自动转 `{element-6066-...: id}` 协议格式，返回值里的元素引用自动转回 `Element` 对象（`_convert_arg` / `_convert_result` 递归转换）
- **截图**：`save_screenshot`（Base64 解码落盘 PNG）
- **窗口**：尺寸/最大化/最小化/全屏/标签页句柄
- **Cookie / 超时**：全套增删查 + 隐式等待/页面加载/脚本超时
- **上下文切换** `_SwitchTo`：窗口、新标签页、iframe（支持索引/name/元素三种入参）、弹窗 `Alert`
- **生命周期**：`with Chrome() as driver:` 上下文管理器，块结束自动 `quit()`；`__del__` 兜底回收进程（防泄漏）

`Chrome` / `Edge` / `Firefox` 三个子类只差 `browser_name` 和 Options 类——模板方法模式。

### 4.4 `element.py` — 元素封装（对应 WebElement）

`Element` 是"DOM 元素的引用"，所有属性都是**实时向浏览器查询**的：

- 交互：`click`（自动滚到可视区+可交互性检查）、`send_keys`（混合文本与 `Keys` 特殊键）、`clear`、`submit`（W3C 移除了原生 submit，用 JS 实现）
- 状态：`text`、`tag_name`、`get_attribute`（HTML 属性）/ `get_property`（JS 实时属性，如输入框当前值）——两者的区别是 UI 自动化面试高频点
- 几何：`rect`（x/y/width/height）
- 子查找：在元素内部继续 `find_element`
- 截图：单元素截图

`ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"`——W3C 规范定义的元素引用键（UUID 是规范写死的），同时兼容旧版 JSON Wire 协议的 `ELEMENT` 键。

### 4.5 `wait.py` — 显式等待

`WebDriverWait`：轮询调用条件函数直到返回真值或超时。比 `time.sleep` 可靠：**条件满足立即继续，不满足才等到超时**。默认吞掉 `NoSuchElementException` 和 `StaleElementReferenceException`（元素还没渲染出来属于正常中间状态）。`until_not` 反向等待（等条件消失）。

### 4.6 `expected_conditions.py` — 17 个等待条件

`presence_of_element_located`、`visibility_of`、`element_to_be_clickable`、`title_contains`、`url_contains`、`text_to_be_present_in_element` 等——与 Selenium 同名同义。

### 4.7 `actions.py` — 动作链

`ActionChains` 基于 W3C Actions API（pointer/key 输入源 + tick 时间轴）：`move_to_element`（悬停菜单）、`context_click`（右键）、`double_click`、`drag_and_drop`、`scroll_by_amount`（滚轮）、`key_down/key_up`（Ctrl+A 这类组合键），`.perform()` 一次性提交。

### 4.8 `manager.py` — 驱动自动管理（对标 Selenium Manager，约 300 行）

驱动查找的**四级策略**（按优先级）：

1. 环境变量指定（`WEBPILOT_CHROME_DRIVER` 等）
2. 系统 PATH 查找
3. 本地缓存 `~/.webpilot/drivers/` 匹配浏览器大版本
4. **自动下载**：
   - Chrome：Chrome for Testing 官方 JSON 接口挑匹配大版本
   - Edge：Microsoft 官方接口（注意代码里处理了一个怪癖——该接口返回 **UTF-16** 编码文本）
   - Firefox：geckodriver GitHub Releases API

浏览器版本检测也分平台：Windows 优先读注册表（`BLBeacon` 等键）再退回安装目录跑 `--version`；macOS/Linux 走常见安装路径。下载用流式写入临时目录、解压、非 Windows 平台补可执行权限。

### 4.9 `by.py` / `keys.py` / `options.py` / `logger.py`

- `by.py`：定位策略（ID/XPath/CSS/link text 等），`to_w3c()` 把简写统一翻译成 W3C 的 `using/value` 格式
- `keys.py`：特殊按键常量（ENTER/CONTROL/BACKSPACE 等，对应 Unicode PUA 码点）
- `options.py`：三种浏览器的启动选项（headless、参数、prefs）
- `logger.py`：`WEBPILOT_LOG=DEBUG` 环境变量开启后，能看到每一条发往驱动的 HTTP 请求与响应——**排查协议问题的照妖镜**

## 5. 与 Selenium 的对照

| 能力 | Selenium | WebPilot |
|---|---|---|
| 底层 | W3C WebDriver 协议 | 同一协议，HTTP 客户端自己写 |
| 创建驱动 | `webdriver.Chrome()` | `Chrome()` |
| 查找元素 | `find_element(By.ID, "x")` | 相同 |
| 显式等待 | `WebDriverWait` + EC | 相同 |
| 动作链 | `ActionChains` | 相同 |
| 驱动管理 | Selenium Manager | `manager.py` 自动下载 |

**学会 WebPilot = 顺带精通 Selenium 原理**，反之亦然。

## 6. 测试与示例

- `tests/test_webpilot.py`：pytest 端到端测试，**用本地 HTML 页面做被测对象，不依赖外网**
- `examples/demo_quotes.py`：登录 + 表单输入 + 翻页 + 截图（quotes.toscrape.com）
- `examples/demo_saucedemo.py`：电商登录 + 动作链加购 + Cookie（saucedemo.com）
- CI：GitHub Actions 自动跑测试
- 依赖：`requests>=2.31` + `pytest>=8.0`

## 7. 关键设计决策（面试可讲）

1. **为什么每条命令独立建连？** chromedriver 的 keep-alive 实现有 bug，第二条命令解析错乱返回 400——协议层的真实坑，靠抓包定位
2. **为什么 find_element 抛异常、find_elements 返回空列表？** 单个查找失败是"必然知道"的错误（显式失败），批量查找为空是合法状态（页面上就是没有）——与 Selenium 语义一致
3. **为什么属性查询分 attribute 和 property？** HTML 属性是静态初始值，JS property 是实时状态（如输入框当前值）——前端基础
4. **为什么默认吞 NoSuchElementException？** 显式等待期间元素未出现是正常中间态，不该中断轮询
5. **为什么 with 上下文 + `__del__` 双保险？** 驱动是子进程，泄漏会攒一堆僵尸 chromedriver

## 8. 局限与扩展

- 不支持 CDP（Chrome DevTools Protocol）：网络拦截、性能抓取等高级能力可叠加 CDP 层
- 无网格/分布式：可接 Selenium Grid 的 remote 端点（`CommandExecutor` 换 remote_url 即可）
- 移动端：可接 Appium 的 WebDriver 服务端（同一协议）

## 9. 与你技能树的对应关系

- 补全了你"前端 + 安卓 + 机台"三端之外的**Web UI 自动化**版图
- 面试讲法：**"我理解 Selenium 的本质是 W3C WebDriver 协议的 HTTP 客户端，并独立实现过一版"**——这是 1-3 年岗位里极具区分度的一句话
- 建议演示：`WEBPILOT_LOG=DEBUG` 跑一次 demo，对着协议日志讲 `POST /session` → `POST /element` → `POST /click` 的完整链路，面试官会记住你
