# NETRIX — Deploy to GitHub + Vercel (custom domain)

This guide deploys NETRIX as a Flask app on **Vercel**, with source on **GitHub**,
and a custom domain from **Namecheap** (or similar “cheap domain” registrars).

> **Important:** Vercel’s filesystem is ephemeral. **Do not use SQLite in production.**
> Use a managed **PostgreSQL** database (Neon, Supabase, Vercel Postgres, Railway, etc.).

---

## 1. Prepare the repository

1. Create a new GitHub repository (e.g. `netrix`).
2. Push this project (do **not** commit `.env` or `instance/*.db`):

```bash
cd netrix
git init
git add .
git commit -m "Initial NETRIX release"
git branch -M main
git remote add origin https://github.com/YOUR_USER/netrix.git
git push -u origin main
```

---

## 2. Create a Postgres database

Pick one:

| Provider | Notes |
|----------|--------|
| [Neon](https://neon.tech) | Free tier, serverless Postgres |
| [Supabase](https://supabase.com) | Free tier |
| [Vercel Postgres](https://vercel.com/storage/postgres) | Integrated with Vercel |

Copy the connection string, e.g.:

```text
postgresql://user:password@host/dbname?sslmode=require
```

If the provider gives `postgres://...`, NETRIX rewrites it to `postgresql://` automatically.

---

## 3. Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → Import your GitHub repo.
2. Framework preset: **Other** (Python via `api/index.py` + `vercel.json`).
3. **Environment variables** (Project → Settings → Environment Variables):

| Name | Value |
|------|--------|
| `SECRET_KEY` | Long random string |
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | Your Postgres URL |
| `MAIL_SERVER` | e.g. `smtp.gmail.com` |
| `MAIL_PORT` | `587` |
| `MAIL_USE_TLS` | `true` |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password / Gmail App Password |
| `MAIL_DEFAULT_SENDER` | From address |
| `BOOTSTRAP_ADMIN_EMAIL` | (optional) first admin email |
| `BOOTSTRAP_ADMIN_PASSWORD` | (optional) first admin password |

4. Deploy. Open the `*.vercel.app` URL and register a normal user at `/register`.

Optional bootstrap admin is only created when both `BOOTSTRAP_ADMIN_*` vars are set
and no matching user exists. **Demo accounts are not created.**

---

## 4. Custom domain (Namecheap / Cheapest Name / etc.)

1. In **Vercel** → Project → **Settings** → **Domains** → add your domain  
   (e.g. `netrix.example.com` or `www.example.com`).
2. Vercel shows the DNS records to create.
3. In **Namecheap** (Domain List → Manage → Advanced DNS):

| Type | Host | Value |
|------|------|--------|
| **A** | `@` | `76.76.21.21` (Vercel’s apex IP — confirm in Vercel UI) |
| **CNAME** | `www` | `cname.vercel-dns.com` |

Or follow the exact records Vercel displays (they may use CNAME for apex via ALIAS).

4. Wait for DNS propagation (often minutes, sometimes up to 48h).
5. Vercel issues HTTPS certificates automatically.

---

## 5. Email PDF reports

After SMTP vars are set:

1. Log in → create/generate a project.
2. Open **Download Centre**.
3. Use **Email PDF Report** with your email or a client address.
4. Or download the PDF directly.

**Gmail:** enable 2FA, create an [App Password](https://myaccount.google.com/apppasswords),  
use that as `MAIL_PASSWORD` (not your normal Gmail password).

---

## 6. Auth model

- **Register** (`/register`) — public self-registration → role `user`
- **Login** (`/login`) — email or username + password
- **No demo accounts** are seeded
- Optional **bootstrap admin** via environment variables (once)

---

## 7. Local development (still supported)

```bash
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 — use `/register` to create an account.

---

## 8. Troubleshooting

| Issue | Fix |
|-------|-----|
| App blank / 500 on Vercel | Check Vercel function logs; ensure `DATABASE_URL` is Postgres |
| Email fails | Verify SMTP vars; Gmail needs App Password |
| Tables missing | App runs `db.create_all()` on start; confirm DB connectivity |
| Domain not resolving | Check Namecheap DNS vs Vercel domain panel |

---

## Architecture notes

- Entry: `api/index.py` → Flask `create_app('production')`
- Routes: auth, main UI, `/projects/*`, `/api/*`
- Reports: ReportLab PDF, email via SMTP (`app/services/email_service.py`)
