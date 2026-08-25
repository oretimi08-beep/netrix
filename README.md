# NETRIX — Enterprise Network Planning Framework

Web application for VLSM/IPv4/IPv6 planning, VLAN design, Cisco config generation,
topology/UML diagrams, PDF/Word/Excel reports, Packet Tracer lab guides, and live SSH push.

## Features

- Secure **registration** and **login** (no demo accounts)
- Project management with multi-router / multi-switch / WAN design
- Automated VLSM, VLAN, IPv4 & IPv6 ULA planning
- Cisco IOS router/switch configuration generation
- Professional PDF reports (executive summary, metrics, diagrams)
- **Download** reports or **email PDF** to yourself or a client
- Role-based access control
- REST API endpoints

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 → **Register** a new account → **Login**.

## Production (GitHub + Vercel + custom domain)

See **[DEPLOY_ONLINE.md](DEPLOY_ONLINE.md)** (quick online) and **[DEPLOYMENT.md](DEPLOYMENT.md)** for:

- Pushing to GitHub
- Postgres on Neon/Supabase/Vercel
- Vercel env vars (including SMTP for email reports)
- Pointing a Namecheap domain at Vercel

## Environment

Copy `.env.example` to `.env` and set `SECRET_KEY`, `DATABASE_URL`, and `MAIL_*` as needed.
