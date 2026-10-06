"""
Application settings, read from environment variables.

Locally they come from backend/.env (gitignored); on Vercel from Project Settings ->
Environment Variables. Values that tests or operators may change at runtime (such as
ADMIN_TOKEN) are read where they are used, not cached here.
"""

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

try:  # local dev only; python-dotenv never overrides variables that are already set
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    mongodb_uri: str | None
    mongodb_db: str
    allowed_origins: tuple[str, ...]
    # Secure cookies need HTTPS; browsers treat http://localhost as secure, so this stays on in dev too.
    cookie_secure: bool
    # Encrypts stored 2-step (TOTP) secrets. Required in production; any long random string.
    app_secret_key: str | None
    # Public base URL used in emailed links; when unset it is taken from the request.
    app_base_url: str | None
    email_api_key: str | None
    email_from: str
    # Vercel Cron sends "Authorization: Bearer <CRON_SECRET>"; scheduled jobs refuse calls without it.
    cron_secret: str | None
    # Sign-ins allowed per IP address in 15 minutes. A college lab or campus Wi-Fi puts many
    # students behind one address; wrong passwords are limited per account as well (lockout).
    login_limit_per_ip: int
    # Lets a local Vite dev server (http://localhost:*) call the API with cookies. Off on Vercel,
    # so a page on someone's own machine can't make signed-in requests to production.
    allow_localhost_origins: bool
    # Online fee payment (Razorpay). Without the key pair the "Pay online" button is hidden.
    razorpay_key_id: str | None
    razorpay_key_secret: str | None
    razorpay_webhook_secret: str | None
    # SMS through MSG91 (India: each message needs a DLT-approved template, SMS_TEMPLATE_<NAME>).
    sms_api_key: str | None
    # WhatsApp through the Meta Cloud API (approved templates, WHATSAPP_TEMPLATE_<NAME>).
    whatsapp_token: str | None
    whatsapp_phone_id: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name="CollegeConnect",
            mongodb_uri=os.getenv("MONGODB_URI") or None,
            mongodb_db=os.getenv("MONGODB_DB", "collegeconnect"),
            allowed_origins=tuple(o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()),
            cookie_secure=_flag("COOKIE_SECURE", True),
            app_secret_key=os.getenv("APP_SECRET_KEY") or None,
            app_base_url=(os.getenv("APP_BASE_URL") or "").rstrip("/") or None,
            email_api_key=os.getenv("EMAIL_API_KEY") or None,
            email_from=os.getenv("EMAIL_FROM", "CollegeConnect <onboarding@resend.dev>"),
            cron_secret=os.getenv("CRON_SECRET") or None,
            login_limit_per_ip=int(os.getenv("LOGIN_LIMIT_PER_IP") or 300),
            allow_localhost_origins=_flag("ALLOW_LOCALHOST_ORIGINS", not os.getenv("VERCEL")),
            razorpay_key_id=os.getenv("RAZORPAY_KEY_ID") or None,
            razorpay_key_secret=os.getenv("RAZORPAY_KEY_SECRET") or None,
            razorpay_webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET") or None,
            sms_api_key=os.getenv("SMS_API_KEY") or None,
            whatsapp_token=os.getenv("WHATSAPP_TOKEN") or None,
            whatsapp_phone_id=os.getenv("WHATSAPP_PHONE_ID") or None,
        )


settings = Settings.from_env()
