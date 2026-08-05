from typing import Any, Iterable

from django.db.models import Count, Q, QuerySet, Case, When, Value, IntegerField

from common_parser.models import Branch, Review


PROVIDER_CHOICES = ["yandex", "2gis", "vlru", "google"]

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


def parse_providers_param(query_params) -> list[dict[str, Any]]:
    """
    Разбирает провайдеров из query-параметров в формате CSV:
    providers=yandex,vlru&count_yandex=1&filters_yandex=rating__gt=4
    """
    providers_raw = query_params.get("providers")
    provider_single = query_params.get("provider")

    raw = (providers_raw or provider_single or "").strip()
    if not raw:
        return []

    providers_list = [p.strip() for p in raw.split(",") if p.strip()]
    global_count = _parse_int(query_params.get("count"))
    global_filters = query_params.get("filters") or ""

    result: list[dict[str, Any]] = []
    for prov in providers_list:
        prov_count = _parse_int(query_params.get(f"count_{prov}"))
        prov_filters = query_params.get(f"filters_{prov}") or ""
        result.append(
            {
                "provider": prov,
                "count": prov_count if prov_count is not None else global_count,
                "filters": prov_filters if prov_filters else global_filters,
            }
        )
    return result


def _ordered(qs: QuerySet[Review], *, sort_photos: bool) -> QuerySet[Review]:
    if not sort_photos:
        return qs.order_by("-published_date")
    return qs.order_by(
        Case(
            When(~Q(photos__isnull=True) & ~Q(photos=""), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ).desc(),
        "-published_date",
    )


def get_reviews_response_for_branches(*, branches: Iterable[Branch], query_params) -> dict[str, Any]:
    branches_list = list(branches)
    only_providers = _parse_bool(query_params.get("only_providers"), default=False)
    providers = parse_providers_param(query_params)
    sort_photos = _parse_bool(query_params.get("sort_photos"), default=False)
    min_rating = _parse_int(query_params.get("min_rating"))
    if min_rating is None:
        min_rating = DEFAULT_MIN_RATING

    reviews_data: list[Review] | QuerySet[Review]

    if providers:
        reviews_list: list[Review] = []
        for prov in providers:
            provider_name = prov.get("provider")
            predata = Review.objects.filter(
                branch__in=branches_list, provider=provider_name, rating__gte=min_rating
            )
            predata = _ordered(predata, sort_photos=sort_photos)

            filters = (prov.get("filters") or "").strip()
            if filters:
                predata = predata.filter(parse_filter_string(filters))

            count = prov.get("count")
            if count:
                reviews_list += list(predata[:count])
            else:
                reviews_list += list(predata)

        if not only_providers:
            provider_to_exclude = [item["provider"] for item in providers if item.get("provider")]
            others = Review.objects.filter(
                branch__in=branches_list, rating__gte=min_rating
            ).exclude(provider__in=provider_to_exclude)
            others = _ordered(others, sort_photos=sort_photos)
            reviews_list += list(others)

        reviews_data = reviews_list
    else:
        offset = _parse_int(query_params.get("offset")) or 0
        limit = _parse_int(query_params.get("limit"))
        filters = query_params.get("filters") or ""

        reviews = Review.objects.filter(branch__in=branches_list, rating__gte=min_rating)
        reviews = _ordered(reviews, sort_photos=sort_photos)

        if filters:
            reviews = reviews.filter(parse_filter_string(filters))

        if limit is not None:
            reviews = reviews[offset : offset + limit]
        elif offset:
            reviews = reviews[offset:]
        reviews_data = reviews

    provider_reviews_count = (
        Review.objects.filter(branch__in=branches_list)
        .values("provider")
        .annotate(review_count=Count("id"))
    )

    return {
        "providers_requested": providers,
        "reviews": reviews_data,
        "provider_reviews_count": provider_reviews_count,
    }
