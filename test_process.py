from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    
    # 登录
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)
    
    # 跳转到工序管理
    page.evaluate("goPage('base/process')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/process_list.png', full_page=True)
    print("截图: 工序管理页面")
    
    browser.close()
    print("完成!")
