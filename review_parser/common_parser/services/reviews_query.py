import random
from typing import Any, Iterable

from django.db.models import Q, QuerySet, Case, When, Value, IntegerField, Count, Avg

from common_parser.models import Branch, Review


DEFAULT_MIN_RATING = 4

ALLOWED_FILTER_FIELDS = {
    "author",
    "avatar",
    "video",
    "photos",
    "published_date",
    "rating",
    "content",
    "provider",
    "review_url",
}

ALLOWED_FILTER_LOOKUPS = {
    "exact",
    "gt",
    "lt",
    "gte",
    "lte",
    "in",
    "isnull",
    "icontains",
}

SORT_CHOICES = ("newest", "oldest", "photos_first")
DEFAULT_SORT = "newest"

# что отобрать из общей отфильтрованной кучи (yandex+2gis+vlru вместе), ДО того
# как применится sort — то есть sort просто упорядочивает уже отобранные N,
# а pick решает, какие именно N туда попадут
PICK_CHOICES = ("earliest", "latest", "random")

PROVIDER_KEYS = ("yandex", "2gis", "vlru")


def _select_batch(
    reviews_qs: QuerySet[Review], *, pick: str, offset: int, limit: int | None
) -> QuerySet[Review]:
    if pick == "random":
        ids = list(reviews_qs.values_list("id", flat=True))
        sample_size = min(limit, len(ids)) if limit is not None else len(ids)
        sampled_ids = random.sample(ids, sample_size)
        return Review.objects.filter(pk__in=sampled_ids)

    ordered = reviews_qs.order_by("published_date" if pick == "earliest" else "-published_date")
    if limit is not None:
        sliced = ordered[offset:offset + limit]
    elif offset:
        sliced = ordered[offset:]
    else:
        sliced = ordered

    ids = list(sliced.values_list("id", flat=True))
    return Review.objects.filter(pk__in=ids)


def _provider_stats(
    branches_list: list[Branch], filtered_reviews: QuerySet[Review]
) -> dict[str, dict[str, Any]]:
    """
    Для каждого провайдера считаем две пары чисел по реальным отзывам в базе
    (не по бейджу с сайта — он считается по-другому и на другой выборке):
    review_count/review_avg — по всем отзывам без ограничений;
    review_count_filtered/review_avg_filtered — по текущему запросу с фильтрами.
    """
    totals = {
        row["provider"]: row
        for row in Review.objects.filter(branch__in=branches_list)
        .values("provider")
        .annotate(cnt=Count("id"), avg=Avg("rating"))
    }
    filtered = {
        row["provider"]: row
        for row in filtered_reviews.values("provider").annotate(cnt=Count("id"), avg=Avg("rating"))
    }

    stats: dict[str, dict[str, Any]] = {}
    for provider in PROVIDER_KEYS:
        t = totals.get(provider)
        f = filtered.get(provider)
        stats[provider] = {
            "review_count": t["cnt"] if t else 0,
            "review_avg": round(t["avg"], 2) if t and t["avg"] is not None else None,
            "review_count_filtered": f["cnt"] if f else 0,
            "review_avg_filtered": round(f["avg"], 2) if f and f["avg"] is not None else None,
        }
    return stats


class UnsupportedFilterError(ValueError):
    """Клиент запросил фильтр по полю/оператору, которого нет в белом списке."""


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _validate_filter_key(key: str) -> None:
    field, sep, lookup = key.rpartition("__")
    if not sep or lookup not in ALLOWED_FILTER_LOOKUPS:
        field = key
    if field not in ALLOWED_FILTER_FIELDS:
        raise UnsupportedFilterError(f"Filtering by '{field}' is not supported")


