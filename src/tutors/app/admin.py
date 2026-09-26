from django.contrib import admin

from tutors.app.models import Review, Student, Tutor


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 1


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "created_at", "age", "updated_at"]
    list_filter = ["name", "email", "created_at", "age", "updated_at"]
    search_fields = ["name", "email"]
    inlines = [
        ReviewInline,
    ]


@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "last_name",
        "is_high_edu",
        "experience",
        "created_at",
        "age",
        "updated_at",
    ]
    list_filter = [
        "name",
        "last_name",
        "is_high_edu",
        "experience",
        "created_at",
        "age",
        "updated_at",
    ]
    search_fields = ["name", "last_name", "is_high_edu", "experience", "email"]
    inlines = [
        ReviewInline,
    ]
