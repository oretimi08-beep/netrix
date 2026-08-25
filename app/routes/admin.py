"""Admin-only routes: monitoring, users, projects, site settings."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user
from app import db
from app.models import User, Project, Department, GeneratedData, SiteSetting
from app.utils.rbac import admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/overview', methods=['GET'])
@admin_required
def overview():
    """System monitoring snapshot for the admin dashboard."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    users = User.query.all()
    projects = Project.query.order_by(Project.created_at.desc()).all()

    by_role = {'admin': 0, 'user': 0, 'viewer': 0}
    active_users = 0
    recent_logins = 0
    for u in users:
        by_role[u.role] = by_role.get(u.role, 0) + 1
        if u.is_active:
            active_users += 1
        if u.last_login and u.last_login >= week_ago:
            recent_logins += 1

    by_status = {}
    completed = 0
    generated = 0
    for p in projects:
        st = p.status or 'Draft'
        by_status[st] = by_status.get(st, 0) + 1
        if st == 'Completed':
            completed += 1
        if p.generated:
            generated += 1

    recent_users = sorted(
        users,
        key=lambda x: x.created_at or datetime.min,
        reverse=True,
    )[:8]
    recent_projects = projects[:10]

    settings = SiteSetting.all_as_dict()

    return jsonify({
        'generated_at': now.isoformat() + 'Z',
        'users': {
            'total': len(users),
            'active': active_users,
            'by_role': by_role,
            'recent_logins_7d': recent_logins,
        },
        'projects': {
            'total': len(projects),
            'completed': completed,
            'with_generated_data': generated,
            'by_status': by_status,
        },
        'departments_total': Department.query.count(),
        'recent_users': [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'last_login': u.last_login.isoformat() if u.last_login else None,
                'is_active': u.is_active,
            }
            for u in recent_users
        ],
        'recent_projects': [
            {
                'id': p.id,
                'project_name': p.project_name,
                'company_name': p.company_name,
                'status': p.status,
                'owner': p.owner.username if p.owner else None,
                'owner_id': p.user_id,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'base_network': p.base_network,
            }
            for p in recent_projects
        ],
        'settings': {
            'site_name': settings.get('site_name'),
            'maintenance_mode': settings.get('maintenance_mode'),
            'allow_registration': settings.get('allow_registration'),
            'announcement': settings.get('announcement'),
        },
        'health': {
            'database': 'ok',
            'app': 'ok',
        },
    })


@admin_bp.route('/projects', methods=['GET'])
@admin_required
def list_all_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    out = []
    for p in projects:
        d = p.to_dict(include_generated=False)
        d['owner_username'] = p.owner.username if p.owner else None
        d['owner_email'] = p.owner.email if p.owner else None
        d['has_generated'] = bool(p.generated)
        out.append(d)
    return jsonify(out)


@admin_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@admin_required
def admin_delete_project(project_id):
    p = Project.query.get(project_id)
    if not p:
        return jsonify({'error': 'Project not found'}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    SiteSetting.ensure_defaults()
    return jsonify(SiteSetting.all_as_dict())


@admin_bp.route('/settings', methods=['PUT'])
@admin_required
def update_settings():
    """Update frontend-facing site settings (announcement, welcome text, etc.)."""
    data = request.get_json() or {}
    allowed = set(SiteSetting.DEFAULTS.keys())
    updated = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        SiteSetting.set(key, value)
        updated[key] = str(value) if value is not None else ''
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'success': True, 'updated': updated, 'settings': SiteSetting.all_as_dict()})


@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'error': 'User not found'}), 404
    data = u.to_dict()
    data['project_count'] = u.projects.count()
    return jsonify(data)


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    full_name = (data.get('full_name') or '').strip()
    role = (data.get('role') or 'user').strip().lower()

    if not username or not email or not password:
        return jsonify({'error': 'username, email and password are required'}), 400
    if role not in User.VALID_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'error': 'Username or email already exists'}), 409

    u = User(
        username=username,
        email=email,
        full_name=full_name or username,
        role=role,
        is_active=bool(data.get('is_active', True)),
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}

    if u.id == current_user.id and data.get('role') and data.get('role') != 'admin':
        return jsonify({'error': 'Cannot demote your own admin account'}), 400
    if u.id == current_user.id and data.get('is_active') is False:
        return jsonify({'error': 'Cannot deactivate your own account'}), 400

    if 'full_name' in data:
        u.full_name = (data['full_name'] or '').strip()
    if 'email' in data:
        email = data['email'].strip().lower()
        existing = User.query.filter(User.email == email, User.id != u.id).first()
        if existing:
            return jsonify({'error': 'Email already in use'}), 409
        u.email = email
    if 'username' in data:
        username = data['username'].strip()
        existing = User.query.filter(User.username == username, User.id != u.id).first()
        if existing:
            return jsonify({'error': 'Username already in use'}), 409
        u.username = username
    if 'role' in data:
        role = data['role'].strip().lower()
        if role not in User.VALID_ROLES:
            return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400
        u.role = role
    if 'is_active' in data:
        u.is_active = bool(data['is_active'])
    if data.get('password'):
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        u.set_password(data['password'])

    db.session.commit()
    return jsonify(u.to_dict())


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'error': 'User not found'}), 404
    if u.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/roles', methods=['GET'])
@admin_required
def list_roles():
    from app.utils.rbac import ROLES, ROLE_LABELS, PERMISSIONS
    roles_info = []
    for r in ROLES:
        roles_info.append({
            'id': r,
            'label': ROLE_LABELS.get(r, r),
            'permissions': sorted(p for p, allowed in PERMISSIONS.items() if r in allowed),
        })
    return jsonify(roles_info)
