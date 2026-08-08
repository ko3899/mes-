import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


from utils.table_order import (  # noqa: E402
    move_record,
    ordered_ids,
    reorder_ids,
    step_record,
)
from utils import helpers  # noqa: E402


class TableOrderTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE prod_workorder (id INTEGER PRIMARY KEY)')
        self.db.executemany(
            'INSERT INTO prod_workorder(id) VALUES (?)',
            [(value,) for value in range(1, 11)],
        )
        self.db.execute('''CREATE TABLE sys_table_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_key TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_key, record_id)
        )''')
        self.db.commit()

    def tearDown(self):
        self.db.close()
        os.remove(self.path)

    def test_move_ninth_record_to_sixth(self):
        self.assertEqual(
            reorder_ids(list(range(1, 11)), 9, 6),
            [1, 2, 3, 4, 5, 9, 6, 7, 8, 10],
        )

    def test_target_position_is_clamped(self):
        self.assertEqual(reorder_ids([1, 2, 3], 2, 99), [1, 3, 2])
        self.assertEqual(reorder_ids([1, 2, 3], 2, -5), [2, 1, 3])

    def test_move_record_persists_continuous_positions(self):
        result = move_record(self.db, 'prod/workorder', 2, 6)
        self.assertEqual(result, [10, 9, 8, 7, 6, 2, 5, 4, 3, 1])
        rows = self.db.execute(
            'SELECT record_id, position FROM sys_table_order '
            'WHERE table_key=? ORDER BY position',
            ('prod/workorder',),
        ).fetchall()
        self.assertEqual([row['position'] for row in rows], list(range(1, 11)))

    def test_step_record_respects_boundaries(self):
        self.assertEqual(step_record(self.db, 'prod/workorder', 10, 'up')[0], 10)
        self.assertEqual(step_record(self.db, 'prod/workorder', 10, 'down')[:2], [9, 10])

    def test_ordered_ids_rejects_unknown_module(self):
        with self.assertRaises(ValueError):
            ordered_ids(self.db, 'not/allowed')

    def test_generic_list_uses_manual_order_until_field_sort_is_selected(self):
        move_record(self.db, 'prod/workorder', 2, 1)
        with mock.patch.object(helpers, 'get_db', return_value=self.db), \
                mock.patch.object(helpers, '_get_table_columns', return_value=['id']):
            default_rows = helpers.crud_list('prod_workorder', {'page': 1, 'size': 20})
            explicit_rows = helpers.crud_list(
                'prod_workorder',
                {'page': 1, 'size': 20, 'sort': 'id', 'order': 'ASC'},
            )
        self.assertEqual(default_rows['data']['list'][0]['id'], 2)
        self.assertEqual([row['id'] for row in explicit_rows['data']['list'][:3]], [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
