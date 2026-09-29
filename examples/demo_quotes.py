"""示例 1：登录 + 翻页 —— 以 quotes.toscrape.com（自动化练习专用站点）为例。

覆盖：打开页面、表单输入、按钮点击、显式等待、滚动、翻页、后退、截图。

运行: python examples/demo_quotes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webpilot import By, Chrome, WebDriverWait
from webpilot import expected_conditions as EC

OUT = Path(__file__).resolve().parent / "artifacts"
OUT.mkdir(exist_ok=True)


def main():
    # headless=False 可以看到浏览器真实操作过程
    with Chrome(headless=True) as driver:
        driver.set_window_size(1280, 900)
        wait = WebDriverWait(driver, timeout=15)

        # 1. 打开登录页，输入账号密码（该站点任意账号可登录）
        driver.get("https://quotes.toscrape.com/login")
        driver.find_element(By.ID, "username").send_keys("demo_user")
        driver.find_element(By.ID, "password").send_keys("demo_pass")

        # 2. 滚动到登录按钮并点击（模拟真实用户先看清楚再点）
        login_btn = driver.find_element(By.CSS_SELECTOR, "input[type=submit]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", login_btn)
        login_btn.click()

        # 3. 等待名言列表渲染，抓取本页名言
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".quote")))
        quotes = driver.find_elements(By.CSS_SELECTOR, ".quote .text")
        print(f"登录成功，第 1 页共 {len(quotes)} 条名言:")
        for i, q in enumerate(quotes[:3], 1):
            print(f"  {i}. {q.text[:60]}...")

        # 4. 翻页：滚动到 Next 按钮并点击，等待 URL 变化确认翻页完成
        next_btn = driver.find_element(By.CSS_SELECTOR, "li.next > a")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", next_btn)
        next_btn.click()
        wait.until(EC.url_contains("/page/2"))
        print("\n已翻到第 2 页:", driver.current_url)
        driver.save_screenshot(OUT / "quotes_page2.png")

        # 5. 后退回第 1 页（浏览器历史导航）
        driver.back()
        wait.until(EC.url_to_be("https://quotes.toscrape.com/"))
        print("后退成功:", driver.current_url)

        driver.save_screenshot(OUT / "quotes_page1.png")
        print(f"\n截图已保存到 {OUT}")


if __name__ == "__main__":
    main()
