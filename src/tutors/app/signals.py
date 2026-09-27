from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from tutors.app.models import Review


@receiver([post_save,  post_delete], sender=Review)
def update_tutor_rating(sender,instance, **kwargs):
    print(f"🔥 Сигнал сработал! Review ID: {instance.id}")
    instance.reviews.update_rating_and_count()



