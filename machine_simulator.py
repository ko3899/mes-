"""AIM机台V1/V2命令行模拟器。"""
import argparse
import hashlib
import hmac
import socket


def main():
    parser = argparse.ArgumentParser(description='AIM机台通讯模拟器')
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--protocol', choices=('1', '2'), default='2')
    parser.add_argument('--device', default='AIM001')
    parser.add_argument('--station', default='ST01')
    parser.add_argument('--cavity', default='C1')
    parser.add_argument('--request-no', default='SIM001')
    parser.add_argument('--sn', required=True)
    parser.add_argument('--secret', default='', help='V2共享密钥；端点未配置时留空')
    args = parser.parse_args()
    if args.protocol == '1':
        frame = args.sn
    else:
        frame = '|'.join(('REQ', '2', args.device, args.station, args.cavity,
                          args.request_no, args.sn))
        if args.secret:
            signature = hmac.new(
                args.secret.encode('utf-8'), frame.encode('utf-8'), hashlib.sha256
            ).hexdigest()
            frame += '|' + signature
    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        connection.sendall((frame + '\r\n').encode('utf-8'))
        response = connection.makefile('rb').readline().decode('utf-8').rstrip()
    print(response)


if __name__ == '__main__':
    main()
