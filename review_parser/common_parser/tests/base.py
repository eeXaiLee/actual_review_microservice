from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from common_parser.models import ApiClient, Branch, Organization, Review


class ReviewsFixtureMixin:
    """Общие тестовые данные для тестов API отзывов: одна организация,
    один филиал, три отзыва с разными рейтингами и провайдерами, а также
    JWT-клиент этой организации (cls.user) и чужой филиал (cls.other_branch)
    для проверки, что чужие данные не отдаются."""

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
            published_date=timezone.now() - timedelta(days=2),
        )
        # newer
        Review.objects.create(
            branch=cls.branch,
            author="a2",
            rating=5,
            content="c2",
            provider="yandex",
            published_date=timezone.now() - timedelta(days=1),
        )
        Review.objects.create(
            branch=cls.branch,
            author="v1",
            rating=4,
            content="vc1",
            provider="vlru",
            published_date=timezone.now(),
        )

        cls.user = User.objects.create_user(
            username="client", password="pass12345"
        )
        cls.api_client_profile = ApiClient.objects.create(
            user=cls.user, organization=org
        )

        other_org = Organization.objects.create(
            inn="987654321098", name="Other Org"
        )
        cls.other_branch = Branch.objects.create(
            organization=other_org, address="Other Addr"
        )

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
