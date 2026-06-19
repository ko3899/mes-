from playwright.sync_api import sync_playwright
import os

os.makedirs('D:/MES工厂管家/screenshots', exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 登录页
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='D:/MES工厂管家/screenshots/ui_login.png')
    
    # 登录
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    
    # 仪表盘
    page.screenshot(path='D:/MES工厂管家/screenshots/ui_dashboard.png')
    
    browser.close()
    print("截图完成!")
