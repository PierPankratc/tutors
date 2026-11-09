from django.contrib import admin

from tutors.account.models import EmailToken


@admin.register(EmailToken)
class EmailTokenAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "token", "created_at"]
    readonly_fields = ["token", "created_at"]
