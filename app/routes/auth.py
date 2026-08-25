from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.utils.rbac import login_required_api

auth_bp = Blueprint('auth', __name__)


def _wants_json():
    if request.is_json or request.mimetype == 'application/json':
        return True
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if _wants_json():
            return jsonify({'success': True, 'user': current_user.to_dict(), 'redirect': url_for('main.dashboard')})
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        as_json = _wants_json() or request.is_json
        if request.is_json or request.mimetype == 'application/json':
            data = request.get_json(silent=True) or {}
            email = (data.get('email') or data.get('username') or '').strip()
            password = data.get('password') or ''
            remember = bool(data.get('remember', False))
        else:
            email = (request.form.get('email') or '').strip()
            password = request.form.get('password') or ''
            remember = bool(request.form.get('remember'))

        if not email or not password:
            msg = 'Email/username and password are required.'
            if as_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return render_template('login.html')

        user = User.query.filter((User.email == email) | (User.username == email)).first()
        if user and user.is_active and user.check_password(password):
            login_user(user, remember=remember)
            try:
                user.last_login = datetime.utcnow()
                db.session.commit()
            except Exception:
                db.session.rollback()
            if as_json:
                return jsonify({'success': True, 'user': user.to_dict(), 'redirect': url_for('main.dashboard')})
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))

        msg = 'Invalid credentials or inactive account.'
        if as_json:
            return jsonify({'success': False, 'message': msg}), 401
        flash(msg, 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Public self-registration creates a standard 'user' role account."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Admin can disable registration via site settings
    try:
        from app.models import SiteSetting
        allow = str(SiteSetting.get('allow_registration', 'true')).lower() in ('1', 'true', 'yes')
    except Exception:
        allow = True
    if not allow and request.method == 'GET':
        flash('Registration is currently disabled by the administrator.', 'warning')
        return redirect(url_for('auth.login'))
    if not allow and request.method == 'POST':
        msg = 'Registration is currently disabled by the administrator.'
        if _wants_json() or request.is_json:
            return jsonify({'success': False, 'message': msg}), 403
        flash(msg, 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        as_json = _wants_json() or request.is_json
        if request.is_json or request.mimetype == 'application/json':
            data = request.get_json(silent=True) or {}
        else:
            data = request.form

        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        full_name = (data.get('full_name') or '').strip()

        if not username or not email or not password:
            msg = 'Username, email and password are required.'
            if as_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return render_template('register.html')

        if len(password) < 6:
            msg = 'Password must be at least 6 characters.'
            if as_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'warning')
            return render_template('register.html')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            msg = 'Username or email already registered.'
            if as_json:
                return jsonify({'success': False, 'message': msg}), 409
            flash(msg, 'warning')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            full_name=full_name or username,
            role='user',  # self-registration is always standard user
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if as_json:
            return jsonify({'success': True, 'message': 'Registration successful. Please log in.'})
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
