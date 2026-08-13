"""HMAC authentication for private-deployment edge gateways."""

import hashlib
import hmac
import json
import os
import time


class GatewayAuthError(ValueError):
    pass


def build_signature(gateway_id, timestamp, nonce, body, secret):
    body_hash = hashlib.sha256(bytes(body)).hexdigest()
    message = f'{gateway_id}\n{timestamp}\n{nonce}\n{body_hash}'.encode('utf-8')
    return hmac.new(str(secret).encode('utf-8'), message, hashlib.sha256).hexdigest()


def _secret_for(gateway_id):
    try:
        secrets = json.loads(os.environ.get('MES_GATEWAY_SECRETS_JSON', '{}'))
    except (TypeError, ValueError) as exc:
        raise GatewayAuthError('gateway secret configuration is invalid') from exc
    secret = secrets.get(gateway_id) if isinstance(secrets, dict) else None
    if not isinstance(secret, str) or not secret:
        raise GatewayAuthError('gateway secret is not configured')
    return secret


def create_gateway_auth_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS iot_gateway_credential (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_code TEXT NOT NULL UNIQUE,
        secret_hash TEXT,
        secret_fingerprint TEXT,
        customer_code TEXT,
        factory_code TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_gateway_nonce (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_code TEXT NOT NULL,
        nonce TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at INTEGER,
        UNIQUE(gateway_code,nonce)
    )''')
    credential_columns = {row[1] for row in db.execute('PRAGMA table_info(iot_gateway_credential)')}
    for column in ('secret_fingerprint', 'customer_code', 'factory_code'):
        if column not in credential_columns:
            db.execute(f'ALTER TABLE iot_gateway_credential ADD COLUMN {column} TEXT')
    nonce_columns = {row[1] for row in db.execute('PRAGMA table_info(iot_gateway_nonce)')}
    if 'expires_at' not in nonce_columns:
        db.execute('ALTER TABLE iot_gateway_nonce ADD COLUMN expires_at INTEGER')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gateway_nonce_expiry ON iot_gateway_nonce(expires_at)')
    db.commit()


def authenticate_gateway(db, gateway_id, timestamp, nonce, signature, body, max_skew=300):
    if not all(isinstance(value, str) and value.strip()
               for value in (gateway_id, timestamp, nonce, signature)):
        raise GatewayAuthError('missing gateway authentication headers')
    if len(nonce) > 128:
        raise GatewayAuthError('gateway nonce is too long')
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
    if not row['customer_code'] or not row['factory_code'] or not row['secret_fingerprint']:
        raise GatewayAuthError('gateway credential scope is incomplete')
    secret = _secret_for(gateway_id)
    fingerprint = hashlib.sha256(secret.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(fingerprint, row['secret_fingerprint']):
        raise GatewayAuthError('gateway secret configuration does not match credential')
    body_hash = hashlib.sha256(bytes(body)).hexdigest()
    message = f'{gateway_id}\n{timestamp}\n{nonce}\n{body_hash}'.encode('utf-8')
    expected = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise GatewayAuthError('invalid gateway signature')
    try:
        now = int(time.time())
        db.execute('DELETE FROM iot_gateway_nonce WHERE expires_at IS NULL OR expires_at < ?',
                   (now,))
        db.execute(
            'INSERT INTO iot_gateway_nonce(gateway_code,nonce,expires_at) VALUES(?,?,?)',
            (gateway_id, nonce, now + int(max_skew)),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if 'UNIQUE constraint failed' in str(exc):
            raise GatewayAuthError('gateway nonce replayed') from exc
        raise
    return dict(row)
