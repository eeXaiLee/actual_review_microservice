from rest_framework.test import APITestCase

from .base import ReviewsFixtureMixin


class OrganizationReviewsApiTests(ReviewsFixtureMixin, APITestCase):
    """Тесты GET /api/common/organization_reviews (все филиалы организации)."""

    def test_organization_reviews(self):
        resp = self.client.get("/api/common/organization_reviews")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("branches", resp.data)
        self.assertGreaterEqual(len(resp.data["reviews"]), 1)

    def test_organization_reviews_does_not_include_foreign_branch(self):
        resp = self.client.get("/api/common/organization_reviews")
        self.assertEqual(resp.status_code, 200)
        branch_ids = {b["id"] for b in resp.data["branches"]}
        self.assertNotIn(self.other_branch.id, branch_ids)

    def test_organization_reviews_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/common/organization_reviews")
        self.assertEqual(resp.status_code, 401)
