# BoxShift

**Van Box 3 naar Box 2 — Beleggings-BV management platform.**

BoxShift helps Dutch investors manage their transition from Box 3 (personal assets) to Box 2 (beleggings-BV). Track leads, users, holdings, transactions, annual reports, and VPB filings in one place.

---

## Features

- **Lead Management** — Track potential clients interested in BV setup
- **BV Administration** — Manage beleggings-BV entities per user
- **Holdings Tracker** — Track investment portfolios within each BV
- **Transaction Log** — Record all BV transactions
- **Annual Reports** — Generate and manage yearly BV reports
- **VPB Filing** — Corporate tax (vennootschapsbelasting) filing management
- **AI Assistance** — Claude-powered features via Anthropic API
- **GitHub OAuth** — Secure login with username allowlist
- **Email Notifications** — Via Resend API

---

## Quick Start

### Local Development

```bash
git clone git@github.com:friso-kolkman/boxshift.git
cd boxshift
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your keys
python app.py           # runs on http://localhost:8080
```

### Docker

```bash
cp .env.example .env
docker compose up -d    # runs on http://localhost:8080
```

### Demo Data

```bash
python seed_demo.py     # populates DB with sample data
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session key |
| `DATABASE_URL` | No | SQLite by default, PostgreSQL supported |
| `ANTHROPIC_API_KEY` | For AI features | Claude API key |
| `GITHUB_CLIENT_ID` | For auth | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | For auth | GitHub OAuth app secret |
| `APP_URL` | Yes | Application base URL |
| `ALLOWED_GITHUB_USERS` | Yes | Comma-separated GitHub usernames |
| `RESEND_API_KEY` | For email | Resend API key |
| `EMAIL_FROM` | For email | Sender email address |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | SQLAlchemy |
| Frontend | Jinja2 templates |
| Auth | GitHub OAuth |
| Email | Resend |
| AI | Anthropic Claude |
| Deployment | Docker + Caddy |

---

## Deployment

Deployed at [boxshift.nl](https://boxshift.nl) via Docker + Caddy HTTPS on Hetzner.

---

## License

MIT

---

Built by [Friso Kolkman](https://linkedin.com/in/frisokolkman) & Pieter Louwerse
