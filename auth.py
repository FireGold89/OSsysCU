"""簡易 Session 登入（Phase 1 — 環境變數用戶）"""
import hmac
import json
import os
import time
from functools import wraps

from flask import jsonify, request, session

SESSION_USER_KEY = 'auth_user'
SESSION_ROLE_KEY = 'auth_role'
SESSION_ACTIVITY_KEY = 'auth_last_activity'

_PUBLIC_API = frozenset({
    '/api/auth/login',
    '/api/system/status',
})

_ADMIN_API_PREFIXES = (
    '/api/settings',
    '/api/system/restore-db',
    '/api/system/restore-uploads',
)


def is_enabled():
    """已設定登入密碼或 AUTH_USERS 時啟用"""
    if os.environ.get('AUTH_ENABLED', '').strip().lower() in ('0', 'false', 'no'):
        return False
    if os.environ.get('AUTH_USERS', '').strip():
        return True
    if os.environ.get('APP_ADMIN_PASSWORD', '').strip():
        return True
    if os.environ.get('APP_LOGIN_PASSWORD', '').strip():
        return True
    return False


def secret_key():
    key = os.environ.get('SECRET_KEY', '').strip()
    if key:
        return key
    # 本機未設定時每次 restart session 失效；生產請設 SECRET_KEY
    return 'ossyscu-dev-insecure-change-me'


def session_lifetime_days():
    try:
        return max(1, int(os.environ.get('AUTH_SESSION_DAYS', '1')))
    except ValueError:
        return 1


def idle_timeout_minutes(role):
    """閒置逾時（分鐘）：admin 預設 30，其餘 60"""
    key = 'AUTH_IDLE_MINUTES_ADMIN' if role == 'admin' else 'AUTH_IDLE_MINUTES'
    default = '30' if role == 'admin' else '60'
    try:
        return max(1, int(os.environ.get(key, default)))
    except ValueError:
        return int(default)


def idle_timeout_seconds(role):
    return idle_timeout_minutes(role) * 60


def touch_session():
    session[SESSION_ACTIVITY_KEY] = time.time()


def session_idle_expired(user=None):
    if not is_enabled():
        return False
    u = user or current_user()
    if not u:
        return False
    last = session.get(SESSION_ACTIVITY_KEY)
    if last is None:
        return False
    return time.time() - float(last) > idle_timeout_seconds(u.get('role'))


def _enforce_idle_and_touch(user):
    if session_idle_expired(user):
        logout_user()
        return jsonify({'success': False, 'error': '閒置逾時，請重新登入'}), 401
    touch_session()
    return None


def _clean_env_secret(val):
    """去除 Zeabur 粘贴时常见的前后空白或引号"""
    s = (val or '').strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        s = s[1:-1]
    return s


def _parse_auth_users():
    """從 AUTH_USERS JSON 或 APP_* 環境變數載入用戶"""
    raw = os.environ.get('AUTH_USERS', '').strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'AUTH_USERS JSON 無效: {e}') from e
        if not isinstance(data, list) or not data:
            raise ValueError('AUTH_USERS 須為非空陣列')
        users = []
        for item in data:
            if not isinstance(item, dict):
                continue
            username = (item.get('username') or item.get('user') or '').strip()
            password = _clean_env_secret(item.get('password'))
            role = (item.get('role') or 'user').strip().lower()
            if not username or not password:
                continue
            if role not in ('admin', 'user'):
                role = 'user'
            users.append({'username': username, 'password': password, 'role': role})
        if not users:
            raise ValueError('AUTH_USERS 內無有效用戶')
        return users

    users = []
    admin_user = _clean_env_secret(os.environ.get('APP_ADMIN_USER', 'admin')) or 'admin'
    admin_pass = _clean_env_secret(os.environ.get('APP_ADMIN_PASSWORD', ''))
    qs_user = _clean_env_secret(os.environ.get('APP_LOGIN_USER', 'qs')) or 'qs'
    qs_pass = _clean_env_secret(os.environ.get('APP_LOGIN_PASSWORD', ''))

    # 只设 APP_LOGIN_PASSWORD 时，admin 共用同一密码（Zeabur 常见遗漏）
    if not admin_pass and qs_pass:
        admin_pass = qs_pass

    if admin_pass:
        users.append({'username': admin_user, 'password': admin_pass, 'role': 'admin'})

    if qs_pass:
        role = 'user'
        if qs_user.lower() == admin_user.lower() and admin_pass and _safe_eq(qs_pass, admin_pass):
            role = 'admin'
        users.append({'username': qs_user, 'password': qs_pass, 'role': role})

    return users


