#!/usr/bin/env python3
"""
NETRIX database connection checker.
Run:  python check_db.py
"""
import sys
import os
from pathlib import Path

# Ensure app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    print('=' * 50)
    print('NETRIX Database Diagnostics')
    print('=' * 50)

    from config import Config, basedir, _instance, resolve_database_uri

    uri = resolve_database_uri()
    print(f'Basedir:   {basedir}')
    print(f'Instance:  {_instance}  exists={_instance.exists()}')
    print(f'Resolved URI:\n  {uri}')
    print()

    if uri.startswith('sqlite'):
        # Extract path
        path_part = uri.replace('sqlite:///', '', 1)
        db_path = Path(path_part)
        print(f'SQLite file: {db_path}')
        print(f'  exists:    {db_path.exists()}')
        if db_path.exists():
            print(f'  size:      {db_path.stat().st_size} bytes')
        print(f'  parent writable: {os.access(db_path.parent, os.W_OK)}')
        print()

        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path), timeout=10)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            print(f'Tables: {tables or "(none)"}')
            if 'users' in tables:
                cur.execute('SELECT id, username, role, is_active FROM users')
                for row in cur.fetchall():
                    print(f'  user id={row[0]} username={row[1]} role={row[2]} active={row[3]}')
            conn.close()
            print('\nRaw SQLite: OK')
        except Exception as e:
            print(f'\nRaw SQLite FAILED: {e}')
            return 1

    print()
    try:
        from app import create_app, db
        from app.models import User, Project
        from sqlalchemy import text
        app = create_app('development')
        with app.app_context():
            db.session.execute(text('SELECT 1'))
            print(f'SQLAlchemy: OK')
            print(f'  Users:    {User.query.count()}')
            print(f'  Projects: {Project.query.count()}')
        print()
        print('All checks passed.')
        return 0
    except Exception as e:
        print(f'SQLAlchemy FAILED: {type(e).__name__}: {e}')
        print()
        print('Troubleshooting:')
        print('  1. Delete the DB file and restart:  rm instance/netrix.db && python run.py')
        print('  2. Or set an absolute path in .env:')
        print('       DATABASE_URL=sqlite:////full/path/to/netrix.db')
        print('  3. Ensure the folder is writable by your user.')
        return 1

if __name__ == '__main__':
    sys.exit(main())
