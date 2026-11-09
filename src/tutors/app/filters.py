import django_filters
from django_filters import FilterSet

from tutors.app.models import Tutor


class TutorFilter(FilterSet):
    max_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")

    max_experience = django_filters.NumberFilter(
        field_name="experience", lookup_expr="lte"
    )
    min_experience = django_filters.NumberFilter(
        field_name="experience", lookup_expr="gte"
    )

    high_edu = django_filters.BooleanFilter(field_name="is_high_edu")

    class Meta:
        model = Tutor
        fields = []
