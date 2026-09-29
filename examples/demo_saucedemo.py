"""示例 2：电商流程 —— 登录 saucedemo.com、加购商品、断言购物车数量。

展示显式等待、ActionChains 动作链、Cookie 操作。
运行: python examples/demo_saucedemo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webpilot import ActionChains, By, Chrome, WebDriverWait
from webpilot import expected_conditions as EC

OUT = Path(__file__).resolve().parent / "artifacts"
OUT.mkdir(exist_ok=True)


def main():
    # 想用 Edge/Firefox 把 Chrome 换成对应类即可，API 完全一致
    with Chrome(headless=True) as driver:
        wait = WebDriverWait(driver, timeout=10)

        # 1. 登录
        driver.get("https://www.saucedemo.com")
        driver.find_element(By.ID, "user-name").send_keys("standard_user")
        driver.find_element(By.ID, "password").send_keys("secret_sauce")
        driver.find_element(By.ID, "login-button").click()

        wait.until(EC.url_contains("inventory"))
        print("登录成功:", driver.current_url)

        # 2. 用动作链把第一件商品加入购物车
        add_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".inventory_item button"))
        )
        ActionChains(driver).move_to_element(add_btn).pause(0.3).click().perform()

        badge = driver.find_element(By.CLASS_NAME, "shopping_cart_badge")
        assert badge.text == "1", f"购物车数量应为 1，实际 {badge.text}"
        print("加购成功，购物车数量:", badge.text)

        # 3. 读取 Cookie 验证会话
        session_cookie = driver.get_cookie("session-username")
        print("会话 Cookie:", session_cookie["value"] if session_cookie else "无")

        driver.save_screenshot(OUT / "saucedemo_cart.png")
        print(f"截图已保存到 {OUT}")


if __name__ == "__main__":
    main()
