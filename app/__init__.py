from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from config import config
import os
import sys

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to continue.'
login_manager.login_message_category = 'warning'


def ensure_generated_columns(app):
    """Add ipv6_json / design_json columns if missing (SQLite only)."""
    uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').lower()
    if not uri.startswith('sqlite'):
        return
    try:
        from sqlalchemy import text
        rows = db.session.execute(text('PRAGMA table_info(generated_data)')).fetchall()
        cols = {r[1] for r in rows}
        if 'ipv6_json' not in cols:
            db.session.execute(
                text("ALTER TABLE generated_data ADD COLUMN ipv6_json TEXT DEFAULT '[]'")
            )
        if 'design_json' not in cols:
            db.session.execute(
                text("ALTER TABLE generated_data ADD COLUMN design_json TEXT DEFAULT '{}'")
            )
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            app.logger.warning('ensure_generated_columns: %s', e)
        except Exception:
            print('[NETRIX] ensure_generated_columns:', e)


def ensure_devices_json_column(app):
    """Add projects.devices_json if missing (SQLite only)."""
    uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').lower()
    if not uri.startswith('sqlite'):
        return
    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns('projects')]
        if 'devices_json' not in cols:
            db.session.execute(
                text("ALTER TABLE projects ADD COLUMN devices_json TEXT DEFAULT '{}'")
            )
            db.session.commit()
            print('[NETRIX] Migrated: added projects.devices_json')
    except Exception as mig_err:
        print(f'[NETRIX] Migration note: {mig_err}')


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    # Vercel / production often sets VERCEL=1 or FLASK_ENV=production
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
        config_name = 'production'

    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )
    app.config.from_object(config.get(config_name, config['default']))

    # Mail settings from environment
    app.config.setdefault('MAIL_SERVER', os.environ.get('MAIL_SERVER', ''))
    app.config.setdefault('MAIL_PORT', int(os.environ.get('MAIL_PORT', 587)))
    app.config.setdefault('MAIL_USE_TLS', os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes'))
    app.config.setdefault('MAIL_USE_SSL', os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes'))
    app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
    app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
    app.config.setdefault(
        'MAIL_DEFAULT_SENDER',
        os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME', ''),
    )

    # Ensure folders exist (may fail on read-only serverless — ignore)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        upload = app.config.get('UPLOAD_FOLDER') or os.path.join(app.instance_path, 'uploads')
        os.makedirs(str(upload), exist_ok=True)
    except Exception:
        pass

    db.init_app(app)
    login_manager.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': '*'}})

    from app.models import User, Project, Department, GeneratedData, SiteSetting  # noqa: F401
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    from app.routes.projects import projects_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    try:
        with app.app_context():
            _init_database(app)
    except Exception as init_err:
        # On Vercel, missing DATABASE_URL must not prevent the WSGI app from loading
        print(f'[NETRIX] Database init deferred/failed: {init_err}', file=sys.stderr)
        app.config['NETRIX_DB_ERROR'] = str(init_err)

    # Trust X-Forwarded-* headers when behind Vercel / Render / nginx
    if os.environ.get('VERCEL') or os.environ.get('RENDER') or config_name == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


def _init_database(app):
    """Create tables and verify connectivity. Demo accounts are NOT seeded."""
    from sqlalchemy import text

    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f'[NETRIX] Database URI: {uri[:60]}...' if len(uri) > 60 else f'[NETRIX] Database URI: {uri}')

    try:
        db.session.execute(text('SELECT 1'))
        db.session.commit()
    except Exception as exc:
        print(f'[NETRIX] ERROR: cannot connect to database:\n  {exc}', file=sys.stderr)
        print('[NETRIX] Tips:', file=sys.stderr)
        print('  - For local: delete instance/netrix.db and restart', file=sys.stderr)
        print('  - For production: set DATABASE_URL to a Postgres URL (Neon/Supabase/Vercel)', file=sys.stderr)
        # On serverless first cold start, tables may not exist yet — still try create_all
        pass

    try:
        db.create_all()
    except Exception as e:
        print(f'[NETRIX] create_all note: {e}')

    ensure_generated_columns(app)
    ensure_devices_json_column(app)

    # Default admin account (always ensure exists for monitoring console)
    # Override with BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD if set.
    from app.models import User, SiteSetting
    try:
        SiteSetting.ensure_defaults()
    except Exception as e:
        print(f'[NETRIX] SiteSetting defaults note: {e}')

    admin_email = (os.environ.get('BOOTSTRAP_ADMIN_EMAIL') or 'admin@netrix.local').strip().lower()
    admin_password = (os.environ.get('BOOTSTRAP_ADMIN_PASSWORD') or 'Admin@Netrix2026').strip()
    admin_user = User.query.filter(
        (User.username == 'admin') | (User.email == admin_email)
    ).first()
    if not admin_user:
        u = User(
            username='admin',
            email=admin_email,
            full_name='System Administrator',
            role='admin',
            is_active=True,
        )
        u.set_password(admin_password)
        db.session.add(u)
        try:
            db.session.commit()
            print(f'[NETRIX] Admin account ready: {admin_email} / (password from env or default)')
        except Exception as e:
            db.session.rollback()
            print(f'[NETRIX] Admin seed failed: {e}')
    else:
        # Ensure role stays admin for the primary admin username
        changed = False
        if admin_user.username == 'admin' and admin_user.role != 'admin':
            admin_user.role = 'admin'
            admin_user.is_active = True
            changed = True
        # Optional password reset: set BOOTSTRAP_ADMIN_RESET=1 to apply BOOTSTRAP_ADMIN_PASSWORD
        if os.environ.get('BOOTSTRAP_ADMIN_RESET', '').lower() in ('1', 'true', 'yes'):
            admin_user.set_password(admin_password)
            admin_user.role = 'admin'
            admin_user.is_active = True
            changed = True
            print('[NETRIX] Admin password reset via BOOTSTRAP_ADMIN_RESET')
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None
