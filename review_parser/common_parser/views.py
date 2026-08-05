from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from loguru import logger

from .models import Branch, BranchIPMapping, PlaylistIPMapping, Video, Playlist
from .serializers import ReviewSerializer, BranchSerializer, VideoSerializer, PlaylistSerializer
from common_parser.services.reviews_query import (
    get_reviews_response_for_branches,
    UnsupportedFilterError,
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
                    "provider_reviews_count": [{"provider", "review_count"}],
                    "reviews": [
                        {"id", "author", "avatar", "video", "photos", "published_date",
                         "rating", "content", "provider", "branch", "review_url"}
                    ]
                            '''

REVIEWS_MANUAL_PARAMETERS = [
    openapi.Parameter('providers', openapi.IN_QUERY, description="Провайдеры через запятую, например yandex,vlru", type=openapi.TYPE_STRING, required=False),
    openapi.Parameter('only_providers', openapi.IN_QUERY, description="Показывать только перечисленные в providers площадки, без остальных", type=openapi.TYPE_BOOLEAN, required=False),
    openapi.Parameter('min_rating', openapi.IN_QUERY, description="Минимальный рейтинг отзыва (по умолчанию 4)", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('sort_photos', openapi.IN_QUERY, description="Сначала показывать отзывы с фото", type=openapi.TYPE_BOOLEAN, required=False),
    openapi.Parameter('offset', openapi.IN_QUERY, description="Пагинация: смещение (применяется, только если providers не задан)", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('limit', openapi.IN_QUERY, description="Пагинация: количество отзывов (применяется, только если providers не задан)", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('filters', openapi.IN_QUERY, description="Фильтр по полям отзыва, например rating__gt=4&author__icontains=ivan (применяется, только если providers не задан)", type=openapi.TYPE_STRING, required=False),
    openapi.Parameter('count_<provider>', openapi.IN_QUERY, description="Лимит отзывов для конкретного провайдера, например count_yandex=5", type=openapi.TYPE_INTEGER, required=False),
    openapi.Parameter('filters_<provider>', openapi.IN_QUERY, description="Фильтр для конкретного провайдера, например filters_yandex=rating__gt=4", type=openapi.TYPE_STRING, required=False),
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
        'provider_reviews_count': service_result["provider_reviews_count"],
        'reviews': reviews_data,
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
        'provider_reviews_count': service_result["provider_reviews_count"],
        'reviews': reviews_data,
    }
    return Response(data)


@swagger_auto_schema(
    method="GET",
    manual_parameters=[],
    responses={200: '''
                    "ip",
                    "playlists": [{"id", "title", "count", "url", "parse_date", "provider"}],
                    "provider_videos_count": [{"playlist__provider", "review_count"}],
                    "videos": [
                        {"id", "url", "title", "author", "date", "preview", "duration", "playlist"}
                    ]
                            ''', 400: "Некорректные данные"}
)
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
