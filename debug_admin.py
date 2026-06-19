from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    errors = []
    page.on('console', lambda msg: errors.append(f'{msg.type}: {msg.text}'))
    page.on('pageerror', lambda exc: errors.append(f'ERROR: {exc}'))
    
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    
    page.fill('#lu', 'admin')
    page.fill('#lp', 'admin123')
    page.click('#loginBtn')
    page.wait_for_timeout(5000)
    
    body = page.inner_text('body')
    with open('D:/MES工厂管家/screenshots/debug_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Page content: {body[:500]}\n\nConsole errors ({len(errors)}):\n")
        for e in errors:
            f.write(f"  {e}\n")
    
    page.screenshot(path='D:/MES工厂管家/screenshots/debug.png')
    browser.close()
    print("Done, check debug_output.txt")