def load_users():
    if not hasattr(load_users, '_cache'):
        load_users._cache = _parse_auth_users()
    return load_users._cache


def configured_usernames():
    """供 status 诊断：已配置账号名（不含密码）"""
    if not is_enabled():
        return []
    try:
        return [u['username'] for u in load_users()]
    except ValueError:
        return []


def reload_users():
    if hasattr(load_users, '_cache'):
        del load_users._cache
    return load_users()


def _safe_eq(a, b):
    return hmac.compare_digest(str(a or ''), str(b or ''))


def authenticate(username, password):
    name = (username or '').strip()
    pwd = password or ''
    if not name or not pwd:
        return None
    name_lower = name.lower()
    for u in load_users():
        if u['username'].lower() == name_lower and _safe_eq(u['password'], pwd):
            return {'username': u['username'], 'role': u['role']}
    return None


def login_user(user):
    session.permanent = True
    session[SESSION_USER_KEY] = user['username']
    session[SESSION_ROLE_KEY] = user['role']
    touch_session()


def logout_user():
    session.pop(SESSION_USER_KEY, None)
    session.pop(SESSION_ROLE_KEY, None)
    session.pop(SESSION_ACTIVITY_KEY, None)


def auth_status_payload(user=None):
    """供 /api/auth/me 回傳 Session 設定（不含密碼）"""
    u = user or current_user()
    if not u:
        return {
            'auth_required': is_enabled(),
            'user': None,
        }
    return {
        'auth_required': True,
        'user': u,
        'idle_timeout_seconds': idle_timeout_seconds(u.get('role')),
        'session_lifetime_days': session_lifetime_days(),
    }


def current_user():
    if not is_enabled():
        return None
    name = session.get(SESSION_USER_KEY)
    if not name:
        return None
    return {
        'username': name,
        'role': session.get(SESSION_ROLE_KEY) or 'user',
    }


def is_public_api(path, method):
    if path in _PUBLIC_API:
        return True
    if path == '/api/auth/me':
        return True
    if path == '/api/auth/logout' and method == 'POST':
        return True
    return False


def requires_admin(path, method):
    if method == 'OPTIONS':
        return False
    for prefix in _ADMIN_API_PREFIXES:
        if path == prefix or path.startswith(prefix + '/'):
            return True
    return False


def check_request():
    """before_request：回傳 None 或 (response, status)"""
    if not is_enabled():
        return None
    path = request.path or ''
    if not path.startswith('/api/'):
        return None
    if is_public_api(path, request.method):
        return None
    user = current_user()
    if not user:
        return jsonify({'success': False, 'error': '請先登入'}), 401
    if path == '/api/auth/touch' and request.method == 'POST':
        expired = session_idle_expired(user)
        if expired:
            logout_user()
            return jsonify({'success': False, 'error': '閒置逾時，請重新登入'}), 401
        touch_session()
        return None
    blocked = _enforce_idle_and_touch(user)
    if blocked:
        return blocked
    if requires_admin(path, request.method) and user.get('role') != 'admin':
        return jsonify({'success': False, 'error': '需要管理員權限'}), 403
    return None


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if is_enabled() and not current_user():
            return jsonify({'success': False, 'error': '請先登入'}), 401
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_enabled():
            return f(*args, **kwargs)
        user = current_user()
        if not user:
            return jsonify({'success': False, 'error': '請先登入'}), 401
        if user.get('role') != 'admin':
            return jsonify({'success': False, 'error': '需要管理員權限'}), 403
        return f(*args, **kwargs)
    return wrapped
