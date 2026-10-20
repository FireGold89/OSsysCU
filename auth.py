"""簡易 Session 登入（Phase 1 — 環境變數用戶）"""
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import wraps

from flask import jsonify, request, session

import access_control
import database as db

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
    '/api/admin',
)

_WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})
_LOGIN_ROLES = frozenset({'admin', 'user', 'qs', 'finance', 'viewer'})
# 財務帳號可改 Master List（開票／報價主檔），不可改地盤付款、ISO、系統設定
_FINANCE_WRITE_PREFIXES = (
    '/api/master/item',
    '/api/master/quotations',
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
            if role not in _LOGIN_ROLES:
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


def hash_password(password):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), 120_000)
    return f'pbkdf2${salt}${dk.hex()}'


def verify_password(password, stored):
    parts = (stored or '').split('$')
    if len(parts) != 3 or parts[0] != 'pbkdf2':
        return False
    salt, hexd = parts[1], parts[2]
    dk = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt.encode('ascii'), 120_000)
    return hmac.compare_digest(dk.hex(), hexd)


def authenticate(username, password):
    name = (username or '').strip()
    pwd = password or ''
    if not name or not pwd:
        return None
    try:
        row = db.get_app_user_by_username(name)
    except Exception:
        row = None
    if row:
        if not row.get('is_active'):
            return None
        if verify_password(pwd, row.get('password_hash')):
            return {'username': row['username'], 'role': row.get('role') or 'qs', 'id': row['id']}
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


def actor_for_session():
    """目前登入者的有效權限（資料庫帳號即時讀取，環境變數帳號用角色預設）"""
    user = current_user()
    if not user:
        return None
    row = None
    try:
        row = db.get_app_user_by_username(user['username'])
    except Exception:
        row = None
    if row:
        if not row.get('is_active'):
            return {'inactive': True, 'username': user['username']}
        role = (row.get('role') or 'qs').strip().lower()
        raw = None
        if row.get('perm_json'):
            try:
                raw = json.loads(row['perm_json'])
            except json.JSONDecodeError:
                raw = None
        is_admin = role == 'admin'
        perms = access_control.preset_matrix('admin') if is_admin else access_control.normalize_matrix(raw, role)
        return {
            'username': row['username'],
            'role': role,
            'id': row['id'],
            'display_name': row.get('display_name'),
            'is_admin': is_admin,
            'perms': perms,
            'inactive': False,
        }
    role = (user.get('role') or 'user').strip().lower()
    is_admin = role == 'admin'
    return {
        'username': user['username'],
        'role': role,
        'is_admin': is_admin,
        'perms': access_control.preset_matrix('admin' if is_admin else role),
        'inactive': False,
        'from_env': True,
    }


def auth_status_payload(user=None):
    """供 /api/auth/me 回傳 Session 設定（不含密碼）"""
    u = user or current_user()
    if not u:
        return {
            'auth_required': is_enabled(),
            'user': None,
        }
    actor = actor_for_session()
    if not actor or actor.get('inactive'):
        return {
            'auth_required': True,
            'user': None,
        }
    base_user = {
        'username': actor.get('username'),
        'role': actor.get('role'),
        'display_name': actor.get('display_name'),
        'is_admin': bool(actor.get('is_admin')),
        'from_env': bool(actor.get('from_env')),
    }
    return {
        'auth_required': True,
        'user': base_user,
        'permissions': actor.get('perms') or {},
        'idle_timeout_seconds': idle_timeout_seconds('admin' if actor.get('is_admin') else 'user'),
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


def role_allows_write(role, path):
    """寫入權限：admin 全部；qs/user 除管理員 API；finance 僅 Master；viewer 只讀"""
    role = (role or 'user').strip().lower()
    if role == 'admin':
        return True
    if role == 'viewer':
        return False
    if requires_admin(path, 'POST'):
        return False
    if role == 'finance':
        return any(path == p or path.startswith(p + '/') for p in _FINANCE_WRITE_PREFIXES)
    return role in ('user', 'qs')


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
    actor = actor_for_session()
    if not actor or actor.get('inactive'):
        logout_user()
        return jsonify({'success': False, 'error': '帳號已停用，請重新登入'}), 401
    if path != '/api/auth/logout':
        err = access_control.decide(actor, request.method, path)
        if err:
            return jsonify({'success': False, 'error': err}), 403
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
