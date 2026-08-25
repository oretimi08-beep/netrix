#!/usr/bin/env python3
"""
NETRIX – Enterprise Network Planning Framework
Run: python run.py
"""
import os
import sys

# Make sure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app, db
    from app.models import User, Project, Department, GeneratedData
except ModuleNotFoundError as e:
    print('=' * 60)
    print(' Missing Python package:', e)
    print(' Interpreter in use:', sys.executable)
    print()
    print(' FIX (PyCharm):')
    print('   1. Right-click setup_pycharm.py → Run')
    print('   2. Then right-click run.py → Run')
    print('   (Both must use the same interpreter / .venv)')
    print()
    print(' FIX (Terminal):')
    print('   python -m pip install -r requirements.txt')
    print('   OR double-click install_deps.bat')
    print('=' * 60)
    raise SystemExit(1) from e

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Project': Project,
        'Department': Department,
        'GeneratedData': GeneratedData,
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    # Mask password in URI for display
    display_uri = uri
    if '@' in uri:
        # mysql+pymysql://user:pass@host/db → mysql+pymysql://user:***@host/db
        try:
            pre, post = uri.split('@', 1)
            scheme_user = pre.rsplit(':', 1)[0]
            display_uri = f'{scheme_user}:***@{post}'
        except Exception:
            pass
    print(f'''
    ╔══════════════════════════════════════════════╗
    ║   NETRIX Enterprise Network Planning         ║
    ║   http://127.0.0.1:{port:<5}                       ║
    ╠══════════════════════════════════════════════╣
    ║   Register: /register   Login: /login        ║
    ╠══════════════════════════════════════════════╣
    ║   DB: {display_uri[:40]:<40} ║
    ╚══════════════════════════════════════════════╝
    ''')
    app.run(host='0.0.0.0', port=port, debug=debug)
