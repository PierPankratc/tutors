from datetime import timedelta
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_token",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self) -> bool:
        return (timezone.now() - self.created_at) < timedelta(hours=12)
