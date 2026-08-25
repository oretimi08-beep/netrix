from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('app.html')


@main_bp.route('/app')
@login_required
def app_page():
    return render_template('app.html')


@main_bp.route('/health')
def health():
    """Public health check for online platforms (Render/Vercel/uptime)."""
    from flask import jsonify
    try:
        from app import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    return jsonify({'status': 'ok' if db_ok else 'degraded', 'database': db_ok}), status


@main_bp.route('/setup-required')
def setup_required():
    """Shown when production DB is not configured."""
    from flask import current_app, render_template_string
    err = current_app.config.get('NETRIX_DB_ERROR') or 'DATABASE_URL is not set or unreachable'
    return render_template_string("""
    <!doctype html><html><head><title>NETRIX setup</title>
    <style>body{font-family:system-ui;max-width:640px;margin:40px auto;padding:0 16px}
    code{background:#f1f5f9;padding:2px 6px;border-radius:4px}</style></head><body>
    <h1>Database setup required</h1>
    <p>NETRIX is online, but needs a <strong>Postgres</strong> database on Vercel.</p>
    <ol>
      <li>Create a free DB at <a href="https://neon.tech">neon.tech</a> or Supabase</li>
      <li>In Vercel → Project → Settings → Environment Variables, set:</li>
    </ol>
    <ul>
      <li><code>DATABASE_URL</code> = your postgres connection string</li>
      <li><code>SECRET_KEY</code> = any long random string</li>
      <li><code>FLASK_ENV</code> = production</li>
    </ul>
    <p>Then <strong>Redeploy</strong> the project.</p>
    <pre style="background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto">{{ err }}</pre>
    </body></html>
    """, err=err), 503
