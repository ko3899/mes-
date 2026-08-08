import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


from blueprints.table_order import table_order_bp  # noqa: E402


class TableOrderApiTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE prod_workorder (id INTEGER PRIMARY KEY)')
        self.db.executemany('INSERT INTO prod_workorder(id) VALUES (?)', [(i,) for i in range(1, 11)])
        self.db.execute('''CREATE TABLE sys_table_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_key TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_key, record_id)
        )''')
        self.db.commit()

        self.app = Flask(__name__)
        self.app.secret_key = 'test-secret'
        self.app.register_blueprint(table_order_bp)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 1
        self.db_patch = patch('blueprints.table_order.get_db', return_value=self.db)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.db.close()
        os.remove(self.path)

    def test_move_ninth_default_record_to_sixth(self):
        response = self.client.post('/api/table-order/move', json={
            'table_key': 'prod/workorder',
            'record_id': 2,
            'target_position': 6,
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['data']['ordered_ids'], [10, 9, 8, 7, 6, 2, 5, 4, 3, 1])
        self.assertEqual(payload['data']['positions']['2'], 6)

    def test_unknown_module_is_rejected(self):
        response = self.client.post('/api/table-order/move', json={
            'table_key': 'sqlite/master',
            'record_id': 1,
            'target_position': 1,
        })
        self.assertEqual(response.status_code, 400)

    def test_step_down_moves_one_position(self):
        response = self.client.post('/api/table-order/step', json={
            'table_key': 'prod/workorder',
            'record_id': 10,
            'direction': 'down',
        })
        self.assertEqual(response.get_json()['data']['ordered_ids'][:2], [9, 10])


if __name__ == '__main__':
    unittest.main()
