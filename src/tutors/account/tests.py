from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tutors.account.models import EmailToken

User = get_user_model()


class EmailTokenTests(TestCase):
    def test_email_token_validity(self):
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        token = EmailToken.objects.create(user=user)
        self.assertTrue(token.is_valid())

        token.created_at = timezone.now() - timedelta(hours=13)
        token.save(update_fields=["created_at"])
        self.assertFalse(token.is_valid())
