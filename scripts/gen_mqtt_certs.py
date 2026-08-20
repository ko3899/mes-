"""生成 MES MQTT 双向 TLS(mTLS)证书链。

生成内容:
  - CA 根证书(自签)
  - 中央消费者客户端证书
  - 每个边缘网关的客户端证书(按 gateway_id)
  - mosquitto broker 所需配置片段(启用 mTLS + ACL)

证书用于边缘网关 <-> MQTT broker <-> 中央消费者之间的双向认证。
私钥不上传 Git,仅在本地 certs/ 目录生成。

依赖:openssl(系统已安装)。

用法:
    # 初始化 CA + 中央消费者证书
    python scripts/gen_mqtt_certs.py init

    # 为某网关签发证书
    python scripts/gen_mqtt_certs.py gateway GW-F01-A

    # 轮换某网关证书(吊销旧的、签发新的)
    python scripts/gen_mqtt_certs.py rotate GW-F01-A

    # 查看已签发证书
    python scripts/gen_mqtt_certs.py list
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERTS_DIR = os.path.join(PROJECT_ROOT, 'certs', 'mqtt')
CA_DIR = os.path.join(CERTS_DIR, 'ca')
GATEWAYS_DIR = os.path.join(CERTS_DIR, 'gateways')
CENTRAL_DIR = os.path.join(CERTS_DIR, 'central')


def _run(cmd, **kwargs):
    """运行命令,失败时打印输出并退出。"""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print('命令失败:', ' '.join(cmd), file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(1)
    return result


def _openssl_available():
    return shutil.which('openssl') is not None


def init():
    """初始化 CA 并签发中央消费者证书。"""
    if not _openssl_available():
        print('未找到 openssl,请先安装', file=sys.stderr)
        return 1
    os.makedirs(CA_DIR, exist_ok=True)
    os.makedirs(CENTRAL_DIR, exist_ok=True)

    ca_key = os.path.join(CA_DIR, 'ca.key')
    ca_crt = os.path.join(CA_DIR, 'ca.pem')

    if os.path.exists(ca_crt):
        print(f'CA 已存在: {ca_crt}')
        print('如需重新生成,请先删除 certs/mqtt/ca/ 目录')
    else:
        print('生成 CA 私钥...')
        _run(['openssl', 'genrsa', '-out', ca_key, '4096'])
        print('生成 CA 根证书(10年)...')
        _run([
            'openssl', 'req', '-x509', '-new', '-nodes',
            '-key', ca_key,
            '-sha256', '-days', '3650',
            '-out', ca_crt,
            '-subj', '/C=CN/O=MES-Factory/CN=MES-MQTT-CA',
        ])
        print(f'CA 证书: {ca_crt}')

    # 中央消费者证书
    _issue_client_cert(
        'central-consumer', CENTRAL_DIR, 'MES-Central-Consumer',
        ca_key, ca_crt,
    )
    print('\n初始化完成。分发:')
    print(f'  CA 证书:    {ca_crt} -> 所有节点(broker/网关/消费者)都需要')
    print(f'  消费者证书: {CENTRAL_DIR}/  -> 仅部署在中央 MES 侧')
    return 0


def gateway(gateway_id):
    """为指定网关签发客户端证书。"""
    ca_key = os.path.join(CA_DIR, 'ca.key')
    ca_crt = os.path.join(CA_DIR, 'ca.pem')
    if not os.path.exists(ca_crt):
        print('CA 不存在,请先运行 init', file=sys.stderr)
        return 1
    out_dir = os.path.join(GATEWAYS_DIR, gateway_id)
    os.makedirs(out_dir, exist_ok=True)
    _issue_client_cert(
        gateway_id, out_dir, f'MES-Gateway-{gateway_id}',
        ca_key, ca_crt,
    )
    print(f'\n网关 {gateway_id} 证书已生成: {out_dir}/')
    print('将该目录下的 .pem(证书)和 .key(私钥)部署到网关,')
    print(f'并确保网关配置 MES_EDGE_MQTT_CA 指向 {ca_crt}')
    return 0


def rotate(gateway_id):
    """轮换网关证书:归档旧证书,签发新证书。"""
    out_dir = os.path.join(GATEWAYS_DIR, gateway_id)
    if not os.path.isdir(out_dir):
        print(f'网关 {gateway_id} 无现存证书,请用 gateway 子命令签发', file=sys.stderr)
        return 1
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    archive = os.path.join(GATEWAYS_DIR, 'archived', f'{gateway_id}_{ts}')
    os.makedirs(os.path.dirname(archive), exist_ok=True)
    shutil.move(out_dir, archive)
    print(f'旧证书已归档: {archive}')
    print('请在 broker 侧更新 CRL 或移除旧证书信任,然后部署新证书。')
    return gateway(gateway_id)


def list_certs():
    """列出已签发的证书。"""
    if not os.path.isdir(GATEWAYS_DIR):
        print('暂无网关证书')
        return 0
    print('已签发证书:')
    if os.path.isdir(CENTRAL_DIR):
        print(f'  central-consumer: {CENTRAL_DIR}/')
    for name in sorted(os.listdir(GATEWAYS_DIR)):
        if name == 'archived':
            continue
        full = os.path.join(GATEWAYS_DIR, name)
        if os.path.isdir(full):
            print(f'  {name}: {full}/')
    archived = os.path.join(GATEWAYS_DIR, 'archived')
    if os.path.isdir(archived):
        print('已归档(轮换下来的旧证书):')
        for name in sorted(os.listdir(archived)):
            print(f'  {name}')
    return 0


def _issue_client_cert(name, out_dir, cn, ca_key, ca_crt):
    """签发一张客户端证书(私钥 + CSR + 用 CA 签名)。"""
    key = os.path.join(out_dir, f'{name}.key')
    csr = os.path.join(out_dir, f'{name}.csr')
    crt = os.path.join(out_dir, f'{name}.pem')

    print(f'生成 {name} 私钥...')
    _run(['openssl', 'genrsa', '-out', key, '2048'])
    print(f'生成 {name} CSR...')
    _run([
        'openssl', 'req', '-new',
        '-key', key,
        '-out', csr,
        '-subj', f'/C=CN/O=MES-Factory/CN={cn}',
    ])
    print(f'用 CA 签发 {name} 证书(2年)...')
    _run([
        'openssl', 'x509', '-req',
        '-in', csr,
        '-CA', ca_crt,
        '-CAkey', ca_key,
        '-CAcreateserial',
        '-out', crt,
        '-days', '730',
        '-sha256',
    ])
    os.remove(csr)


def broker_config():
    """输出 mosquitto broker 启用 mTLS 的配置片段。"""
    ca_crt = os.path.join(CA_DIR, 'ca.pem')
    print(f'''# mosquitto.conf - MQTT mTLS 配置片段
# 放到 /etc/mosquitto/conf.d/mes-mtls.conf

# 监听 8883,强制双向 TLS
listener 8883
protocol mqtt

# 信任的 CA(校验客户端证书)
cafile {ca_crt}
certfile /etc/mosquitto/certs/broker.pem
keyfile /etc/mosquitto/certs/broker.key
require_certificate true
use_identity_as_username true

# ACL:网关只能发布自己的事件主题、订阅自己的 ack 主题
# 详见 docs/mqtt-certificate-management.md
acl_file /etc/mosquitto/acl.conf
''')
    return 0


def main():
    parser = argparse.ArgumentParser(description='MES MQTT mTLS 证书管理')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init', help='初始化 CA 并签发中央消费者证书')
    p_gw = sub.add_parser('gateway', help='为网关签发证书')
    p_gw.add_argument('gateway_id', help='网关 ID,如 GW-F01-A')
    p_rot = sub.add_parser('rotate', help='轮换网关证书')
    p_rot.add_argument('gateway_id')
    sub.add_parser('list', help='列出已签发证书')
    sub.add_parser('broker-config', help='输出 mosquitto mTLS 配置片段')
    args = parser.parse_args()

    if args.cmd == 'init':
        return init()
    if args.cmd == 'gateway':
        return gateway(args.gateway_id)
    if args.cmd == 'rotate':
        return rotate(args.gateway_id)
    if args.cmd == 'list':
        return list_certs()
    if args.cmd == 'broker-config':
        return broker_config()
    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
