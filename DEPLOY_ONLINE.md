# Display NETRIX Online

## Fix Vercel 404 NOT_FOUND

That error means Vercel did not route traffic to the Flask app. This project is fixed with:

- `vercel.json` → rewrites all paths to `/api/index`
- `api/index.py` → Flask WSGI `app`

### Do this on Vercel

1. **Push the latest code** (with the fixed `vercel.json` and `api/index.py`) to GitHub.
2. In Vercel → Project → **Deployments** → **Redeploy** (clear cache if available).
3. **Environment Variables** (Settings → Environment Variables) — required:

| Name | Value |
|------|--------|
| `SECRET_KEY` | long random string |
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | **Postgres** URL (see below) |

4. Open your `*.vercel.app` URL again.

### Create free Postgres (required on Vercel)

SQLite **does not work** on Vercel.

1. Go to https://neon.tech → create project → copy connection string  
   Example: `postgresql://user:pass@host/neondb?sslmode=require`
2. Paste it as `DATABASE_URL` in Vercel.
3. Redeploy.

### Custom domain

Vercel → Settings → Domains → add domain → set Namecheap DNS as shown.

---

## Alternative: Render.com (often easier for Flask)

1. New Web Service from GitHub  
2. Build: `pip install -r requirements.txt`  
3. Start: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`  
4. Add Postgres + same env vars  

---

## Local

```bash
python run.py
```
→ http://127.0.0.1:5000
