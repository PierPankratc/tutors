from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from tutors.app.models import Review, Tutor


@receiver([post_save, post_delete], sender=Review, dispatch_uid="update_tutor_rating")
def update_tutor_rating(sender, instance, **kwargs):
    """
    Обновляет рейтинг и количество отзывов репетитора
    при создании, изменении или удалении отзыва.
    """
    instance.tutor.update_rating_and_count()
    cache.delete("tutors_list")


@receiver(
    [post_save, post_delete], sender=Tutor, dispatch_uid="invalidate_tutors_cache"
)
def invalidate_tutors_cache(sender, instance, **kwargs):
    cache.delete("tutors_list")
