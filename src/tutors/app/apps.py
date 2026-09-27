from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "tutors.app"

    def ready(self):
        import tutors.app.signals
