from rest_framework.test import APIClient


def test_organization_reviews(api_client):
    resp = api_client.get("/api/common/organization_reviews")
    assert resp.status_code == 200
    assert "branches" in resp.data
    assert len(resp.data["reviews"]) >= 1


def test_organization_reviews_does_not_include_foreign_branch(
    api_client, reviews_fixture
):
    resp = api_client.get("/api/common/organization_reviews")
    assert resp.status_code == 200
    branch_ids = {b["id"] for b in resp.data["branches"]}
    assert reviews_fixture.other_branch.id not in branch_ids


def test_organization_reviews_requires_authentication(reviews_fixture):
    resp = APIClient().get("/api/common/organization_reviews")
    assert resp.status_code == 401
