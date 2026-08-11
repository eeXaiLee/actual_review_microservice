import os
from urllib.parse import parse_qs, urlparse

import isodate
from django.utils import timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from common_parser.services.create_objects import (
    create_video, get_or_create_playlist
)

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')

THUMBNAIL_KEYS_BY_QUALITY = ("maxres", "standard", "high", "medium", "default")

_youtube_client = None


def _get_client():
    """
    Клиент YouTube Data API создаётся лениво (при первом реальном обращении,
    а не при импорте модуля) и со static_discovery=True — иначе googleapiclient
    на каждый build() ходит в сеть за discovery-документом Google, и просто
    импорт этого файла мог бы упасть без сети.
    """
    global _youtube_client
    if _youtube_client is None:
        _youtube_client = build(
            "youtube",
            "v3",
            developerKey=YOUTUBE_API_KEY,
            static_discovery=True
        )
    return _youtube_client


def _extract_playlist_id(playlist_url: str) -> str | None:
    query = parse_qs(urlparse(playlist_url).query)
    playlist_ids = query.get("list")
    return playlist_ids[0] if playlist_ids else None


def get_playlist_videos(playlist_id: str) -> list[dict]:
    """Возвращает все видео плейлиста (проходит по всем страницам)."""
    youtube = _get_client()
    videos = []
    next_page_token = None

    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        items = response.get("items", [])
        video_ids = [
            item["snippet"]["resourceId"]["videoId"]
            for item in items
            if item.get("snippet", {}).get("resourceId", {}).get("videoId")
        ]

        durations = {}
        if video_ids:
            video_response = youtube.videos().list(
                part="contentDetails", id=",".join(video_ids)
            ).execute()
            durations = {
                item["id"]: int(
                    isodate.parse_duration(
                        item["contentDetails"]["duration"]
                    ).total_seconds()
                )
                for item in video_response.get("items", [])
            }

        for item in items:
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue

            thumbnails = snippet.get("thumbnails", {})
            best_key = next(
                (k for k in THUMBNAIL_KEYS_BY_QUALITY if k in thumbnails),
                None
            )
            best_thumbnail = thumbnails.get(best_key, {}) if best_key else {}

            videos.append({
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", ""),
                "author": snippet.get("channelTitle", ""),
                # ISO-8601 строка ("...Z") — сериализатор сам разберёт её в
                # timezone-aware datetime, вручную парсить не нужно.
                "date": snippet.get("publishedAt"),
                "preview": best_thumbnail.get("url", ""),
                "duration": durations.get(video_id, 0),
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_playlist_data(playlist_url: str) -> dict | None:
    playlist_id = _extract_playlist_id(playlist_url)
    if not playlist_id:
        logger.error(
            f"YouTube: не удалось найти ID плейлиста в ссылке {playlist_url}"
        )
        return None

    youtube = _get_client()

    try:
        playlist_response = youtube.playlists().list(
            part="snippet", id=playlist_id
        ).execute()
    except HttpError as e:
        logger.error(f"YouTube: ошибка запроса плейлиста {playlist_url}: {e}")
        return None

    items = playlist_response.get("items", [])
    if not items:
        logger.error(
            f"YouTube: плейлист не найден или недоступен: {playlist_url}"
        )
        return None

    try:
        videos = get_playlist_videos(playlist_id)
    except HttpError as e:
        logger.error(
            f"YouTube: ошибка получения видео плейлиста {playlist_url}: {e}"
        )
        return None

    return {
        "url": playlist_url,
        "title": items[0]["snippet"]["title"],
        "count": len(videos),
        "videos": videos,
        "provider": "youtube",
        "parse_date": timezone.now(),
    }


def parse_youtube_videos(url: str) -> tuple[int, int] | None:
    if not YOUTUBE_API_KEY:
        logger.error("YouTube: не задан YOUTUBE_API_KEY, парсинг невозможен")
        return None

    data = get_playlist_data(url)
    if data is None:
        return None

    videos = data.pop("videos")
    playlist = get_or_create_playlist(data)
    if playlist is None:
        logger.error(
            f"YouTube: не удалось создать/найти плейлист {url}, "
            "видео не сохранены"
        )
        return None

    for video in videos:
        video["playlist"] = playlist.id

    cnt = 0
    for video in videos:
        if create_video(video):
            cnt += 1

    logger.info(
        f"YouTube create finished: "
        f"url={url} parsed={len(videos)} created={cnt}"
    )
    return (len(videos), cnt)
