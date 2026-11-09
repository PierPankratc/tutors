from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

User = get_user_model()


@shared_task(bind=True)
def send_message(self, id, token):
    try:
        user = User.objects.get(id=id)
        url = f"http://localhost:8000/api/accounts/verify-email/{token}/"
        subject = "Подтверждение регистрации"
        message = (
            f"Здравствуйте, {user.username}!\n\n"
            f"Пожалуйста, перейдите по ссылке для активации аккаунта:\n{url}"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        return f"Email sent to user {id}"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc
