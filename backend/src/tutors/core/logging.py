import logging
import re

# Маскируем значения секретов и ПДн: сами значения никогда не должны попадать в логи
_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|password_hash|token|access_token|refresh_token|secret|"
    r"authorization|x-csrf-token)\b\s*[=:]\s*([^\s,;\"']+)"
)
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class SensitiveDataFilter(logging.Filter):
    """Редакция секретов и ПДн в сообщениях логов (требование безопасности №1)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - некорректный формат не должен ломать приложение
            return True
        redacted = _SECRET_PATTERN.sub(r"\1=***", message)
        redacted = _EMAIL_PATTERN.sub("***@***", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
