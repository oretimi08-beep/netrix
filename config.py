"""
NETRIX configuration — SQLite (local) / Postgres (production / Vercel).
"""
import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv

basedir = Path(__file__).resolve().parent
load_dotenv(basedir / '.env')

_instance = basedir / 'instance'


def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / '.write_test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return True
    except Exception as exc:
        print(f'[NETRIX] Cannot write to {path}: {exc}', file=sys.stderr)
        return False


def _sqlite_uri(db_path: Path) -> str:
    absolute = db_path.resolve()
    posix = absolute.as_posix()
    if absolute.drive:
        return f'sqlite:///{posix}'
    return f'sqlite:///{posix}'


def _normalize_database_url(url: str) -> str:
    """Vercel/Heroku style postgres:// → SQLAlchemy postgresql://"""
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url


def resolve_database_uri():
    """
    Priority:
      1. DATABASE_URL (Postgres recommended on Vercel; also MySQL/SQLite)
      2. instance/netrix.db (local writable)
      3. System temp directory fallback
    """
    env_url = (os.environ.get('DATABASE_URL') or '').strip()
    if env_url:
        env_url = _normalize_database_url(env_url)
        if env_url.startswith('sqlite:///') and not env_url.startswith('sqlite:////'):
            rest = env_url[len('sqlite:///'):]
            if not rest.startswith('/') and not (len(rest) > 1 and rest[1] == ':'):
                abs_path = (basedir / rest).resolve()
                fixed = _sqlite_uri(abs_path)
                print(f'[NETRIX] Expanded relative DATABASE_URL → {fixed}')
                return fixed
        return env_url

    if _ensure_dir(_instance):
        return _sqlite_uri(_instance / 'netrix.db')

    tmp_dir = Path(tempfile.gettempdir())
    _ensure_dir(tmp_dir)
    db_path = tmp_dir / 'netrix.db'
    print(f'[NETRIX] Using temp database: {db_path}', file=sys.stderr)
    return _sqlite_uri(db_path)


def sqlite_connect_args(uri: str) -> dict:
    if not uri.startswith('sqlite'):
        return {}
    return {
        'timeout': 30,
        'check_same_thread': False,
    }


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-netrix-2024'
    SQLALCHEMY_DATABASE_URI = resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'connect_args': sqlite_connect_args(SQLALCHEMY_DATABASE_URI),
    }
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = 3600 * 24
    UPLOAD_FOLDER = str(_instance / 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True

    # SMTP / report email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME', '')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    # Prefer SECRET_KEY from env in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or Config.SECRET_KEY


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
