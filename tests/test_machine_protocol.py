import os
import sys

import pytest
import hashlib
import hmac


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from services.machine_protocol import (  # noqa: E402
    AccessDecision,
    ProtocolError,
    format_response,
    parse_request,
    parse_reader_frame,
)


ENDPOINT = {
    'protocol_version': 1,
    'device_code': 'AIM001',
    'station_code': 'LASER01',
    'cavity_code': 'CAVITY1',
    'encoding': 'utf-8',
}


def v2_frame(device='AIM001', station='LASER01', cavity='CAVITY1', request_no='1', sn='SN001'):
    unsigned = f'REQ|2|{device}|{station}|{cavity}|{request_no}|{sn}'
    signature = hmac.new(b'secret-key', unsigned.encode(), hashlib.sha256).hexdigest()
    return (unsigned + '|' + signature + '\r\n').encode()


def test_v1_uses_endpoint_identity_and_returns_exact_legacy_response():
    request = parse_request(b'E*612201000816FB10054692B\r\n', ENDPOINT)
    assert request.protocol_version == 1
    assert request.device_code == 'AIM001'
    assert request.station_code == 'LASER01'
    assert request.cavity_code == 'CAVITY1'
    assert request.sn == 'E*612201000816FB10054692B'
    assert request.request_no
    assert format_response(request, AccessDecision.allow()) == b'<L1>\r\n'
    assert format_response(
        request, AccessDecision.reject('UNKNOWN_SN', 'SN不存在')
    ) == b'<L3>\r\n'


def test_noread_is_a_valid_v1_scan_failure_request():
    request = parse_request(b'NoRead\r\n', ENDPOINT)
    assert request.sn == 'NoRead'


def test_v2_parses_identity_and_formats_enhanced_response():
    endpoint = dict(ENDPOINT, protocol_version=2, shared_secret='secret-key')
    request = parse_request(v2_frame(request_no='000123'), endpoint)
    decision = AccessDecision.allow('LASER-T08', 'CCD-T16', '允许加工')
    assert request.request_no == '000123'
    assert request.sn == 'SN001'
    assert format_response(request, decision) == (
        'ACK|2|000123|L1|OK|LASER-T08|CCD-T16|允许加工\r\n'.encode('utf-8')
    )


def test_v2_reject_response_sanitizes_delimiters_and_newlines():
    endpoint = dict(ENDPOINT, protocol_version=2, shared_secret='secret-key')
    request = parse_request(v2_frame(request_no='9'), endpoint)
    response = format_response(
        request, AccessDecision.reject('WRONG_STEP', '错误|工序\r\n请检查')
    ).decode('utf-8')
    assert response == 'ACK|2|9|L3|WRONG_STEP|||错误 工序  请检查\r\n'


@pytest.mark.parametrize('frame', [
    b'REQ|3|AIM001|LASER01|CAVITY1|1|SN001\r\n',
    b'REQ|2|AIM001|LASER01|CAVITY1|SN001\r\n',
    b'REQ|2|AIM001|LASER01|CAVITY1|1|\r\n',
])
def test_v2_rejects_invalid_frames(frame):
    with pytest.raises(ProtocolError):
        parse_request(frame, dict(ENDPOINT, protocol_version=2, shared_secret='secret-key'))


def test_v2_identity_must_match_endpoint():
    with pytest.raises(ProtocolError, match='设备身份'):
        parse_request(
            v2_frame(device='OTHER'),
            dict(ENDPOINT, protocol_version=2, shared_secret='secret-key'),
        )


def test_rejects_embedded_newline_and_oversized_frame():
    with pytest.raises(ProtocolError):
        parse_request(b'SN001\nSN002\r\n', ENDPOINT)
    with pytest.raises(ProtocolError, match='过长'):
        parse_request((b'A' * 4097) + b'\r\n', ENDPOINT)


def test_uses_configured_encoding():
    endpoint = dict(ENDPOINT, encoding='gbk')
    request = parse_request('产品序列号001\r\n'.encode('gbk'), endpoint)
    assert request.sn == '产品序列号001'


def test_v2_requires_valid_hmac_when_endpoint_has_shared_secret():
    endpoint = dict(ENDPOINT, protocol_version=2, shared_secret='secret-key')
    unsigned = 'REQ|2|AIM001|LASER01|CAVITY1|S1|SN001'
    signature = hmac.new(b'secret-key', unsigned.encode(), hashlib.sha256).hexdigest()
    parsed = parse_request((unsigned + '|' + signature + '\r\n').encode(), endpoint)
    assert parsed.sn == 'SN001'
    with pytest.raises(ProtocolError, match='签名'):
        parse_request((unsigned + '|bad\r\n').encode(), endpoint)
    with pytest.raises(ProtocolError, match='签名'):
        parse_request((unsigned + '\r\n').encode(), endpoint)


def test_endpoint_protocol_cannot_be_downgraded_and_v2_requires_secret():
    with pytest.raises(ProtocolError, match='V2'):
        parse_request(b'SN001\r\n', dict(ENDPOINT, protocol_version=2, shared_secret='secret'))
    with pytest.raises(ProtocolError, match='密钥'):
        parse_request(
            b'REQ|2|AIM001|LASER01|CAVITY1|1|SN001\r\n',
            dict(ENDPOINT, protocol_version=2, shared_secret=''),
        )
    with pytest.raises(ProtocolError, match='V1'):
        parse_request(
            b'REQ|2|AIM001|LASER01|CAVITY1|1|SN001\r\n',
            ENDPOINT,
        )


def test_hikrobot_reader_frame_accepts_idle_payload_and_strips_optional_fields():
    endpoint = dict(ENDPOINT)
    request = parse_reader_frame(b'SN001;ISO15415=A\x00', endpoint)
    assert request.sn == 'SN001'
    assert format_response(request, AccessDecision.allow(), b'') == b'<L1>'
