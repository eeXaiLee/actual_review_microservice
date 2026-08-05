from datetime import datetime, timedelta

from rest_framework.test import APITestCase

from common_parser.models import Branch, Organization, Review, BranchIPMapping


class ReviewsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        org = Organization.objects.create(inn="123456789012", name="Org")
        cls.branch = Branch.objects.create(
            organization=org,
            address="Addr",
            yandex_map_url="https://yandex.ru/maps/org/x",
            twogis_map_url="https://2gis.ru/firm/123",
            vlru_url="https://www.vl.ru/test",
        )

        # older
        Review.objects.create(
            branch=cls.branch,
            author="a1",
            rating=3,
            content="c1",
            provider="yandex",
            published_date=datetime.now() - timedelta(days=2),
        )
        # newer
        Review.objects.create(
            branch=cls.branch,
            author="a2",
            rating=5,
            content="c2",
            provider="yandex",
            published_date=datetime.now() - timedelta(days=1),
        )
        Review.objects.create(
            branch=cls.branch,
            author="v1",
            rating=4,
            content="vc1",
            provider="vlru",
            published_date=datetime.now(),
        )

        BranchIPMapping.objects.create(branch=cls.branch, ip_address="1.2.3.4")

    def test_get_reviews_basic_and_pagination(self):
        resp = self.client.get("/api/common/reviews", {"branch_id": self.branch.id})
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
        # default min_rating=4 hides the rating=3 review
        resp = self.client.get("/api/common/reviews", {"branch_id": self.branch.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["reviews"]), 2)

        # lowering min_rating brings it back
        resp2 = self.client.get(
            "/api/common/reviews", {"branch_id": self.branch.id, "min_rating": 1}
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data["reviews"]), 3)

    def test_reviews_providers_csv_only_providers(self):
        resp = self.client.get(
            "/api/common/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex,vlru",
                "count_yandex": 1,
                "only_providers": "true",
            },
        )
        self.assertEqual(resp.status_code, 200)
        # 1 yandex + all vlru (1)
        self.assertEqual(len(resp.data["reviews"]), 2)
        providers = {r["provider"] for r in resp.data["reviews"]}
        self.assertEqual(providers, {"yandex", "vlru"})

    def test_reviews_provider_filters(self):
        resp = self.client.get(
            "/api/common/reviews",
            {
                "branch_id": self.branch.id,
                "providers": "yandex",
                "filters_yandex": "rating__gt=4",
                "only_providers": "true",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(float(r["rating"]) > 4 for r in resp.data["reviews"]))

    def test_reviews_rejects_unsupported_filter_field(self):
        resp = self.client.get(
            "/api/common/reviews",
            {"branch_id": self.branch.id, "filters": "branch__organization__inn=123456789012"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_reviews_by_ip(self):
        resp = self.client.get(
            "/api/common/reviews_by_ip",
            {},
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("branches", resp.data)
        self.assertGreaterEqual(len(resp.data["reviews"]), 1)
