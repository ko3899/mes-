"""Run the central MQTT event consumer as a private-deployment service."""

import os
import sqlite3
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))

from services.mqtt_event_consumer import MqttEventConsumer  # noqa: E402
from services.device_event_ingest import create_device_event_tables  # noqa: E402
from utils.database import DB_PATH  # noqa: E402


def main():
    db_path = os.environ.get('MES_CENTRAL_DB', DB_PATH)
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    create_device_event_tables(db)
    consumer = MqttEventConsumer(
        os.environ['MES_MQTT_HOST'], int(os.environ.get('MES_MQTT_PORT', '8883')),
        os.environ['MES_MQTT_CA'], os.environ['MES_MQTT_CERT'], os.environ['MES_MQTT_KEY'], db,
    )
    consumer.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        return 0
    finally:
        consumer.close()
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
