from django_filters import FilterSet
import django_filters

from tutors.app.models import Tutor


class TutorFilter(FilterSet):
    max_rating = django_filters.NumberFilter(field_name="rating")

    max_experience = django_filters.NumberFilter(
        field_name="experience"
    )

    high_edu = django_filters.BooleanFilter(field_name="is_high_edu")

    class Meta:
        model = Tutor
        fields = []
