from fastapi import Request


def client_ip(request: Request) -> str:
    """Vercel puts the real client address first in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")[:300]


def base_url(request: Request) -> str:
    from app.core.config import settings

    if settings.app_base_url:
        return settings.app_base_url
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"
