from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from common_parser.models import ApiClient, Branch, Organization, Review


@pytest.fixture
def reviews_fixture(db):
    """
    Общие тестовые данные для тестов API отзывов: одна организация, один
    филиал, три отзыва с разными рейтингами и провайдерами, JWT-клиент этой
    организации (.user) и чужой филиал (.other_branch) для проверки, что
    чужие данные не отдаются.
    """
    org = Organization.objects.create(inn="123456789012", name="Org")
    branch = Branch.objects.create(
        organization=org,
        address="Addr",
        yandex_map_url="https://yandex.ru/maps/org/x",
        twogis_map_url="https://2gis.ru/firm/123",
        vlru_url="https://www.vl.ru/test",
    )

    Review.objects.create(
        branch=branch,
        author="a1",
        rating=3,
        content="c1",
        provider="yandex",
        published_date=timezone.now() - timedelta(days=2),
    )
    Review.objects.create(
        branch=branch,
        author="a2",
        rating=5,
        content="c2",
        provider="yandex",
        published_date=timezone.now() - timedelta(days=1),
    )
    Review.objects.create(
        branch=branch,
        author="v1",
        rating=4,
        content="vc1",
        provider="vlru",
        published_date=timezone.now(),
    )

    user = User.objects.create_user(username="client", password="pass12345")
    ApiClient.objects.create(user=user, organization=org)

    other_org = Organization.objects.create(
        inn="987654321098", name="Other Org"
    )
    other_branch = Branch.objects.create(
        organization=other_org, address="Other Addr"
    )

    return SimpleNamespace(branch=branch, other_branch=other_branch, user=user)


@pytest.fixture
def api_client(reviews_fixture):
    """Аутентифицированный DRF-клиент от имени клиента reviews_fixture."""
    client = APIClient()
    client.force_authenticate(user=reviews_fixture.user)
    return client
