import ipaddress

from fastapi import Request


def client_ip(request: Request) -> str:
    """Реальный IP клиента за нашим Nginx (X-Real-IP), с валидацией формата.

    Приложение доступно только внутри docker-сети, поэтому заголовок доверенный;
    любое невалидное значение отбрасывается, чтобы не писать мусор в audit_log.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    candidate = (
        request.headers.get("X-Real-IP")
        or forwarded.split(",")[0].strip()
        or (request.client.host if request.client else "")
    )
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "0.0.0.0"  # noqa: S104 - это плейсхолдер, не bind-адрес
