"""轻量级内存限流器,作为 ``flask-limiter`` 不可用时兜底。

设计目标:
- 无第三方依赖,开箱即用
- 与 ``flask_limiter.Limiter`` 默认行为对齐(按 remote_addr 计数)
- 支持默认全局限流 + 单路由独立限流 + 豁免
- 多线程安全,自动清理过期时间戳

生产环境建议:
- 多进程部署时内存计数器会按进程隔离,建议使用 ``flask-limiter`` + RedisStorage
- 单机/内网/测试环境,内存限流已足够

用法:
    from utils.rate_limiter import SimpleRateLimiter
    limiter = SimpleRateLimiter(default_limits=['200 per day', '50 per hour'])
    limiter.init_app(app)

    @app.route('/api/login', methods=['POST'])
    @limiter.limit('10 per minute')
    def login():
        ...
"""

import threading
import time
from collections import defaultdict
from functools import wraps


class SimpleRateLimiter:
    """基于滑动窗口思想的内存固定窗口限流器。"""

    _UNITS = {
        'second': 1,
        'seconds': 1,
        'minute': 60,
        'minutes': 60,
        'hour': 3600,
        'hours': 3600,
        'day': 86400,
        'days': 86400,
    }

    def __init__(self, key_func=None, default_limits=None):
        self.key_func = key_func or self._default_key_func
        self.default_limits = self._parse_limits(default_limits or [])
        self.route_limits = {}
        self._storage = defaultdict(list)
        self._lock = threading.RLock()
        self._app = None

    # ----------------------------- 公共 API -----------------------------

    def init_app(self, app):
        """注册到 Flask app。"""
        self._app = app
        app.before_request(self._check_limit)

    def limit(self, *limits):
        """装饰器:为某个路由单独设置限流规则。

        示例:
            @limiter.limit('10 per minute')
            def login(): ...
        """
        parsed = self._parse_limits(list(limits))

        def decorator(f):
            f._simple_rate_limits = parsed
            return f

        return decorator

    def exempt(self, f):
        """装饰器: exempt 某个路由不受限流。"""
        f._simple_rate_exempt = True
        return f

    # ----------------------------- 内部实现 -----------------------------

    @staticmethod
    def _default_key_func():
        from flask import request

        return request.remote_addr or 'anonymous'

    @classmethod
    def _parse_limits(cls, limits):
        """把 ['200 per day', '50 per hour'] 解析成 [(200, 86400), (50, 3600)]。"""
        parsed = []
        for limit in limits:
            if not limit:
                continue
            parts = limit.lower().split()
            if len(parts) != 3 or parts[1] != 'per':
                raise ValueError(f'Invalid rate limit: {limit}')
            count = int(parts[0])
            unit = parts[2]
            if unit not in cls._UNITS:
                raise ValueError(f'Unknown time unit: {unit}')
            parsed.append((count, cls._UNITS[unit]))
        return parsed

    def _get_limits_for_request(self, view_func):
        """返回适用于当前请求的限制规则。"""
        if view_func is None:
            return self.default_limits
        # 如果视图函数有自己的规则,优先使用
        own = getattr(view_func, '_simple_rate_limits', None)
        if own is not None:
            return own
        return self.default_limits

    def _is_exempt(self, view_func):
        if view_func is None:
            return False
        return getattr(view_func, '_simple_rate_exempt', False)

    def _clean_storage(self, now, max_window):
        """清理所有超过最大窗口的过期时间戳,避免内存无限增长。"""
        cutoff = now - max_window
        for key in list(self._storage.keys()):
            timestamps = self._storage[key]
            self._storage[key] = [t for t in timestamps if t > cutoff]
            if not self._storage[key]:
                del self._storage[key]

    def _check_limit(self):
        """Flask before_request 钩子。"""
        from flask import request, jsonify

        if self._app is None:
            return None

        # 仅对 API 接口做限流；静态资源与页面本身不计入，
        # 避免管理后台一次性加载几十个 CSS/JS 就瞬间打爆 50/hour 额度
        if not request.path.startswith('/api/'):
            return None

        view_func = self._app.view_functions.get(request.endpoint)
        if self._is_exempt(view_func):
            return None

        limits = self._get_limits_for_request(view_func)
        if not limits:
            return None

        key = self.key_func()
        now = time.time()
        max_window = max(window for _, window in limits)

        with self._lock:
            self._clean_storage(now, max_window)
            timestamps = self._storage[key]

            for count, window in limits:
                # 计算当前窗口内请求数
                current = sum(1 for t in timestamps if now - t < window)
                if current >= count:
                    return jsonify({
                        'error': 'Too many requests',
                        'retry_after': int(window - (now % window)) or 1,
                    }), 429

            timestamps.append(now)
        return None
