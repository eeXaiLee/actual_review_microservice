from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from loguru import logger

from .models import Branch, BranchIPMapping, PlaylistIPMapping, Video, Playlist, Review
from .serializers import ReviewSerializer, BranchSerializer, VideoSerializer, PlaylistSerializer
from common_parser.services.reviews_query import (
    get_reviews_response_for_branches,
    UnsupportedFilterError,
    SORT_CHOICES,
)


def _client_ip(request) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


REVIEWS_RESPONSE_SCHEMA = '''
                    "branch": {
                        "id", "address", "organization",
                        "google_map_url", "yandex_map_url", "twogis_map_url", "vlru_url", "vlru_org_id",
                        "google_review_count", "google_review_avg", "google_parse_date",
                        "yandex_review_count", "yandex_review_avg", "yandex_parse_date",
                        "twogis_review_count", "twogis_review_avg", "twogis_parse_date",
                        "vlru_review_count", "vlru_review_avg", "vlru_parse_date"
                    },
                    "reviews": [
                        {"id", "author", "avatar", "video", "photos", "published_date",
                         "rating", "content", "provider", "branch", "review_url"}
                    ],
                    "total_filtered": "сколько отзывов подходит под текущий запрос (с учётом всех фильтров)",
                    "offset": "текущее смещение пагинации",
                    "limit": "текущий размер страницы (null, если не задан)",
                    "provider_totals_unfiltered": [{"provider", "review_count"}]
                            '''

# google не парсится (парсер убран при рефакторинге), поэтому в список для
# фильтра его не включаем — иначе в дропдауне будет вариант, который никогда
# не вернёт ни одного отзыва
PROVIDER_VALUES = [choice[0] for choice in Review.PROVIDER_CHOICES if choice[0] != "google"]

REVIEWS_MANUAL_PARAMETERS = [
    openapi.Parameter(
        'providers', openapi.IN_QUERY,
        description="Провайдеры, отзывы которых нужно вернуть (если не задано — все провайдеры филиала)",
        type=openapi.TYPE_ARRAY,
        items=openapi.Items(type=openapi.TYPE_STRING, enum=PROVIDER_VALUES),
        collection_format='csv',
        required=False,
    ),
    openapi.Parameter('min_rating', openapi.IN_QUERY, description="Минимальный рейтинг отзыва (по умолчанию 4)", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('has_photos', openapi.IN_QUERY, description="true — только отзывы с фото, false — только без фото", type=openapi.TYPE_BOOLEAN, required=False),
    openapi.Parameter('author', openapi.IN_QUERY, description="Поиск по имени автора (частичное совпадение, без учёта регистра)", type=openapi.TYPE_STRING, required=False),
    openapi.Parameter(
        'sort', openapi.IN_QUERY,
        description="Сортировка отзывов (по умолчанию newest)",
        type=openapi.TYPE_STRING,
        enum=list(SORT_CHOICES),
        required=False,
    ),
    openapi.Parameter('offset', openapi.IN_QUERY, description="Пагинация: смещение", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('limit', openapi.IN_QUERY, description="Пагинация: количество отзывов", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('filters', openapi.IN_QUERY, description="Полный фильтр по полям отзыва — для случаев, не покрытых полями выше", type=openapi.TYPE_STRING, required=False),
]


@swagger_auto_schema(
    method="GET",
    manual_parameters=[
        openapi.Parameter('branch_id', openapi.IN_QUERY, description="Идентификатор филиала", type=openapi.TYPE_STRING, required=True),
    ] + REVIEWS_MANUAL_PARAMETERS,
    responses={200: REVIEWS_RESPONSE_SCHEMA, 400: "Некорректные данные"},
)
@api_view(['GET'])
def get_reviews(request):
    branch_id = request.query_params.get('branch_id')
    if not branch_id:
        return Response({"detail": "branch_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if not branch_id.isdigit():
        return Response({"detail": "branch_id must be a number"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        branch = Branch.objects.get(id=branch_id)
    except Branch.DoesNotExist:
        return Response({"detail": "Branch not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        service_result = get_reviews_response_for_branches(branches=[branch], query_params=request.query_params)
    except UnsupportedFilterError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    reviews_data = ReviewSerializer(service_result["reviews"], many=True).data

    data = {
        'branch': BranchSerializer(branch).data,
        'reviews': reviews_data,
        'total_filtered': service_result["total_filtered"],
        'offset': service_result["offset"],
        'limit': service_result["limit"],
        'provider_totals_unfiltered': service_result["provider_totals_unfiltered"],
    }
    return Response(data)


@swagger_auto_schema(
    method="GET",
    manual_parameters=REVIEWS_MANUAL_PARAMETERS,
    responses={200: REVIEWS_RESPONSE_SCHEMA, 400: "Некорректные данные"},
)
@api_view(['GET'])
def get_reviews_by_ip(request):
    ip = _client_ip(request)
    branches = [mapping.branch for mapping in BranchIPMapping.objects.filter(ip_address=ip)]

    try:
        service_result = get_reviews_response_for_branches(branches=branches, query_params=request.query_params)
    except UnsupportedFilterError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    reviews_data = ReviewSerializer(service_result["reviews"], many=True).data

    data = {
        'ip': ip,
        'branches': BranchSerializer(branches, many=True).data,
        'reviews': reviews_data,
        'total_filtered': service_result["total_filtered"],
        'offset': service_result["offset"],
        'limit': service_result["limit"],
        'provider_totals_unfiltered': service_result["provider_totals_unfiltered"],
    }
    return Response(data)


@swagger_auto_schema(method="GET", auto_schema=None)
@api_view(['GET'])
def get_videos_by_ip(request):
    ip = _client_ip(request)
    playlists = [mapping.playlist for mapping in PlaylistIPMapping.objects.filter(ip_address=ip)]

    videos = Video.objects.filter(playlist__in=playlists)
    videos_data = VideoSerializer(videos, many=True).data
    playlist_serializer = PlaylistSerializer(playlists, many=True)

    data = {
        'ip': ip,
        'playlists': playlist_serializer.data,
        'provider_videos_count': Video.objects.filter(playlist__in=playlists).values('playlist__provider').annotate(review_count=Count('id')),
        'videos': videos_data,
    }
    return Response(data)


@csrf_exempt
def webhook(request):
    logger.info(f"webhook received: body={request.body.decode('utf-8')}")
    return HttpResponse(status=200)
