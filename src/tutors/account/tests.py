from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

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


class AccountRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("register")

    @patch("tutors.account.serializers.send_message.delay")
    def test_register_and_verify_email_success(self, mock_send_delay):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_active)
        self.assertTrue(hasattr(user, "email_token"))
        mock_send_delay.assert_called_once_with(user.id, str(user.email_token.token))

        verify_url = reverse("verify_email", kwargs={"token": user.email_token.token})
        verify_response = self.client.get(verify_url)
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(EmailToken.objects.filter(user=user).exists())

    def test_register_password_mismatch(self):
        payload = {
            "username": "user2",
            "email": "user2@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_verify_expired_token(self):
        user = User.objects.create_user(
            username="expireduser",
            email="expired@example.com",
            password="StrongPassword123!",
            is_active=False,
        )
        token = EmailToken.objects.create(user=user)
        token.created_at = timezone.now() - timedelta(hours=13)
        token.save(update_fields=["created_at"])

        verify_url = reverse("verify_email", kwargs={"token": token.token})
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
