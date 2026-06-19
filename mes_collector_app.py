"""MES采集端 - 原生桌面应用"""
import os
import sys
import threading
import time

def get_base():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def main():
    base_dir = get_base()
    os.chdir(base_dir)
    sys.path.insert(0, os.path.join(base_dir, 'backend'))
    
    from backend.app import app
    from backend.utils.database import init_db, _init_extra_tables, _create_indexes
    
    init_db()
    _init_extra_tables()
    _create_indexes()
    
    def run_server():
        app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
    
    import webview
    webview.create_window(
        'MES采集终端',
        'http://127.0.0.1:8080',
        width=420,
        height=800,
        resizable=True,
        min_size=(360, 600)
    )
    webview.start()

if __name__ == '__main__':
    main()
