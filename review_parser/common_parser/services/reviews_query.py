from typing import Any, Iterable

from django.db.models import Q, QuerySet, Case, When, Value, IntegerField

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

    reviews = _ordered(reviews, sort=sort)

    total_filtered = reviews.count()

    if limit is not None:
        page = reviews[offset:offset + limit]
    elif offset:
        page = reviews[offset:]
    else:
        page = reviews

    return {
        "reviews": page,
        "total_filtered": total_filtered,
        "offset": offset,
        "limit": limit,
    }
