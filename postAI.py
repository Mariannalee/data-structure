from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv

# 讀取 .env 檔案
load_dotenv()
IG_EMAIL = os.getenv("INSTRGAM_EMAIL")
IG_PASSWORD = os.getenv("INSTRGAM_PASSWORD")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # 顯示瀏覽器
    context = browser.new_context()  # 使用無痕模式
    page = browser.new_page()

    print("啟動瀏覽器，開始登入 thread...")

    # 進入 thread 登入頁面
    page.goto("https://www.threads.net/login")
    page.wait_for_timeout(3000)

    # 使用 .env 讀取帳號密碼
    page.fill('input[autocomplete="username"]', IG_EMAIL)
    page.fill('input[autocomplete="current-password"]', IG_PASSWORD)

    
    # 按下登入按鈕
    
    page.click('div[role="button"]:has-text("登入")')
    page.wait_for_timeout(10000)
    print("登入成功！")
    page.screenshot(path="debug_1_after_login.png")

    # 直接前往個人頁面
    page.goto("https://www.threads.net/following")
    page.wait_for_timeout(3000)
    print("進入個人首頁")
    page.screenshot(path="debug_2_after_profile.png")

    # 點擊「新增」開啟發文對話框
    post_trigger = page.locator("svg:has-text('建立')").first
    post_trigger.wait_for()
    post_trigger.click()
    page.wait_for_timeout(2000)
    print("thread 貼文對話框開啟成功！")
    page.screenshot(path="debug_3_after_click_post_box.png")

    #輸入文字中
    print("輸入文字中...")
    post_box = page.locator('div[contenteditable="true"]').first
    post_box.click()  # 點擊輸入框以聚焦
    page.keyboard.type("這是我在 Threads 自動發的文 ✨")
    page.wait_for_timeout(3000)
    print("文字輸入完成！")

    print("Thread 偵測到輸入")
    # 直接設定圖片到 input[type="file"]
    print("上傳圖片中...")
    page.set_input_files('input[type="file"]', "stone.jpg")
    print("圖片上傳完成！")

# 等待圖片上傳完成
    page.wait_for_timeout(3000)



    print("⌛ 等待 Thread 啟用發佈按鈕...")
# 按下一步
    print("🚀 貼文發佈中...")
    page.locator('div[role="button"]:has-text("發佈")').nth(1).click(force=True)
    page.wait_for_timeout(5000)

    input("瀏覽器保持開啟，按 Enter 關閉...")

    # 關閉瀏覽器
    browser.close()
    print("瀏覽器已關閉")

    

    