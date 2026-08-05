from rest_framework.test import APITestCase

from .base import ReviewsFixtureMixin


class ReviewsByIpApiTests(ReviewsFixtureMixin, APITestCase):
    """Тесты GET /api/common/reviews_by_ip (филиал определяется по IP)."""

    def test_reviews_by_ip(self):
        resp = self.client.get(
            "/api/common/reviews_by_ip",
            {},
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("branches", resp.data)
        self.assertGreaterEqual(len(resp.data["reviews"]), 1)
