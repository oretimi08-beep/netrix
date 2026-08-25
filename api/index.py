"""
Vercel serverless entry for NETRIX.

All HTTP traffic is rewritten to this function (see vercel.json).
"""
from __future__ import annotations

import os
import sys
import traceback

# Project root must be on sys.path so `import app` works
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault('FLASK_ENV', 'production')
# Vercel sets VERCEL=1 automatically

try:
    from app import create_app

    app = create_app('production')
except Exception:  # noqa: BLE001 — surface startup errors in the browser
    _STARTUP_TRACEBACK = traceback.format_exc()
    from flask import Flask

    app = Flask(__name__)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def startup_error(path: str = ''):
        tb = _STARTUP_TRACEBACK
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>NETRIX startup error</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#111}}
 pre{{background:#0f172a;color:#e2e8f0;padding:16px;border-radius:8px;overflow:auto;font-size:12px}}
 .box{{background:#fef2f2;border:1px solid #fecaca;padding:16px;border-radius:8px}}
 code{{background:#f1f5f9;padding:2px 6px;border-radius:4px}}
</style></head><body>
 <h1>NETRIX failed to start on Vercel</h1>
 <div class="box">
  <p>The Flask app could not boot. Common fixes:</p>
  <ol>
   <li>Set <code>DATABASE_URL</code> to a <strong>Postgres</strong> URL (Neon/Supabase) — SQLite does not work on Vercel.</li>
   <li>Set <code>SECRET_KEY</code> in Vercel → Project → Settings → Environment Variables.</li>
   <li>Redeploy after saving env vars.</li>
  </ol>
 </div>
 <h3>Traceback</h3>
 <pre>{tb}</pre>
</body></html>"""
        return html, 500


# Vercel Python looks for `app` (WSGI)
application = app
