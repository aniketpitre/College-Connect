from fastapi import Request


def client_ip(request: Request) -> str:
    """The caller's address, for rate limits and the audit log.

    Vercel sets X-Real-IP itself, so a client can't fake it; X-Forwarded-For can carry whatever
    the client sent, so it is not trusted (it would let anyone dodge the per-IP limits). Off Vercel
    (local development) the socket address is used.
    """
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
