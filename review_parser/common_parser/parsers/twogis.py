import json
import os
import re
import time
from datetime import datetime

from django.utils import timezone
from loguru import logger

from common_parser.models import Branch
from common_parser.services.create_objects import (
    create_review,
    get_or_create_Branch,
    get_or_create_Organization,
)
from common_parser.services.http_client import get as http_get

TWOGIS_API_KEY = os.getenv("TWOGIS_API_KEY", "")

MAX_2GIS_PAGES = 20


def convert_2gis_reviews_to_model_data(
    branch: Branch, review_data: dict, url: str
) -> dict:
    """
    Преобразует данные отзывов из 2GIS в объекты модели Review.

    :param branch: Объект Branch, к которому привязываются отзывы
    :param review_data: Данные review
    :return: словарь для модели review
    """

    try:
        published_date = datetime.fromisoformat(review_data["date_created"])
        if timezone.is_naive(published_date):
            published_date = timezone.make_aware(published_date)
    except (KeyError, ValueError):
        published_date = timezone.now()

    avatar_url = (
        review_data
        .get("user", {})
        .get("photo_preview_urls", {})
        .get("url", "")
    )

    photos_pr = review_data.get("photos", [])

    photos = []

    for photo in photos_pr:
        # Извлекаем ссылку 'url' из каждого фото
        photos.append(photo["preview_urls"]["url"])

    photos_str = ",".join(photos)

    review = {
        "branch": branch,
        "author": review_data.get("user", {}).get("name", "Аноним"),
        "avatar": avatar_url if avatar_url else None,
        "video": None,
        "photos": photos_str,
        "published_date": published_date,
        "rating": review_data.get("rating", 0),
        "content": review_data.get("text", ""),
        "provider": "2gis",
        "review_url": url + "/tab/reviews/review/" + review_data.get("id", ""),
    }
    return review


def create_2gis_reviews(
    url: str, inn: str, org_name: str = "", address: str = "", count: str = 50
) -> int | None:
    dict_2gis = parse(get_api_url_from_2gis(url, count or 50))

    try:
        for _ in range(MAX_2GIS_PAGES):
            new_dict = parse(
                get_api_url_from_2gis_offset(
                    url, count or 50, len(dict_2gis["reviews"])
                )
            )["reviews"]
            if not new_dict:
                break
            dict_2gis["reviews"] += new_dict
        else:
            logger.warning(
                f"2GIS: пагинация остановлена по потолку "
                f"в {MAX_2GIS_PAGES} страниц (url={url})"
            )
    except Exception:
        logger.exception("2GIS pagination failed")

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="twogis_map_url",
        url=url,
        review_count_name="twogis_review_count",
        review_count=dict_2gis["count"],
        review_avg_name="twogis_review_avg",
        review_avg=dict_2gis["rating"],
    )

    if branch is None:
        logger.error(
            f"2GIS: не удалось создать/найти филиал (address={address}), "
            f"отзывы не сохранены"
        )
        return None

    branch.twogis_parse_date = timezone.now()
    branch.save()

    cnt = 0

    for review in dict_2gis["reviews"]:
        if create_review(
            convert_2gis_reviews_to_model_data(
                branch=branch, review_data=review, url=url
            )
        ):
            cnt += 1

    parsed_count = len(dict_2gis.get("reviews", []))
    logger.info(
        f"2GIS create finished: url={url} branch_address={address} "
        f"parsed={parsed_count} created={cnt}"
    )
    return (len(dict_2gis["reviews"]), cnt)


def get_api_url_from_2gis(url: str, limit: int = 50) -> str:

    pattern = r"/firm/(\d+)"
    match = re.search(pattern, url)
    if match:
        firm_id = match.group(1)
    else:
        return None
    return f"https://public-api.reviews.2gis.com/2.0/branches/{firm_id}/reviews?limit={limit}&is_advertiser=true&fields=meta.branch_rating,meta.branch_reviews_count,meta.total_count&without_my_first_review=false&rated=true&sort_by=date_edited&key={TWOGIS_API_KEY}&locale=ru_RU"


def get_api_url_from_2gis_offset(
    url: str, limit: int = 50, offset: int = 50
) -> str:

    pattern = r"/firm/(\d+)"
    match = re.search(pattern, url)
    if match:
        firm_id = match.group(1)
    else:
        return None
    return f"https://public-api.reviews.2gis.com/2.0/branches/{firm_id}/reviews?limit={limit}&offset={offset}&is_advertiser=true&fields=meta.branch_rating,meta.branch_reviews_count,meta.total_count&without_my_first_review=false&rated=true&sort_by=date_edited&key={TWOGIS_API_KEY}&locale=ru_RU"


def parse(url):
    response = http_get(url)

    if response.status_code != 200:
        time.sleep(30)

        response = http_get(url)

    response_text = response.text
    response_dict = json.loads(response_text)

    if response_dict["meta"]["total_count"] == 0:
        time.sleep(30)
        response = http_get(url)
        response_text = response.text
        response_dict = json.loads(response_text)

    if response_dict["meta"]["total_count"] == 0:
        logger.error("2GIS parse failed: total_count=0")
        return {"error": "parse failed"}

    return {
        "rating": response_dict["meta"]["branch_rating"],
        "count": response_dict["meta"]["branch_reviews_count"],
        "reviews": response_dict["reviews"],
    }
