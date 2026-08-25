"""AI质检蓝图 - 智能分析（配置驱动，默认 DeepSeek / OpenAI 兼容协议）"""
import requests

from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import admin_required, login_required, permission_required

ai_bp = Blueprint('ai', __name__)

# OpenAI 兼容端点（DeepSeek 等），可由 ai_provider 配置扩展
DEFAULT_MODEL = 'deepseek-chat'
_PROVIDER_ENDPOINTS = {
    'deepseek': 'https://api.deepseek.com/chat/completions',
    'openai': 'https://api.openai.com/v1/chat/completions',
}
SYSTEM_PROMPT = (
    '你是工厂 MES 系统的质检分析助手。请基于用户提供的生产/质检描述，'
    '给出专业、简洁、可执行的分析结论，输出中文。'
    '涉及不合格品时，请明确建议处置方式（返工/报废/让步接收）及依据。'
)


def _load_ai_config():
    rows = get_db().execute(
        """SELECT config_key, config_value FROM sys_config
           WHERE config_key IN ('ai_enabled','ai_provider','ai_api_key','ai_model')"""
    ).fetchall()
    values = {row['config_key']: row['config_value'] for row in rows}
    enabled = str(values.get('ai_enabled') or '').strip().lower() in {
        '1', 'true', 'yes', 'on',
    }
    provider = str(values.get('ai_provider') or '').strip().lower() or 'deepseek'
    return {
        'enabled': enabled,
        'provider': provider,
        'api_key': str(values.get('ai_api_key') or '').strip(),
        'model': str(values.get('ai_model') or '').strip() or DEFAULT_MODEL,
    }


def _call_chat_completion(cfg, user_text, context=None):
    """调用 OpenAI 兼容 chat/completions 接口。"""
    endpoint = _PROVIDER_ENDPOINTS.get(cfg['provider'])
    if not endpoint:
        raise ValueError(f"不支持的 AI 提供方: {cfg['provider']}")
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    prompt = user_text
    if context:
        prompt = f'上下文：{context}\n\n问题：{user_text}'
    messages.append({'role': 'user', 'content': prompt})
    resp = requests.post(
        endpoint,
        headers={
            'Authorization': f"Bearer {cfg['api_key']}",
            'Content-Type': 'application/json',
        },
        json={
            'model': cfg['model'],
            'messages': messages,
            'temperature': 0.3,
            'max_tokens': 1024,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        'reply': data['choices'][0]['message']['content'],
        'model': data.get('model') or cfg['model'],
        'usage': data.get('usage'),
    }


@ai_bp.route('/api/ai/inspect', methods=['POST'])
@permission_required('quality:write')
def ai_inspect():
    """AI 智能分析：配置驱动调用大模型（默认 DeepSeek）。

    请求体: {"text": "分析内容/问题", "context": "可选上下文"}
    """
    d = request.get_json(silent=True) or {}
    text = str(d.get('text') or '').strip()
    if not text:
        return jsonify({'code': 400, 'message': '缺少分析内容 text'}), 400

    cfg = _load_ai_config()
    if not cfg['enabled']:
        return jsonify({
            'code': 503,
            'message': 'AI 服务未启用：请在 系统管理-AI配置 中开启并保存 API Key',
        }), 503
    if not cfg['api_key']:
        return jsonify({
            'code': 503,
            'message': 'AI 服务未配置 API Key：请在 系统管理-AI配置 中填写',
        }), 503

    try:
        result = _call_chat_completion(cfg, text, d.get('context'))
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status in (401, 403):
            return jsonify({'code': 502, 'message': 'AI API Key 无效或无权限，请检查配置'}), 502
        if status == 429:
            return jsonify({'code': 502, 'message': 'AI 服务请求过于频繁，请稍后再试'}), 502
        return jsonify({'code': 502, 'message': f'AI 服务调用失败(HTTP {status})'}), 502
    except requests.exceptions.Timeout:
        return jsonify({'code': 504, 'message': 'AI 服务响应超时，请重试'}), 504
    except requests.exceptions.RequestException:
        return jsonify({'code': 502, 'message': '无法连接 AI 服务，请检查网络'}), 502

    return jsonify({'code': 0, 'data': {
        'reply': result['reply'],
        'model': result['model'],
        'provider': cfg['provider'],
        'usage': result['usage'],
    }})


@ai_bp.route('/api/ai/config')
@admin_required
def ai_config():
    """AI配置"""
    cfg = _load_ai_config()
    return jsonify({'code': 0, 'data': {
        'ai_enabled': cfg['enabled'],
        'ai_provider': cfg['provider'],
        'ai_api_key_configured': bool(cfg['api_key']),
        'ai_model': cfg['model'],
    }})


@ai_bp.route('/api/ai/config/save', methods=['POST'])
@admin_required
def ai_config_save():
    """保存AI配置"""
    d = request.json
    db = get_db()
    allowed_keys = {
        'ai_enabled',
        'ai_provider',
        'ai_api_key',
        'ai_model',
    }
    for key, val in d.items():
        if key not in allowed_keys:
            continue
        if key == 'ai_api_key' and not str(val or '').strip():
            continue
        existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
        if existing:
            db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
        else:
            db.execute(
                "INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)",
                (key, val, 'string'),
            )
    db.commit()
    return jsonify({'code': 0, 'message': 'AI配置已保存'})
