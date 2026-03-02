# BoxShift

**Van Box 3 naar Box 2 — Beleggings-BV Management Platform**

BoxShift helps Dutch investors set up and manage a beleggings-BV (investment holding company) to move from Box 3 to Box 2 taxation. It tracks leads, users, BVs, holdings, transactions, annual reports, and VPB (corporate tax) filings.

---

## Features

- **Lead Management** — Track and convert interested investors
- **User Onboarding** — Guided setup: situation assessment, broker, vermogen estimate
- **BV Administration** — Create and manage beleggings-BVs (KvK number, oprichtingsdatum)
- **Holdings Tracker** — Portfolio positions per BV (ticker, quantity, cost basis, current value)
- **Transaction Log** — Buy, sell, dividend, interest, costs, deposits, withdrawals
- **Annual Reports** — AI-generated annual reports per BV per year
- **VPB Filings** — Corporate tax filing management with AI assistance
- **Dashboard** — Overview of all BVs, holdings value, and key metrics
- **GitHub OAuth** — Secure login via GitHub account

## Architecture

```
Flask App (app.py)
├── Models (models.py)     — Lead, User, BV, Transaction, Holding, AnnualReport, VPBFiling
├── Config (config.py)     — Environment-based configuration
├── Templates (Jinja2)     — Dashboard, onboarding, transactions, reports, VPB
└── Auth                   — GitHub OAuth with allowlist

Database: SQLite (data/boxshift.db)
AI: Anthropic Claude for report generation
Email: Resend for notifications
```

## Quick Start

### Prerequisites

- Python 3.10+
- GitHub OAuth app (for login)

### Local Development

```bash
git clone git@github.com:friso-kolkman/boxshift.git
cd boxshift
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your keys
python app.py          # Runs on http://localhost:8080
```

### Docker (Production)

```bash
cp .env.example .env   # Edit with production values
docker-compose up -d   # Runs behind Caddy at boxshift.nl
```

### Seed Demo Data

```bash
python seed_demo.py  # Creates sample BV with holdings and transactions
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | AI report generation |
| `SECRET_KEY` | Yes | Flask session key |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///data/boxshift.db`) |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth app secret |
| `APP_URL` | Yes | Base URL (e.g., `https://boxshift.nl`) |
| `ALLOWED_GITHUB_USERS` | Yes | Comma-separated GitHub usernames allowed to log in |
| `RESEND_API_KEY` | No | Email notifications via Resend |
| `EMAIL_FROM` | No | Sender address for emails |

## Data Model

```
Lead (email, status)
User (email, name, github_id, vermogen_estimate, broker, situation)
  └── BV (name, kvk_number, oprichtingsdatum, status)
        ├── Transaction (date, type, ticker, quantity, price, amount)
        ├── Holding (ticker, name, quantity, avg_cost, current_price)
        ├── AnnualReport (year, content, status)
        └── VPBFiling (year, belastbaar_bedrag, vpb_bedrag, status)
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Flask (Python 3.10+) |
| Database | SQLite |
| Frontend | Jinja2 templates |
| AI | Anthropic Claude |
| Auth | GitHub OAuth |
| Email | Resend |
| Deployment | Docker + Caddy |

## Deployment

Live at [boxshift.nl](https://boxshift.nl) on Hetzner, served via Caddy HTTPS.

## License

Private
