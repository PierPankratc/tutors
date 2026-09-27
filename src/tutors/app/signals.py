from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from tutors.app.models import Review


@receiver([post_save, post_delete], sender=Review, dispatch_uid='update_tutor_rating')
def update_tutor_rating(sender, instance, **kwargs):
    """
    Обновляет рейтинг и количество отзывов репетитора
    при создании, изменении или удалении отзыва.
    """
    instance.tutor.update_rating_and_count()


