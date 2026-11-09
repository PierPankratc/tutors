from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tutors.account.models import EmailToken
from tutors.account.serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "message": (
                    "Регистрация прошла успешно. "
                    "Проверьте почту для подтверждения аккаунта."
                ),
                "user": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        email_token = get_object_or_404(EmailToken, token=token)
        if not email_token.is_valid():
            email_token.delete()
            return Response(
                {"detail": "Срок действия токена истёк."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = email_token.user
        user.is_active = True
        user.save(update_fields=["is_active"])
        email_token.delete()

        return Response(
            {"message": "Аккаунт успешно активирован."},
            status=status.HTTP_200_OK,
        )
