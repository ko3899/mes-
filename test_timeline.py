from playwright.sync_api import sync_playwright
import os

os.makedirs('D:/MES工厂管家/screenshots', exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 登录
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    
    # 截图首页
    page.screenshot(path='D:/MES工厂管家/screenshots/final_01_dashboard.png')
    print("截图1: 仪表盘")
    
    # 用JS跳转到操作记录
    page.evaluate("window.goPage && goPage('process/record')")
    page.wait_for_timeout(3000)
    
    # 如果goPage不可用，直接用URL跳转
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    
    # 通过点击展开菜单
    try:
        # 找到制程管控菜单
        menu_items = page.locator('.menu-title')
        for i in range(menu_items.count()):
            item = menu_items.nth(i)
            text = item.text_content()
            if '制程管控' in text:
                item.click()
                page.wait_for_timeout(500)
                break
        
        # 找到操作记录
        sub_items = page.locator('.menu-title[data-page]')
        for i in range(sub_items.count()):
            item = sub_items.nth(i)
            text = item.text_content()
            if '操作记录' in text:
                item.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(2000)
                break
        
        page.screenshot(path='D:/MES工厂管家/screenshots/final_02_record.png')
        print("截图2: 操作记录")
        
        # 点击SN轨迹按钮
        sn_btn = page.locator('button:has-text("SN轨迹")')
        if sn_btn.count() > 0:
            sn_btn.first.click()
            page.wait_for_timeout(1000)
            page.fill('#f_sn', 'SN20260619001')
            page.wait_for_timeout(500)
            page.click('#mSave')
            page.wait_for_timeout(3000)
            page.screenshot(path='D:/MES工厂管家/screenshots/final_03_timeline.png', full_page=True)
            print("截图3: SN过站轨迹")
        
    except Exception as e:
        print(f"菜单操作失败: {e}")
        # 直接截图当前页面
        page.screenshot(path='D:/MES工厂管家/screenshots/final_02_current.png')
    
    browser.close()
    print("完成!")
