#!/usr/bin/env python3
"""
Install NETRIX dependencies into the SAME Python interpreter that runs this file.

PyCharm:
  1. Right-click this file → Run 'setup_pycharm'
  2. Wait for success
  3. Right-click run.py → Run  (same interpreter)
     Do NOT run main.py (that is a sample file).
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(ROOT, 'requirements.txt')
MIN_PY = (3, 9)
CRITICAL_PACKAGES = (
    ('flask', 'Flask'),
    ('flask_sqlalchemy', 'Flask-SQLAlchemy'),
    ('flask_login', 'Flask-Login'),
    ('dotenv', 'python-dotenv'),
    ('reportlab', 'reportlab'),
)


def _print_header() -> None:
    print('=' * 60)
    print(' NETRIX setup')
    print(' Interpreter:', sys.executable)
    print(' Python:', sys.version.split()[0])
    print(' Project root:', ROOT)
    print('=' * 60)


def _check_python_version() -> int | None:
    if sys.version_info < MIN_PY:
        print(
            f'ERROR: Python {MIN_PY[0]}.{MIN_PY[1]}+ is required '
            f'(found {sys.version_info.major}.{sys.version_info.minor}).'
        )
        print('Install a newer Python from https://www.python.org/downloads/')
        return 1
    if sys.version_info >= (3, 14):
        print(
            f'WARNING: Python {sys.version_info.major}.{sys.version_info.minor} is very new; '
            'some packages may not have wheels yet. Prefer 3.11 or 3.12 if installs fail.'
        )
    return None


def _check_requirements_file() -> int | None:
    if not os.path.isfile(REQ):
        print('ERROR: requirements.txt not found.')
        print('Expected at:', REQ)
        print('Open the "netrix" folder as the PyCharm project root (the folder that contains run.py).')
        return 1
    try:
        with open(REQ, encoding='utf-8') as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        if not lines:
            print('ERROR: requirements.txt is empty.')
            return 1
    except OSError as e:
        print('ERROR: Cannot read requirements.txt:', e)
        return 1
    return None


def _run_pip(args: list[str], label: str, *, critical: bool = True) -> int:
    cmd = [sys.executable, '-m', 'pip'] + args
    print(f'\n>> {label}')
    print('   ', ' '.join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:
        print('ERROR: Could not run pip with this interpreter.')
        print('Interpreter:', sys.executable)
        print('Create a venv and select it in PyCharm:')
        print('  File → Settings → Project → Python Interpreter → Add → Virtualenv')
        return 127
    except subprocess.TimeoutExpired:
        print('ERROR: pip timed out after 10 minutes (network or mirror issue).')
        print('Check your internet connection and try again.')
        return 124
    except OSError as e:
        print('ERROR: Failed to start pip:', e)
        return 1

    if result.stdout:
        out = result.stdout.strip()
        if len(out) > 2500:
            out = '...\n' + out[-2500:]
        print(out)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or '').strip()
        if err:
            if len(err) > 2000:
                err = err[-2000:]
            print(err)
        if not critical:
            print(f'WARNING: optional step failed ({label}); continuing.')
            return 0
        print('\nERROR: pip failed (exit code {}).'.format(result.returncode))
        low = err.lower()
        if 'permission' in low or 'access is denied' in low:
            print('\nHint: Permission denied — use a project virtualenv (.venv) in PyCharm.')
        elif 'connection' in low or 'timed out' in low or 'network' in low:
            print('\nHint: Network problem — check internet / proxy / firewall, then retry.')
        elif 'ssl' in low or 'certificate' in low:
            print('\nHint: SSL/certificate issue — update pip/certifi or check corporate proxy.')
        elif 'psycopg' in low:
            print('\nHint: psycopg2 is only needed for Postgres (Vercel). Local SQLite does not need it.')
            print('Core requirements no longer include it. Re-run this setup script.')
        elif 'failed-wheel-build' in low or 'no matching distribution' in low:
            print('\nHint: No binary wheel for this Python version. Prefer Python 3.11 or 3.12.')
        return result.returncode
    return 0


def _ensure_pip() -> int:
    try:
        import pip  # noqa: F401
        return 0
    except ImportError:
        print('\n pip not found — trying ensurepip bootstrap...')
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'ensurepip', '--upgrade'],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                print('ERROR: ensurepip failed.')
                print((result.stderr or result.stdout or '')[-1500:])
                return result.returncode
        except Exception as e:
            print('ERROR: Could not bootstrap pip:', e)
            return 1
    return 0


def _verify_packages() -> int:
    print('\nVerifying critical packages...')
    failed = []
    for mod, name in CRITICAL_PACKAGES:
        try:
            m = __import__(mod)
            ver = getattr(m, '__version__', '')
            extra = f' ({ver})' if ver else ''
            print(f'  OK  {name}{extra}')
        except ImportError as e:
            print(f'  FAIL {name}: {e}')
            failed.append(name)
        except Exception as e:
            print(f'  FAIL {name}: unexpected error: {e}')
            failed.append(name)

    # Optional Postgres driver
    try:
        import psycopg2  # noqa: F401
        print('  OK  psycopg2 (Postgres driver, optional)')
    except ImportError:
        print('  --  psycopg2 not installed (OK for local SQLite; needed only for Postgres/Vercel)')

    if failed:
        print('\nERROR: Still missing:', ', '.join(failed))
        print('Try again, or run in a terminal:')
        print(f'  "{sys.executable}" -m pip install -r requirements.txt')
        return 1
    return 0


def main() -> int:
    try:
        _print_header()

        code = _check_python_version()
        if code:
            return code

        code = _check_requirements_file()
        if code:
            return code

        code = _ensure_pip()
        if code:
            return code

        code = _run_pip(['install', '--upgrade', 'pip'], 'Upgrade pip', critical=False)

        code = _run_pip(['install', '-r', REQ], 'Install requirements.txt (core)')
        if code:
            return code

        # Optional Postgres driver — never block local setup
        _run_pip(
            ['install', 'psycopg2-binary==2.9.9'],
            'Optional: psycopg2-binary (Postgres only)',
            critical=False,
        )

        code = _verify_packages()
        if code:
            return code

        print('\n' + '=' * 60)
        print(' Setup complete.')
        print(' Next: right-click run.py → Run (same interpreter)')
        print(' Do NOT run main.py (PyCharm sample).')
        print(' Browser: http://127.0.0.1:5000')
        print(' Register: /register   Login: /login')
        print('=' * 60)
        return 0

    except KeyboardInterrupt:
        print('\nCancelled by user.')
        return 130
    except Exception:
        print('\nUnexpected error during setup:')
        traceback.print_exc()
        print('\nIf this persists, recreate the venv in PyCharm:')
        print('  Settings → Python Interpreter → Add → Virtualenv (.venv)')
        print('  Then Run setup_pycharm.py again.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
