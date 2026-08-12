from rest_framework.test import APITestCase

from .base import ReviewsFixtureMixin


class ReviewsApiTests(ReviewsFixtureMixin, APITestCase):
    """Тесты GET /api/common/reviews (по branch_id)."""

    def test_get_reviews_basic_and_pagination(self):
        resp = self.client.get(
            "/api/common/reviews", {"branch_id": self.branch.id}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("reviews", resp.data)

        resp2 = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "limit": 1, "offset": 0},
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data["reviews"]), 1)

    def test_get_reviews_requires_branch_id(self):
        resp = self.client.get("/api/common/reviews")
        self.assertEqual(resp.status_code, 400)

    def test_get_reviews_rejects_non_numeric_branch_id(self):
        resp = self.client.get("/api/common/reviews", {"branch_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_get_reviews_min_rating_configurable(self):
        # min_rating=4 по умолчанию скрывает отзыв с rating=3
        resp = self.client.get(
            "/api/common/reviews", {"branch_id": self.branch.id}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["reviews"]), 2)

        # при более низком min_rating отзыв снова появляется
        resp2 = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "min_rating": 1},
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data["reviews"]), 3)

    def test_reviews_providers_csv_filters_to_listed_providers_only(self):
        resp = self.client.get(
            "/api/common/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex,vlru",
                "min_rating": 1,
            },
        )
        self.assertEqual(resp.status_code, 200)
        # a1 (yandex, rating 3) + a2 (yandex, rating 5) + v1 (vlru, rating 4)
        # — все три отзыва из фикстуры
        self.assertEqual(len(resp.data["reviews"]), 3)
        providers = {r["provider"] for r in resp.data["reviews"]}
        self.assertEqual(providers, {"yandex", "vlru"})

    def test_reviews_filters_by_rating(self):
        resp = self.client.get(
            "/api/common/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex",
                "filters": "rating__gt=4",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            all(float(r["rating"]) > 4 for r in resp.data["reviews"])
        )

    def test_reviews_rejects_unsupported_filter_field(self):
        resp = self.client.get(
            "/api/common/reviews",
            {
                "branch_id": self.branch.id,
                "filters": "branch__organization__inn=123456789012",
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_reviews_rejects_invalid_filter_value_instead_of_crashing(self):
        resp = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "filters": "rating__gt=abc"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_reviews_rejects_negative_offset(self):
        resp = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "offset": -5},
        )
        self.assertEqual(resp.status_code, 400)

    def test_reviews_rejects_negative_limit(self):
        resp = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "pick": "random", "limit": -1},
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_reviews_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(
            "/api/common/reviews", {"branch_id": self.branch.id}
        )
        self.assertEqual(resp.status_code, 401)

    def test_get_reviews_rejects_foreign_branch(self):
        resp = self.client.get(
            "/api/common/reviews", {"branch_id": self.other_branch.id}
        )
        self.assertEqual(resp.status_code, 403)
