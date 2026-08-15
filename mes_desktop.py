"""MES工厂管家 - 原生桌面应用"""
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
    
    # 启动 Flask 服务器
    from backend.app import app
    from backend.machine_runtime import MachineCommunicationRuntime
    from backend.utils.database import init_db, _init_extra_tables, _create_indexes
    
    init_db()
    _init_extra_tables()
    _create_indexes()
    machine_runtime = MachineCommunicationRuntime()
    machine_runtime.start()
    
    def run_server():
        app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
    
    # 打开原生窗口
    import webview
    webview.create_window(
        'MES工厂管家',
        'http://127.0.0.1:8080/admin',
        width=1400,
        height=900,
        resizable=True,
        min_size=(800, 600)
    )
    try:
        webview.start()
    finally:
        machine_runtime.stop()

if __name__ == '__main__':
    main()
