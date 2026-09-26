from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator

class Student(models.Model):
    name = models.CharField(max_length=30)
    age = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    email = models.EmailField()
    password = models.CharField(max_length=128, validators=[MinLengthValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'студент'
        verbose_name_plural = 'студенты'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'email'],
                name='unique_student_name_email'
            )
        ]
    
    def __str__(self):
        return self.name


class Tutor(models.Model):
    name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    age = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    email = models.EmailField()
    experience = models.FloatField(validators=[MinValueValidator(1)])
    is_high_edu = models.BooleanField(default=False)
    password = models.CharField(max_length=128, validators=[MinLengthValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'репетитор'
        verbose_name_plural = 'репетиторы'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'last_name', 'email'],
                name='unique_tutor_name_lastname_email'
            )
        ]
    
    def __str__(self):
        return f"{self.name} {self.last_name}"


class Review(models.Model):
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    creator = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='written_reviews'
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'отзыв'
        verbose_name_plural = 'отзывы'
        constraints = [
            models.UniqueConstraint(
                fields=['tutor', 'creator'],
                name='unique_review_per_student'
            )
        ]
    
    def __str__(self):
        return f"{self.creator.name} → {self.tutor.name} ({self.rating}⭐)"