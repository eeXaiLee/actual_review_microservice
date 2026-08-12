from rest_framework.test import APIClient


def test_get_reviews_basic_and_pagination(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews", {"branch_id": reviews_fixture.branch.id}
    )
    assert resp.status_code == 200
    assert "reviews" in resp.data

    resp2 = api_client.get(
        "/api/common/reviews",
        {"branch_id": reviews_fixture.branch.id, "limit": 1, "offset": 0},
    )
    assert resp2.status_code == 200
    assert len(resp2.data["reviews"]) == 1


def test_get_reviews_requires_branch_id(api_client):
    resp = api_client.get("/api/common/reviews")
    assert resp.status_code == 400


def test_get_reviews_rejects_non_numeric_branch_id(api_client):
    resp = api_client.get("/api/common/reviews", {"branch_id": "abc"})
    assert resp.status_code == 400


def test_get_reviews_min_rating_configurable(api_client, reviews_fixture):
    # min_rating=4 по умолчанию скрывает отзыв с rating=3
    resp = api_client.get(
        "/api/common/reviews", {"branch_id": reviews_fixture.branch.id}
    )
    assert resp.status_code == 200
    assert len(resp.data["reviews"]) == 2

    # при более низком min_rating отзыв снова появляется
    resp2 = api_client.get(
        "/api/common/reviews",
        {"branch_id": reviews_fixture.branch.id, "min_rating": 1},
    )
    assert resp2.status_code == 200
    assert len(resp2.data["reviews"]) == 3


def test_reviews_providers_csv_filters_to_listed_providers_only(
    api_client, reviews_fixture
):
    resp = api_client.get(
        "/api/common/reviews",
        {
            "branch_id": reviews_fixture.branch.id,
            "providers": "yandex,vlru",
            "min_rating": 1,
        },
    )
    assert resp.status_code == 200
    # a1 (yandex, rating 3) + a2 (yandex, rating 5) + v1 (vlru, rating 4)
    # — все три отзыва из фикстуры
    assert len(resp.data["reviews"]) == 3
    providers = {r["provider"] for r in resp.data["reviews"]}
    assert providers == {"yandex", "vlru"}


def test_reviews_filters_by_rating(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews",
        {
            "branch_id": reviews_fixture.branch.id,
            "providers": "yandex",
            "filters": "rating__gt=4",
        },
    )
    assert resp.status_code == 200
    assert all(float(r["rating"]) > 4 for r in resp.data["reviews"])


def test_reviews_rejects_unsupported_filter_field(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews",
        {
            "branch_id": reviews_fixture.branch.id,
            "filters": "branch__organization__inn=123456789012",
        },
    )
    assert resp.status_code == 400


def test_reviews_rejects_invalid_filter_value_instead_of_crashing(
    api_client, reviews_fixture
):
    resp = api_client.get(
        "/api/common/reviews",
        {"branch_id": reviews_fixture.branch.id, "filters": "rating__gt=abc"},
    )
    assert resp.status_code == 400


def test_reviews_rejects_negative_offset(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews",
        {"branch_id": reviews_fixture.branch.id, "offset": -5},
    )
    assert resp.status_code == 400


def test_reviews_rejects_negative_limit(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews",
        {
            "branch_id": reviews_fixture.branch.id,
            "pick": "random",
            "limit": -1,
        },
    )
    assert resp.status_code == 400


def test_get_reviews_requires_authentication(reviews_fixture):
    resp = APIClient().get(
        "/api/common/reviews", {"branch_id": reviews_fixture.branch.id}
    )
    assert resp.status_code == 401


def test_get_reviews_rejects_foreign_branch(api_client, reviews_fixture):
    resp = api_client.get(
        "/api/common/reviews", {"branch_id": reviews_fixture.other_branch.id}
    )
    assert resp.status_code == 403
