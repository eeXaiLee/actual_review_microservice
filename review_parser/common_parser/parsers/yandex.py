import re
from typing import Optional

from bs4 import BeautifulSoup
from django.utils import timezone
from loguru import logger
from playwright.sync_api import sync_playwright

from common_parser.services.create_objects import (
    create_review,
    get_or_create_Branch,
    get_or_create_Organization,
)
from common_parser.services.parse_date_string import parse_date_string

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _scroll_load_all_reviews(page) -> None:
    """
    Yandex Maps подгружает отзывы порциями (~50 штук) по мере прокрутки
    внутреннего списка отзывов, а не отдаёт их все сразу. Подгрузка
    следующей порции срабатывает, только когда список долистан строго
    до конца (scrollTop == scrollHeight) — небольшой прокрутки на
    фиксированное число пикселей недостаточно.
    """
    previous_count = -1
    stable_rounds = 0

    for _ in range(30):
        current_count = page.eval_on_selector_all(
            ".business-review-view__info", "els => els.length"
        )
        if current_count == previous_count:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        previous_count = current_count

        try:
            page.eval_on_selector(
                ".scroll__container",
                "el => { el.scrollTop = el.scrollHeight; }",
            )
        except Exception:
            break
        page.wait_for_timeout(1500)


def _fetch_rendered_html(url: str) -> str:
    """
    Yandex Maps сервером отдаёт только пустой каркас страницы (skeleton),
    сами отзывы подгружаются через JS уже в браузере. Поэтому обычный
    requests.get() здесь не подходит и нужен реальный рендеринг страницы.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9"},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector(
                ".business-review-view__info", state="attached", timeout=20000
            )
            _scroll_load_all_reviews(page)
        except Exception:
            logger.warning(
                f"Yandex reviews selector not found in time: url={url}"
            )
        html = page.content()
        browser.close()
        return html


def parse(url: str, limit: Optional[int] = None) -> dict:
    logger.info(f"Yandex: начат парсинг: url={url} limit={limit}")
    html = _fetch_rendered_html(url)

    soup = BeautifulSoup(html, "lxml")

    reviews_counter = None
    rating_global = None

    reviews_tab = soup.select_one(".tabs-select-view__title._name_reviews")
    if reviews_tab:
        counter_el = reviews_tab.select_one(".tabs-select-view__counter")
        if counter_el and counter_el.text:
            reviews_counter = counter_el.text.strip()

    stars_block = soup.select_one(".business-summary-rating-badge-view")
    if stars_block:
        rating_parts = [
            el.get_text(strip=True)
            for el in stars_block.select(
                ".business-summary-rating-badge-view__rating-text"
            )
        ]
        if rating_parts:
            rating_text = "".join(rating_parts)
            rating_text = (
                rating_text.replace("\xa0", "").replace(",", ".").strip()
            )
            try:
                rating_global = float(rating_text)
            except ValueError:
                rating_global = None

    result: list[dict] = []
    count = 0

    review_blocks = soup.select(".business-review-view__info")

    for review_block in review_blocks:
        avatar_img_url = ""
        avatar_el = review_block.select_one(".user-icon-view__icon")
        if avatar_el:
            style_attr = str(avatar_el.get("style", ""))
            match = re.search(r'url\(["\']?(.*?)["\']?\)', style_attr)
            if match:
                avatar_img_url = match.group(1).strip('"')

        author_name_el = review_block.select_one(
            ".business-review-view__author-name"
        )
        author_name = author_name_el.text.strip() if author_name_el else ""

        date_published_el = review_block.select_one(
            ".business-review-view__date"
        )
        date_published_raw = (
            date_published_el.text.strip() if date_published_el else ""
        )

        photos_obj = review_block.select(".business-review-media__item-img")
        image_srcs = []
        for photo in photos_obj:
            src = photo.get("src")
            if src:
                image_srcs.append(str(src))
        photos = ", ".join(image_srcs)

        stars_count = len(
            review_block.select(".business-rating-badge-view__star._full")
        )

        review_text_el = review_block.select_one(".business-review-view__body")
        review_text = review_text_el.text.strip() if review_text_el else ""
        if "Ещё" in review_text:
            review_text = review_text.replace("Ещё", "").strip()

        try:
            result.append(
                {
                    "author": author_name,
                    "avatar": avatar_img_url,
                    "published_date": parse_date_string(date_published_raw),
                    "rating": stars_count,
                    "content": review_text,
                    "provider": "yandex",
                    "photos": photos,
                }
            )
            count += 1
        except Exception as e:
            logger.warning(f"Yandex: не удалось разобрать отзыв: {e}")

        if limit and limit == count:
            break

    return {
        "count": reviews_counter,
        "rating": rating_global,
        "reviews": result,
    }


def create_yandex_reviews(
    url: str, inn: str, org_name: str = "", address: str = "", count: int = 50
) -> tuple[int, int] | None:
    dict_yandex = parse(url)

    branch = get_or_create_Branch(
        organization=get_or_create_Organization(inn, org_name),
        address=address,
        url_name="yandex_map_url",
        url=url,
        review_count_name="yandex_review_count",
        review_count=dict_yandex["count"],
        review_avg_name="yandex_review_avg",
        review_avg=dict_yandex["rating"],
    )

    if branch is None:
        logger.error(
            f"Yandex: не удалось создать/найти филиал (address={address}), "
            f"отзывы не сохранены"
        )
        return None

    branch.yandex_parse_date = timezone.now()
    branch.save()

    for d in dict_yandex["reviews"]:
        d["branch"] = branch

    cnt = 0

    for review in dict_yandex["reviews"]:
        if create_review(review):
            cnt += 1

    parsed_count = len(dict_yandex["reviews"])
    logger.info(
        f"Yandex create finished: url={url} branch_address={address} "
        f"parsed={parsed_count} created={cnt}"
    )
    return (len(dict_yandex["reviews"]), cnt)
