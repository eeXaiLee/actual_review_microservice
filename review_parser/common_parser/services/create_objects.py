from django.db import IntegrityError
from loguru import logger

from common_parser.models import Branch, Organization, Playlist, Video
from common_parser.serializers import (
    BranchSerializer,
    OrganizationSerializer,
    PlaylistSerializer,
    ReviewSerializer,
    VideoSerializer,
)


def create_review(data: dict) -> bool:
    """
    Создаёт отзыв, если уже есть такой отзыв (тот же филиал, автор, текст и
    провайдер) — возвращает False. Уникальность отзыва проверяется не заранее
    отдельным запросом (это было небезопасно при параллельном запуске
    парсинга — два запуска могли не увидеть отзыв друг друга и оба его
    создать), а ограничением на уровне базы данных (Review.Meta.constraints):
    если такой отзыв уже есть, .save() сам упадёт с IntegrityError.
    """
    data_rewiew = {
                    'branch': data["branch"].id,
                    'author': data["author"],
                    'avatar': data["avatar"],
                    'rating': data["rating"],
                    'content': data["content"],
                    'published_date': data["published_date"],
                    'provider': data['provider']
                }

    if "photos" in data:
        data_rewiew["photos"] = data["photos"]

    if "video" in data:
        data_rewiew["video"] = data["video"]

    if "review_url" in data:
        data_rewiew["review_url"] = data["review_url"]

    serializer_review = ReviewSerializer(data=data_rewiew)

    if not serializer_review.is_valid():
        logger.warning(
            f"create_review: ошибки сериализатора: {serializer_review.errors}"
        )
        return False

    try:
        serializer_review.save()
        return True
    except IntegrityError:
        return False


def get_or_create_Organization(inn: str, name: str) -> Organization | None:
    try:
        organization = Organization.objects.get(inn=inn)
        if name and organization.name != name:
            organization.name = name
            organization.save()
    except Organization.DoesNotExist:
        serializer_org = OrganizationSerializer(data={
            "inn": inn,
            "name": name or ""
        })
        if serializer_org.is_valid():
            organization = serializer_org.save()
        else:
            logger.warning(
                f"get_or_create_Organization: ошибки сериализатора: {
                    serializer_org.errors
                }"
            )
            return None

    return organization


def get_or_create_Branch(
        organization: Organization,
        address: str,
        url_name: str,
        url: str,
        review_count_name: str,
        review_count: str,
        review_avg_name: str,
        review_avg: str
) -> Branch | None:
    if organization is None:
        logger.warning(
            "get_or_create_Branch: организация не создана, "
            "филиал создавать не из чего"
        )
        return None

    try:
        branch = Branch.objects.get(address=address, organization=organization)
        if url and getattr(branch, url_name) != url:
            setattr(branch, url_name, url)
        if review_count and getattr(branch, review_count_name) != review_count:
            setattr(branch, review_count_name, review_count)
        if review_avg and getattr(branch, review_avg_name) != review_avg:
            setattr(branch, review_avg_name, review_avg)
        branch.save()
    except Branch.DoesNotExist:
        serializer_branch = BranchSerializer(data={
            'organization': organization.id,
            'address': address or "",
            url_name: url
        })
        if serializer_branch.is_valid():
            branch = serializer_branch.save()
        else:
            logger.warning(
                f"get_or_create_Branch: ошибки сериализатора: {
                    serializer_branch.errors
                }"
            )
            return None

    return branch


def get_or_create_playlist(data: dict) -> Playlist | None:
    playlist_url = data.get('url')

    try:
        playlist = Playlist.objects.get(url=playlist_url)
        for key, value in data.items():
            setattr(playlist, key, value)
        playlist.save()
        return playlist
    except Playlist.DoesNotExist:
        serializer_playlist = PlaylistSerializer(data=data)
        if serializer_playlist.is_valid():
            return serializer_playlist.save()
        logger.warning(
            f"get_or_create_playlist: ошибки сериализатора: {
                serializer_playlist.errors
            }"
        )
        return None


def create_video(data: dict) -> bool:
    """
    Создаёт видео, если такого ещё нет (по url) — возвращает False, если уже
    есть или не прошла валидация. Уникальность по url проверяется не только
    заранее отдельным запросом (при параллельном парсинге это ненадёжно), но
    и ограничением на уровне базы данных: если видео всё же успеют создать
    параллельно, .save() упадёт с IntegrityError, и мы просто вернём False.
    """
    if Video.objects.filter(url=data["url"]).exists():
        return False

    serializer_video = VideoSerializer(data=data)
    if not serializer_video.is_valid():
        logger.warning(
            f"create_video: ошибки сериализатора: {serializer_video.errors}"
        )
        return False

    try:
        serializer_video.save()
        return True
    except IntegrityError:
        return False
