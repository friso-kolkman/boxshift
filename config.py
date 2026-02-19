import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data', 'boxshift.db')}")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# GitHub OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
APP_URL = os.getenv("APP_URL", "http://localhost:8080")

# Allowed GitHub usernames (admin access)
ALLOWED_GITHUB_USERS = os.getenv("ALLOWED_GITHUB_USERS", "friso-kolkman").split(",")

# Allow demo login (set to "true" to enable /auth/demo without debug mode)
ALLOW_DEMO_LOGIN = os.getenv("ALLOW_DEMO_LOGIN", "false").lower() == "true"

# Resend (email)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "BoxShift <noreply@boxshift.nl>")
