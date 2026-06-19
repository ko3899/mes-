"""MES工厂管家 - 一键启动脚本"""
import os
import sys
import webbrowser
import threading
import time

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(base_dir)
    
    # 添加所有需要的路径
    for subdir in ['backend', 'frontend', 'admin']:
        p = os.path.join(base_dir, subdir)
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)
    
    from backend.app import app
    from backend.utils.database import init_db, _init_extra_tables, _create_indexes
    
    print("=" * 50)
    print("  MES工厂管家")
    print("=" * 50)
    
    init_db()
    _init_extra_tables()
    _create_indexes()
    
    def open_browser():
        time.sleep(2)
        webbrowser.open('http://localhost:8080/admin')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("服务启动中...")
    print("管理后台: http://localhost:8080/admin")
    print("采集终端: http://localhost:8080")
    print("账号: admin / admin123")
    
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    main()
