"""HMAC authentication for private-deployment edge gateways."""

import hashlib
import hmac
import time


class GatewayAuthError(ValueError):
    pass


def _signing_key(secret):
    return hashlib.sha256(str(secret).encode('utf-8')).digest()


def build_signature(gateway_id, timestamp, nonce, body, secret):
    body_hash = hashlib.sha256(bytes(body)).hexdigest()
    message = f'{gateway_id}\n{timestamp}\n{nonce}\n{body_hash}'.encode('utf-8')
    return hmac.new(_signing_key(secret), message, hashlib.sha256).hexdigest()


def create_gateway_auth_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS iot_gateway_credential (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_code TEXT NOT NULL UNIQUE,
        secret_hash TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_gateway_nonce (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_code TEXT NOT NULL,
        nonce TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(gateway_code,nonce)
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gateway_nonce_time ON iot_gateway_nonce(used_at)')
    db.commit()


def authenticate_gateway(db, gateway_id, timestamp, nonce, signature, body, max_skew=300):
    if not all(isinstance(value, str) and value.strip()
               for value in (gateway_id, timestamp, nonce, signature)):
        raise GatewayAuthError('missing gateway authentication headers')
    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise GatewayAuthError('invalid gateway timestamp') from exc
    if abs(int(time.time()) - sent_at) > int(max_skew):
        raise GatewayAuthError('gateway timestamp expired')
    row = db.execute(
        'SELECT * FROM iot_gateway_credential WHERE gateway_code=? AND enabled=1',
        (gateway_id,),
    ).fetchone()
    if not row:
        raise GatewayAuthError('unknown or disabled gateway')
    body_hash = hashlib.sha256(bytes(body)).hexdigest()
    message = f'{gateway_id}\n{timestamp}\n{nonce}\n{body_hash}'.encode('utf-8')
    try:
        key = bytes.fromhex(row['secret_hash'])
    except (ValueError, TypeError) as exc:
        raise GatewayAuthError('gateway credential is invalid') from exc
    expected = hmac.new(key, message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise GatewayAuthError('invalid gateway signature')
    try:
        db.execute(
            'INSERT INTO iot_gateway_nonce(gateway_code,nonce) VALUES(?,?)',
            (gateway_id, nonce),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if 'UNIQUE constraint failed' in str(exc):
            raise GatewayAuthError('gateway nonce replayed') from exc
        raise
    return dict(row)
