"""MES 数据库备份脚本。

支持 SQLite 和 PostgreSQL 两种模式,根据 MES_DB_TYPE 环境变量自动选择。
备份文件按日期命名,保留最近 N 份,超出自动清理。

用法:
    # SQLite(默认)
    python scripts/backup_database.py

    # PostgreSQL
    MES_DB_TYPE=postgresql MES_DB_HOST=... python scripts/backup_database.py

    # 自定义保留份数和输出目录
    python scripts/backup_database.py --keep 14 --out /data/backups

建议配合系统定时任务(cron / Windows 任务计划)每日执行。
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from utils.database import DB_PATH, DB_TYPE, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS  # noqa: E402


def backup_sqlite(out_dir, keep):
    """备份 SQLite 数据库文件(含 WAL/SHM)为一个 zip。"""
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_path = os.path.join(out_dir, f'mes_sqlite_{timestamp}.zip')

    if not os.path.exists(DB_PATH):
        print(f'数据库文件不存在: {DB_PATH}', file=sys.stderr)
        return 1

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, os.path.basename(DB_PATH))
        for suffix in ('-wal', '-shm'):
            side = DB_PATH + suffix
            if os.path.exists(side):
                zf.write(side, os.path.basename(side))
    print(f'已备份 SQLite -> {zip_path}')

    _cleanup(out_dir, 'mes_sqlite_', '.zip', keep)
    return 0


def backup_postgresql(out_dir, keep):
    """使用 pg_dump 备份 PostgreSQL 数据库。"""
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dump_path = os.path.join(out_dir, f'mes_pg_{timestamp}.dump')

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASS
    cmd = [
        'pg_dump',
        '-h', DB_HOST,
        '-p', str(DB_PORT),
        '-U', DB_USER,
        '-Fc',  # custom format,支持选择性恢复
        '-f', dump_path,
        DB_NAME,
    ]
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print('未找到 pg_dump,请确认 PostgreSQL 客户端工具已安装', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f'pg_dump 失败: {exc.stderr}', file=sys.stderr)
        return 1
    print(f'已备份 PostgreSQL -> {dump_path}')

    _cleanup(out_dir, 'mes_pg_', '.dump', keep)
    return 0


def _cleanup(out_dir, prefix, suffix, keep):
    """保留最近 keep 份备份,删除更旧的。"""
    if keep <= 0:
        return
    files = sorted(
        f for f in os.listdir(out_dir)
        if f.startswith(prefix) and f.endswith(suffix)
    )
    for old in files[:-keep]:
        os.remove(os.path.join(out_dir, old))
        print(f'已清理旧备份: {old}')


def main():
    parser = argparse.ArgumentParser(description='MES 数据库备份')
    parser.add_argument('--out', default=os.path.join(PROJECT_ROOT, 'backups'),
                        help='备份输出目录(默认: backups/)')
    parser.add_argument('--keep', type=int, default=30,
                        help='保留最近 N 份备份(默认: 30)')
    args = parser.parse_args()

    print(f'数据库类型: {DB_TYPE}')
    if DB_TYPE == 'postgresql':
        return backup_postgresql(args.out, args.keep)
    return backup_sqlite(args.out, args.keep)


if __name__ == '__main__':
    raise SystemExit(main())
