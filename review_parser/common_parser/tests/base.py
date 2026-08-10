from datetime import timedelta

from django.utils import timezone

from common_parser.models import Branch, BranchIPMapping, Organization, Review


class ReviewsFixtureMixin:
    """Общие тестовые данные для тестов API отзывов: одна организация,
    один филиал и три отзыва с разными рейтингами и провайдерами."""

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

        BranchIPMapping.objects.create(branch=cls.branch, ip_address="1.2.3.4")
