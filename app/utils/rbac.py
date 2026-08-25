"""
Role-Based Access Control for NETRIX.

Roles
-----
admin  – full system access, manage users, view/edit all projects
user   – create and manage own projects, generate configs, downloads
viewer – read-only access to assigned / own projects (no create/delete/generate)

Permissions are checked via decorators and helper functions.
"""

from functools import wraps
from flask import jsonify, request, abort
from flask_login import current_user

# ---------------------------------------------------------------------------
# Role hierarchy (higher index = more privilege)
# ---------------------------------------------------------------------------
ROLES = ('viewer', 'user', 'admin')

ROLE_LABELS = {
    'admin': 'Administrator',
    'user': 'Network Engineer',
    'viewer': 'Viewer',
}

# Permission catalogue
PERMISSIONS = {
    # Projects
    'project.list':       {'admin', 'user', 'viewer'},
    'project.view':       {'admin', 'user', 'viewer'},
    'project.create':     {'admin', 'user'},
    'project.edit':       {'admin', 'user'},
    'project.delete':     {'admin', 'user'},
    'project.generate':   {'admin', 'user'},
    'project.download':   {'admin', 'user', 'viewer'},
    'project.view_all':   {'admin'},          # see every user's projects
    # Users
    'user.list':          {'admin'},
    'user.create':        {'admin'},
    'user.edit':          {'admin'},
    'user.delete':        {'admin'},
    'user.view_self':     {'admin', 'user', 'viewer'},
    'user.edit_self':     {'admin', 'user', 'viewer'},
    # System
    'settings.manage':    {'admin'},
    'stats.view':         {'admin', 'user', 'viewer'},
}


def role_at_least(role: str, minimum: str) -> bool:
    try:
        return ROLES.index(role) >= ROLES.index(minimum)
    except ValueError:
        return False


def has_permission(permission: str, role: str = None) -> bool:
    if role is None:
        if not current_user.is_authenticated:
            return False
        role = current_user.role or 'viewer'
    allowed = PERMISSIONS.get(permission, set())
    return role in allowed


def login_required_api(f):
    """Require authentication; return JSON 401 for API clients."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            if _wants_json():
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            from flask import redirect, url_for
            return redirect(url_for('auth.login', next=request.path))
        if not current_user.is_active:
            if _wants_json():
                return jsonify({'error': 'Account is disabled', 'code': 'ACCOUNT_DISABLED'}), 403
            abort(403)
        return f(*args, **kwargs)
    return decorated


def permission_required(permission: str):
    """Require a specific permission (implies login)."""
    def decorator(f):
        @wraps(f)
        @login_required_api
        def decorated(*args, **kwargs):
            if not has_permission(permission):
                if _wants_json():
                    return jsonify({
                        'error': f'Permission denied: {permission}',
                        'code': 'FORBIDDEN',
                        'required': permission,
                        'your_role': current_user.role,
                    }), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def role_required(*roles):
    """Require one of the listed roles."""
    def decorator(f):
        @wraps(f)
        @login_required_api
        def decorated(*args, **kwargs):
            if current_user.role not in roles:
                if _wants_json():
                    return jsonify({
                        'error': 'Insufficient role',
                        'code': 'FORBIDDEN',
                        'required_roles': list(roles),
                        'your_role': current_user.role,
                    }), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    return role_required('admin')(f)


def _wants_json():
    if request.is_json or request.mimetype == 'application/json':
        return True
    if request.path.startswith('/api') or request.path.startswith('/projects'):
        return True
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json'


def can_access_project(project) -> bool:
    """Admin sees all; user/viewer see only their own."""
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    return project.user_id == current_user.id


def can_modify_project(project) -> bool:
    """Viewers cannot modify; owners and admins can."""
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'viewer':
        return False
    if current_user.role == 'admin':
        return True
    return project.user_id == current_user.id
