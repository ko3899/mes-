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
    
    from flask import Flask, send_from_directory, session, jsonify, request, g
    import sqlite3
    import hashlib
    
    app = Flask(__name__, static_folder=None)
    app.secret_key = 'mes-collector-secret'
    
    DB_PATH = os.path.join(os.path.dirname(base), 'database', 'mes.db')
    FRONTEND_DIR = base
    
    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
        return g.db
    
    @app.teardown_appcontext
    def close_db(e):
        db = g.pop('db', None)
        if db: db.close()
    
    @app.route('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')
    
    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.json
        db = get_db()
        pwd_hash = hashlib.md5(data['password'].encode()).hexdigest()
        user = db.execute("SELECT * FROM sys_user WHERE username=? AND password=?", (data['username'], pwd_hash)).fetchone()
        if not user:
            return jsonify({'code': 400, 'message': 'Login failed'})
        session['user_id'] = user['id']
        return jsonify({'code': 0, 'data': {'id': user['id'], 'username': user['username'], 'real_name': user['real_name']}})
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        session.clear()
        return jsonify({'code': 0})
    
    @app.route('/api/user/info')
    def user_info():
        if 'user_id' not in session:
            return jsonify({'code': 401})
        db = get_db()
        user = db.execute("SELECT * FROM sys_user WHERE id=?", (session['user_id'],)).fetchone()
        return jsonify({'code': 0, 'data': dict(user)})
    
    def crud_list(table, args):
        db = get_db()
        page = int(args.get('page', 1))
        size = int(args.get('size', 20))
        total = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        rows = db.execute(f"SELECT * FROM {table} LIMIT ? OFFSET ?", (size, (page-1)*size)).fetchall()
        return {'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}}
    
    def crud_add(table, data):
        db = get_db()
        keys = [k for k in data.keys() if k != 'id']
        vals = [data[k] for k in keys]
        cursor = db.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})", vals)
        db.commit()
        return {'code': 0, 'data': {'id': cursor.lastrowid}}
    
    def gen_no(prefix):
        db = get_db()
        row = db.execute("SELECT * FROM sys_numbering WHERE entity_type=?", (prefix,)).fetchone()
        if not row:
            db.execute("INSERT INTO sys_numbering (prefix, entity_type, current_no, digit_count) VALUES (?,?,1,6)", (prefix, prefix))
            db.commit()
            no, digits = 1, 6
        else:
            no = row['current_no'] + 1
            db.execute("UPDATE sys_numbering SET current_no=? WHERE entity_type=?", (no, prefix))
            db.commit()
            digits = row['digit_count']
        return f"{prefix}{time.strftime('%Y%m%d')}{str(no).zfill(digits)}"
    
    @app.route('/api/prod/task/list')
    def task_list():
        return jsonify(crud_list('prod_task', request.args))
    
    @app.route('/api/prod/task/update', methods=['POST'])
    def task_update():
        db = get_db()
        d = request.json
        db.execute("UPDATE prod_task SET status=? WHERE id=?", (d['status'], d['id']))
        db.commit()
        return jsonify({'code': 0})
    
    @app.route('/api/prod/report/list')
    def report_list():
        return jsonify(crud_list('prod_report', request.args))
    
    @app.route('/api/prod/report/add', methods=['POST'])
    def report_add():
        d = request.json
        d['report_no'] = gen_no('BR')
        d['user_id'] = session.get('user_id')
        return jsonify(crud_add('prod_report', d))
    
    @app.route('/api/qm/incoming/list')
    def qm_list():
        return jsonify(crud_list('qm_incoming_inspection', request.args))
    
    @app.route('/api/qm/incoming/add', methods=['POST'])
    def qm_add():
        d = request.json
        d['inspect_no'] = gen_no('IQC')
        d['inspector'] = session.get('user_id')
        return jsonify(crud_add('qm_incoming_inspection', d))
    
    @app.route('/api/tool/borrow/list')
    def borrow_list():
        return jsonify(crud_list('tool_borrow', request.args))
    
    @app.route('/api/tool/borrow/add', methods=['POST'])
    def borrow_add():
        d = request.json
        d['borrow_no'] = gen_no('GJ')
        d['borrower'] = session.get('user_id')
        return jsonify(crud_add('tool_borrow', d))
    
    @app.route('/api/inv/balance/list')
    def inv_list():
        return jsonify(crud_list('inv_balance', request.args))
    
    print("=" * 40)
    print("  MES Collector")
    print("  http://localhost:8080")
    print("  admin / admin123")
    print("=" * 40)
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:8080')
    
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    main()
