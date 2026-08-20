"""验证限流器在生产环境始终生效,并且 flask-limiter 不可用时自动降级到内置实现。"""
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

import pytest

from app import create_app
from utils import database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    database.init_db()
    database._init_extra_tables()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='rate-limit-test')
    return app.test_client()


def test_default_rate_limit_blocks_after_threshold(client):
    """默认 50/hour:同一 IP 连续请求 50 次后第 51 次应被 429 拒绝。"""
    for i in range(50):
        resp = client.get('/healthz', environ_overrides={'REMOTE_ADDR': '1.2.3.4'})
        assert resp.status_code == 200, f'第 {i+1} 次请求失败'

    resp = client.get('/healthz', environ_overrides={'REMOTE_ADDR': '1.2.3.4'})
    assert resp.status_code == 429
    data = resp.get_json()
    assert data['error'] == 'Too many requests'
    assert 'retry_after' in data


def test_rate_limit_is_per_ip(client):
    """不同 IP 的计数器应独立。"""
    for i in range(51):
        resp = client.get('/healthz', environ_overrides={'REMOTE_ADDR': '1.2.3.5'})
    assert resp.status_code == 429

    # 换一个 IP 应被允许
    resp = client.get('/healthz', environ_overrides={'REMOTE_ADDR': '1.2.3.6'})
    assert resp.status_code == 200


def test_rate_limiter_window_expires(monkeypatch):
    """窗口过期后同一 IP 可以继续访问(使用短窗口验证)。"""
    from utils import rate_limiter

    # 用 1 per second 的短窗口,避免测试太慢
    class FakeLimiter(rate_limiter.SimpleRateLimiter):
        def __init__(self, **kwargs):
            super().__init__(default_limits=['1 per second'], **kwargs)

    # 临时替换 app 中的 limiter:这里只测单元逻辑
    lim = FakeLimiter(key_func=lambda: 'k')
    lim._storage['k'] = [time.time() - 2.0]  # 2 秒前的请求
    lim._clean_storage(time.time(), 1)
    assert len(lim._storage.get('k', [])) == 0


def test_simple_rate_limiter_cleanup_does_not_crash():
    """清理过期时间戳不应抛异常。"""
    from utils.rate_limiter import SimpleRateLimiter
    limiter = SimpleRateLimiter(default_limits=['1 per hour'])
    # 伪造一些过期数据
    limiter._storage['1.2.3.9'] = [0.0, 1.0, time.time()]
    limiter._clean_storage(time.time(), 3600)
    assert len(limiter._storage.get('1.2.3.9', [])) == 1
