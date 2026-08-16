"""MES采集终端浏览器启动器，共享主应用的认证与业务接口。"""
import os
import sys
import threading
import time
import webbrowser


def get_project_root():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    project_root = get_project_root()
    os.chdir(project_root)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from backend.app import app
    from backend.machine_runtime import MachineCommunicationRuntime
    from backend.utils.database import init_db, _init_extra_tables, _create_indexes

    init_db()
    _init_extra_tables()
    _create_indexes()
    app.config['SESSION_COOKIE_NAME'] = 'mes_main_session'

    def open_browser():
        time.sleep(1.2)
        webbrowser.open('http://127.0.0.1:8080/')

    if os.environ.get('MES_OPEN_BROWSER', '1') != '0':
        threading.Thread(target=open_browser, daemon=True).start()
    machine_runtime = MachineCommunicationRuntime()
    owns_runtime = machine_runtime.start()
    print('机台通讯运行时：' + ('已启动' if owns_runtime else '已由其他进程托管'))
    try:
        app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
    finally:
        machine_runtime.stop()


if __name__ == '__main__':
    main()
