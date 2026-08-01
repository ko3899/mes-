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
    from backend.utils.database import init_db, _init_extra_tables, _create_indexes

    init_db()
    _init_extra_tables()
    _create_indexes()

    def open_browser():
        time.sleep(1.2)
        webbrowser.open('http://127.0.0.1:8080/')

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
