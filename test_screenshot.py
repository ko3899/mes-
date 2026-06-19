from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 打开管理后台
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    
    # 截图登录页面
    page.screenshot(path='D:/MES工厂管家/screenshots/01_login.png', full_page=True)
    print("截图1: 登录页面")
    
    # 登录
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)
    
    # 截图首页
    page.screenshot(path='D:/MES工厂管家/screenshots/02_dashboard.png', full_page=True)
    print("截图2: 仪表盘")
    
    # 使用 JavaScript 直接跳转到页面
    page.evaluate("goPage('prod/workorder')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/03_workorder.png', full_page=True)
    print("截图3: 工单管理")
    
    page.evaluate("goPage('qm/statistics')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/04_quality.png', full_page=True)
    print("截图4: 质量统计")
    
    page.evaluate("goPage('analytics/oee')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/05_oee.png', full_page=True)
    print("截图5: OEE分析")
    
    page.evaluate("goPage('sys/monitor')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/06_monitor.png', full_page=True)
    print("截图6: 系统监控")
    
    page.evaluate("goPage('query/statistics')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/07_statistics.png', full_page=True)
    print("截图7: 综合统计")
    
    page.evaluate("goPage('notifications')")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='D:/MES工厂管家/screenshots/08_notifications.png', full_page=True)
    print("截图8: 消息通知")
    
    browser.close()
    print("全部截图完成!")
