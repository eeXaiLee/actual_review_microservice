from functools import wraps
from time import perf_counter

from celery import shared_task
from django.shortcuts import get_object_or_404
from django.http import Http404
from loguru import logger

from common_parser.services.parse_all_providers import parse_all_providers
from common_parser.parsers.yandex import create_yandex_reviews
from common_parser.parsers.twogis import create_2gis_reviews
from common_parser.parsers.vlru import create_vlru_reviews
from common_parser.parsers.youtube import parse_youtube_videos
from common_parser.models import Branch, Playlist


def branch_task(func):
    """
    Декоратор для Celery-тасок вида `def task(branch): ...`, которые парсят
    один филиал по его branch_id: сам достаёт Branch, замеряет время,
    оборачивает результат в {"branch_id", "results"} и ловит Http404/любое
    другое исключение с логированием.
    """
    @wraps(func)
    def wrapper(branch_id):
        t0 = perf_counter()
        try:
            branch = get_object_or_404(Branch, id=branch_id)
            results = func(branch)
            logger.info(
                f"{func.__name__}: завершено, "
                f"branch_id={branch_id} "
                f"duration_ms={int((perf_counter()-t0)*1000)}"
            )
            return {"branch_id": branch_id, "results": results}
        except Http404:
            logger.error(f"Филиал не найден (id={branch_id})")
        except Exception as e:
            logger.exception(f"Ошибка в {func.__name__}: {e}")
    return wrapper


def playlist_task(func):
    """
    Декоратор для Celery-тасок вида `def task(playlist): ...`,
    которые парсят один плейлист по его playlist_id.
    """
    @wraps(func)
    def wrapper(playlist_id):
        t0 = perf_counter()
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id)
            results = func(playlist)
            logger.info(
                f"{func.__name__}: завершено, "
                f"playlist_id={playlist_id} "
                f"duration_ms={int((perf_counter()-t0)*1000)}"
            )
            return {"playlist_id": playlist_id, "results": results}
        except Http404:
            logger.error(f"Плейлист не найден (id={playlist_id})")
        except Exception as e:
            logger.exception(f"Ошибка в {func.__name__}: {e}")
    return wrapper


@shared_task(name='common_parser.tasks.weekly_parsing')
def weekly_parsing():
    t0 = perf_counter()
    branches = Branch.objects.all()

    dict_results = {}
    for branch in branches:
        dict_results[f"{branch.id}"] = parse_all_providers(branch)

    logger.info(f"weekly_parsing: завершено, филиалов={len(dict_results)} "
                f"duration_ms={int((perf_counter()-t0)*1000)}")
    return dict_results


@shared_task(name='parse_all_providers_async_on_create')
def parse_all_providers_async_on_create(branch_org_id, branch_address):
    t0 = perf_counter()
    try:
        branch = Branch.objects.get(
            organization_id=branch_org_id,
            address=branch_address
        )
        result = parse_all_providers(branch)
        logger.info(
            f"parse_all_providers_async_on_create: завершено, "
            f"branch_id={branch.id} "
            f"duration_ms={int((perf_counter()-t0)*1000)}"
        )
        return result
    except Branch.DoesNotExist:
        logger.error(
            f"Филиал не найден (org_id={branch_org_id}, "
            f"address={branch_address})"
        )
    except Exception as e:
        logger.exception(f"Ошибка в parse_all_providers_async_on_create: {e}")


@shared_task(name='parse_all_providers_async')
@branch_task
def parse_all_providers_async(branch):
    return parse_all_providers(branch)


@shared_task(name='parse_yandex_async')
@branch_task
def parse_yandex_async(branch):
    return create_yandex_reviews(
        url=branch.yandex_map_url,
        inn=branch.organization.inn,
        address=branch.address,
    )


@shared_task(name='parse_vlru_async')
@branch_task
def parse_vlru_async(branch):
    return create_vlru_reviews(
        branch.vlru_url, branch.organization.inn, address=branch.address
    )


@shared_task(name='parse_2gis_async')
@branch_task
def parse_2gis_async(branch):
    return create_2gis_reviews(
        url=branch.twogis_map_url,
        inn=branch.organization.inn,
        address=branch.address
    )


@shared_task(name='parse_youtube_videos_async')
@playlist_task
def parse_youtube_videos_async(playlist):
    return parse_youtube_videos(playlist.url)