def parse_filter_string(filter_str: str) -> Q:
    """
    Parse a filter string into a Django Q object.

    Supported:
    - field=value
    - field!=value
    - field__op=value (e.g. rating__gt=4)
    - !field__op=value (negation)
    - field__in=1,2,3 (and negation)
    - field__isnull=true/false

    Only fields/operators from ALLOWED_FILTER_FIELDS / ALLOWED_FILTER_LOOKUPS are
    accepted — anything else raises UnsupportedFilterError.
    """
    conditions = Q()
    if not filter_str:
        return conditions

    for part in filter_str.split("&"):
        if not part:
            continue

        if "!=" in part:
            key, value = part.split("!=", 1)
            _validate_filter_key(key)
            q_object = ~Q(**{key: value})
        elif "=" in part:
            key, value = part.split("=", 1)
            negate = False

            if key.startswith("!"):
                negate = True
                key = key[1:]

            _validate_filter_key(key)

            if key.endswith("__in"):
                value_list = [v.strip() for v in value.split(",") if v.strip()]
                q_object = Q(**{key: value_list})
            elif key.endswith("__isnull"):
                q_object = Q(**{key: value.lower() == "true"})
            else:
                q_object = Q(**{key: value})

            if negate:
                q_object = ~q_object
        else:
            continue

        conditions &= q_object

    return conditions


def _ordered(qs: QuerySet[Review], *, sort: str) -> QuerySet[Review]:
    if sort == "photos_first":
        return qs.order_by(
            Case(
                When(~Q(photos__isnull=True) & ~Q(photos=""), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ).desc(),
            "-published_date",
        )
    if sort == "oldest":
        return qs.order_by("published_date")
    return qs.order_by("-published_date")


def get_reviews_response_for_branches(*, branches: Iterable[Branch], query_params) -> dict[str, Any]:
    branches_list = list(branches)

    min_rating = _parse_int(query_params.get("min_rating"))
    if min_rating is None:
        min_rating = DEFAULT_MIN_RATING

    sort = (query_params.get("sort") or DEFAULT_SORT).strip()
    if sort not in SORT_CHOICES:
        sort = DEFAULT_SORT

    pick = (query_params.get("pick") or "").strip().lower()
    if pick not in PICK_CHOICES:
        pick = None

    has_photos_raw = query_params.get("has_photos")
    author = query_params.get("author")
    providers_raw = (query_params.get("providers") or "").strip()
    filters = query_params.get("filters") or ""

    offset = _parse_int(query_params.get("offset")) or 0
    limit = _parse_int(query_params.get("limit"))

    reviews = Review.objects.filter(branch__in=branches_list, rating__gte=min_rating)

    if providers_raw:
        providers_list = [p.strip() for p in providers_raw.split(",") if p.strip()]
        reviews = reviews.filter(provider__in=providers_list)

    if has_photos_raw is not None:
        if _parse_bool(has_photos_raw, default=False):
            reviews = reviews.exclude(photos__isnull=True).exclude(photos="")
        else:
            reviews = reviews.filter(Q(photos__isnull=True) | Q(photos=""))

    if author:
        reviews = reviews.filter(author__icontains=author)

    if filters:
        reviews = reviews.filter(parse_filter_string(filters))

    if pick:
        selected = _select_batch(reviews, pick=pick, offset=offset, limit=limit)
        page = _ordered(selected, sort=sort)
    else:
        ordered = _ordered(reviews, sort=sort)
        if limit is not None:
            page = ordered[offset:offset + limit]
        elif offset:
            page = ordered[offset:]
        else:
            page = ordered

    # для статистики нужен "чистый" queryset без order_by/среза — иначе Django
    # тянет поле сортировки в GROUP BY и ломает подсчёт (каждая запись
    # оказывается в отдельной "группе"), поэтому пересобираем по ID
    page_ids = list(page.values_list("id", flat=True))
    provider_stats = _provider_stats(branches_list, Review.objects.filter(pk__in=page_ids))

    return {
        "reviews": page,
        "offset": offset,
        "limit": limit,
        "provider_stats": provider_stats,
    }
