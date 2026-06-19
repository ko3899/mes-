from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 收集控制台错误
    errors = []
    page.on('console', lambda msg: errors.append(f'{msg.type}: {msg.text}') if msg.type == 'error' else None)
    page.on('pageerror', lambda exc: errors.append(f'PAGE ERROR: {exc}'))
    
    page.goto('http://localhost:8080/admin')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)
    
    # 检查页面内容
    title = page.title()
    body = page.inner_text('body')
    
    print(f"标题: {title}")
    print(f"页面内容长度: {len(body)}")
    print(f"页面前200字: {body[:200]}")
    print(f"\n控制台错误 ({len(errors)}):")
    for e in errors[:10]:
        print(f"  {e}")
    
    browser.close()
