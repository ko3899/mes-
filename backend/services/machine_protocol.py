"""AIM机台V1/V2 TCP报文编解码。"""
from dataclasses import dataclass
import hashlib
import hmac
import uuid


MAX_FRAME_BYTES = 4096


class ProtocolError(ValueError):
    """机台报文不符合协议。"""


@dataclass(frozen=True)
class MachineRequest:
    protocol_version: int
    device_code: str
    station_code: str
    cavity_code: str
    request_no: str
    sn: str


@dataclass(frozen=True)
class AccessDecision:
    decision: str
    reason_code: str
    reason_message: str = ''
    laser_template: str = ''
    inspection_template: str = ''

    @classmethod
    def allow(cls, laser_template='', inspection_template='', message='允许加工'):
        return cls('L1', 'OK', message, laser_template, inspection_template)

    @classmethod
    def reject(cls, reason_code, message=''):
        return cls('L3', reason_code, message)


def _endpoint_value(endpoint, key, default=''):
    try:
        value = endpoint[key]
    except (KeyError, TypeError, IndexError):
        value = default
    return default if value is None else value


def _decode_frame(frame, encoding):
    if not isinstance(frame, (bytes, bytearray)):
        raise ProtocolError('报文必须是字节数据')
    if len(frame) > MAX_FRAME_BYTES + 2:
        raise ProtocolError('报文过长')
    try:
        text = bytes(frame).decode(encoding or 'utf-8')
    except (LookupError, UnicodeDecodeError) as exc:
        raise ProtocolError('报文编码错误') from exc
    if text.endswith('\r\n'):
        text = text[:-2]
    elif text.endswith('\n'):
        text = text[:-1]
    if '\r' in text or '\n' in text:
        raise ProtocolError('报文包含非法换行')
    if not text:
        raise ProtocolError('报文为空')
    if len(text.encode(encoding or 'utf-8')) > MAX_FRAME_BYTES:
        raise ProtocolError('报文过长')
    return text


def parse_request(frame, endpoint):
    """解析一条完整报文，endpoint可以是dict或sqlite Row。"""
    text = _decode_frame(frame, str(_endpoint_value(endpoint, 'encoding', 'utf-8')))
    configured_version = int(_endpoint_value(endpoint, 'protocol_version', 1))
    if text.startswith('REQ|'):
        if configured_version != 2:
            raise ProtocolError('V1端点不接受V2报文')
        parts = text.split('|')
        secret = str(_endpoint_value(endpoint, 'shared_secret', ''))
        if not secret:
            raise ProtocolError('V2端点未配置共享密钥')
        expected_fields = 8
        if len(parts) == 7:
            raise ProtocolError('V2报文缺少签名')
        if len(parts) != expected_fields or parts[0] != 'REQ' or parts[1] != '2':
            raise ProtocolError('V2报文字段或版本错误')
        unsigned_parts = parts[:7]
        _, _, device, station, cavity, request_no, sn = unsigned_parts
        expected_signature = hmac.new(
            secret.encode('utf-8'), '|'.join(unsigned_parts).encode('utf-8'), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(parts[7].lower(), expected_signature):
            raise ProtocolError('V2报文签名错误')
        if not all((device, station, cavity, request_no, sn)):
            raise ProtocolError('V2必填字段为空')
        expected = (
            str(_endpoint_value(endpoint, 'device_code')),
            str(_endpoint_value(endpoint, 'station_code')),
            str(_endpoint_value(endpoint, 'cavity_code')),
        )
        if (device, station, cavity) != expected:
            raise ProtocolError('设备身份与端点配置不匹配')
        return MachineRequest(2, device, station, cavity, request_no, sn)
    if configured_version != 1:
        raise ProtocolError('V2端点不接受V1报文')
    if '|' in text:
        raise ProtocolError('V1序列号包含非法分隔符')
    return MachineRequest(
        1,
        str(_endpoint_value(endpoint, 'device_code')),
        str(_endpoint_value(endpoint, 'station_code')),
        str(_endpoint_value(endpoint, 'cavity_code')),
        uuid.uuid4().hex,
        text,
    )


def _safe_field(value):
    return ''.join(' ' if char in '|\r\n' else char for char in str(value or ''))


def format_response(request, decision, terminator=b'\r\n'):
    """根据请求协议返回精确的线协议响应。"""
    if request.protocol_version == 1:
        return f'<{decision.decision}>'.encode('ascii') + bytes(terminator)
    fields = [
        'ACK', '2', request.request_no, decision.decision,
        decision.reason_code, decision.laser_template,
        decision.inspection_template, decision.reason_message,
    ]
    return ('|'.join(_safe_field(value) for value in fields)).encode('utf-8') + bytes(terminator)


def parse_reader_frame(frame, endpoint):
    """Decode a Hikrobot TCP payload configured without CR/LF delimiters."""
    if not isinstance(frame, (bytes, bytearray)):
        raise ProtocolError('读码器报文必须是字节数据')
    encoding = str(_endpoint_value(endpoint, 'encoding', 'utf-8'))
    try:
        text = bytes(frame).decode(encoding).replace('\x00', '').strip()
    except (LookupError, UnicodeDecodeError) as exc:
        raise ProtocolError('读码器报文编码错误') from exc
    if not text:
        raise ProtocolError('读码器报文为空')
    if ';' in text:
        text = text.split(';', 1)[0].strip()
    return parse_request((text + '\r\n').encode(encoding), endpoint)
