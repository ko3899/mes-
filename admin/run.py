import os
import sys
import webbrowser
import threading
import time

def get_base():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def main():
    base = get_base()
    os.chdir(os.path.dirname(base))
    
    sys.path.insert(0, os.path.join(base, '..', 'backend'))
    from app import app, init_db, _init_extra_tables
    app.config['SESSION_COOKIE_NAME'] = 'mes_admin_session'
    
    print("=" * 40)
    print("  MES Admin")
    print("  http://localhost:8081/admin")
    print("  admin / admin123")
    print("=" * 40)
    
    init_db()
    _init_extra_tables()
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:8081/admin')
    
    if os.environ.get('MES_OPEN_BROWSER', '1') != '0':
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=8081, debug=False)

if __name__ == '__main__':
    main()
