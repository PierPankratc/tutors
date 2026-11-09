from django.test import TestCase
from rest_framework.test import APIClient

from tutors.app.models import Review, Student, Tutor


class TutorAppTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = Student.objects.create(
            name="Alice",
            age=20,
            email="alice@example.com",
            password="securepassword123",
        )
        self.tutor = Tutor.objects.create(
            name="Bob",
            last_name="Smith",
            age=35,
            email="bob@example.com",
            experience=5.0,
            is_high_edu=True,
            password="securepassword123",
        )

    def test_rating_updated_on_review_create_and_delete(self):
        review = Review.objects.create(
            tutor=self.tutor,
            creator=self.student,
            rating=4,
            text="Great tutor!",
        )
        self.tutor.refresh_from_db()
        self.assertEqual(self.tutor.rating, 4.0)
        self.assertEqual(self.tutor.count_review, 1)

        review.delete()
        self.tutor.refresh_from_db()
        self.assertEqual(self.tutor.rating, 0.0)
        self.assertEqual(self.tutor.count_review, 0)

    def test_endpoints_return_200(self):
        for url in ["/app/students/", "/app/tutors/", "/app/reviews/", "/top/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
