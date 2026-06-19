from playwright.sync_api import sync_playwright
import os

os.makedirs('D:/MES工厂管家/screenshots', exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 登录页面
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_01_login.png')
    
    # 登录
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)
    
    # 仪表盘
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_02_dashboard.png')
    
    # 工单管理
    page.evaluate("goPage('prod/workorder')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_03_workorder.png')
    
    # 工序管理
    page.evaluate("goPage('base/process')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_04_process.png')
    
    # OEE分析
    page.evaluate("goPage('analytics/oee')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_05_oee.png')
    
    # 系统监控
    page.evaluate("goPage('sys/monitor')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_06_monitor.png')
    
    # 暗色主题
    page.evaluate("toggleTheme()")
    page.wait_for_timeout(500)
    page.evaluate("goPage('home')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/demo_07_dark_theme.png')
    
    browser.close()
    print("截图完成!")
