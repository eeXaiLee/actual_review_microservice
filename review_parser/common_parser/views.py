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
from .serializers import ReviewSerializer, BranchResponseSerializer, VideoSerializer, PlaylistSerializer
from common_parser.services.reviews_query import (
    get_reviews_response_for_branches,
    UnsupportedFilterError,
    SORT_CHOICES,
    PICK_CHOICES,
)


def _client_ip(request) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


REVIEWS_RESPONSE_SCHEMA = '''
                    "branch": {
                        "id", "address",
                        "organization": {"id", "name", "inn"},
                        "providers": {
                            "yandex": {"url", "parse_date", "review_count", "review_avg", "review_count_filtered", "review_avg_filtered"},
                            "2gis": {"url", "parse_date", "review_count", "review_avg", "review_count_filtered", "review_avg_filtered"},
                            "vlru": {"url", "org_id", "parse_date", "review_count", "review_avg", "review_count_filtered", "review_avg_filtered"}
                        }
                    },
                    "reviews": [
                        {"id", "author", "avatar", "video", "photos", "published_date",
                         "rating", "content", "provider", "branch", "review_url"}
                    ],
                    "offset": "текущее смещение пагинации (параметр скрыт из формы Swagger, но принимается)",
                    "limit": "сколько отзывов запрошено (null, если не задан)"
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
    openapi.Parameter('limit', openapi.IN_QUERY, description="Максимальное количество отзывов в ответе. Если параметр providers не задан, отзывы выбираются из объединённой выборки по всем провайдерам филиала", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter(
        'pick', openapi.IN_QUERY,
        description="Какие именно limit отзывов взять: latest — самые новые, earliest — самые старые, random — случайные. Если не задано — работают offset/sort как обычная постраничная выдача",
        type=openapi.TYPE_STRING,
        enum=list(PICK_CHOICES),
        required=False,
    ),
    openapi.Parameter(
        'sort', openapi.IN_QUERY,
        description="Как расположить отобранные отзывы для показа (по умолчанию newest)",
        type=openapi.TYPE_STRING,
        enum=list(SORT_CHOICES),
        required=False,
    ),
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
        'branch': BranchResponseSerializer(
            branch, context={'provider_stats': service_result['provider_stats']}
        ).data,
        'reviews': reviews_data,
        'offset': service_result["offset"],
        'limit': service_result["limit"],
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
        'branches': BranchResponseSerializer(
            branches, many=True, context={'provider_stats': service_result['provider_stats']}
        ).data,
        'reviews': reviews_data,
        'offset': service_result["offset"],
        'limit': service_result["limit"],
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
