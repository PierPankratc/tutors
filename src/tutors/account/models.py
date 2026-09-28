from datetime import datetime, timezone
import uuid

from django.db import models
from django.conf import settings

class EmailToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_token')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (datetime.now()-self.created_at)> 12*60
    