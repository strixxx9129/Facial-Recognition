"""
YouTube Data API v3 client.

Responsibilities:
- Extract playlist ID from any YouTube playlist URL format
- Fetch all playlist items with pagination (handles >50 items)
- Fetch video metadata in batches of 50 (API limit)
- Parse duration from ISO 8601 to milliseconds
- Handle API errors and quota exhaustion gracefully
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_YT_BASE = settings.YOUTUBE_API_BASE_URL
_API_KEY = settings.YOUTUBE_API_KEY

# ISO 8601 duration pattern: PT1H2M3S, PT30S, P1DT2H etc.
_ISO_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?"
    r"T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


@dataclass
class YouTubeTrack:
    """Normalised representation of a YouTube video as a music track."""
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    duration_ms: Optional[int]
    youtube_url: str
    position: int  # 1-based position in playlist


@dataclass
class YouTubePlaylistMeta:
    playlist_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    total_items: int
    tracks: list[YouTubeTrack] = field(default_factory=list)


class YouTubeAPIError(Exception):
    """Raised when the YouTube API returns a non-2xx response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"YouTube API {status_code}: {message}")


class YouTubeQuotaError(YouTubeAPIError):
    """Raised when YouTube API quota is exhausted (403 rateLimitExceeded)."""


def extract_playlist_id(url: str) -> str:
    """
    Extract playlist ID from various YouTube URL formats:
    - https://www.youtube.com/playlist?list=PLxxxxxx
    - https://www.youtube.com/watch?v=xxxxx&list=PLxxxxxx
    - https://youtu.be/xxxxx?list=PLxxxxxx
    - Raw ID: PLxxxxxx
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "list" in qs:
        return qs["list"][0]
    # Bare ID passed directly
    if re.match(r"^(PL|RD|UU|LL|FL|OL)[A-Za-z0-9_-]{10,}$", url):
        return url
    raise ValueError(f"Cannot extract playlist ID from: {url!r}")


def _iso_duration_to_ms(iso: str) -> Optional[int]:
    """Convert ISO 8601 duration string to milliseconds."""
    m = _ISO_DURATION_RE.match(iso)
    if not m:
        return None
    days = int(m.group("days") or 0)
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    seconds = int(m.group("seconds") or 0)
    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total_seconds * 1000


def _best_thumbnail(thumbnails: dict) -> str:
    """Pick highest resolution thumbnail available."""
    for quality in ("maxres", "standard", "high", "medium", "default"):
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return ""


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    """
    Execute a GET request against the YouTube API.
    Raises YouTubeQuotaError or YouTubeAPIError on failure.
    """
    params["key"] = _API_KEY
    resp = await client.get(f"{_YT_BASE}/{path}", params=params, timeout=15.0)

    if resp.status_code == 403:
        body = resp.json()
        errors = body.get("error", {}).get("errors", [{}])
        reason = errors[0].get("reason", "")
        if reason in ("rateLimitExceeded", "quotaExceeded", "dailyLimitExceeded"):
            raise YouTubeQuotaError(403, reason)
        raise YouTubeAPIError(403, body.get("error", {}).get("message", "Forbidden"))

    if resp.status_code != 200:
        raise YouTubeAPIError(resp.status_code, resp.text[:256])

    return resp.json()


async def fetch_playlist_metadata(playlist_id: str) -> dict:
    """Fetch title, channel name, thumbnail, and item count for a playlist."""
    async with httpx.AsyncClient() as client:
        data = await _get(
            client,
            "playlists",
            {
                "part": "snippet,contentDetails",
                "id": playlist_id,
                "maxResults": 1,
            },
        )

    items = data.get("items", [])
    if not items:
        raise ValueError(f"Playlist not found or private: {playlist_id!r}")

    item = items[0]
    snippet = item["snippet"]
    return {
        "playlist_id": playlist_id,
        "title": snippet.get("title", ""),
        "channel_name": snippet.get("channelTitle", ""),
        "thumbnail_url": _best_thumbnail(snippet.get("thumbnails", {})),
        "total_items": item["contentDetails"]["itemCount"],
    }


async def _fetch_playlist_item_ids(
    client: httpx.AsyncClient, playlist_id: str
) -> list[tuple[str, int]]:
    """
    Collect all (video_id, position) pairs from a playlist, paginating through all pages.
    Returns 1-based positions.
    """
    results: list[tuple[str, int]] = []
    page_token: str | None = None
    position = 1

    while True:
        params: dict = {
            "part": "contentDetails,status",
            "playlistId": playlist_id,
            "maxResults": settings.YOUTUBE_MAX_RESULTS_PER_PAGE,
        }
        if page_token:
            params["pageToken"] = page_token

        data = await _get(client, "playlistItems", params)

        for item in data.get("items", []):
            # Skip private/deleted videos
            status = item.get("status", {}).get("privacyStatus", "public")
            if status in ("private", "privacyStatusUnspecified"):
                position += 1
                continue
            video_id = item["contentDetails"]["videoId"]
            results.append((video_id, position))
            position += 1

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return results


async def _fetch_video_details(
    client: httpx.AsyncClient, video_ids: list[str]
) -> dict[str, dict]:
    """
    Fetch video snippet + contentDetails for up to 50 video IDs at once.
    Returns a dict keyed by video_id.
    """
    # YouTube videos.list accepts up to 50 IDs per request
    BATCH_SIZE = 50
    results: dict[str, dict] = {}

    for i in range(0, len(video_ids), BATCH_SIZE):
        batch = video_ids[i : i + BATCH_SIZE]
        data = await _get(
            client,
            "videos",
            {
                "part": "snippet,contentDetails",
                "id": ",".join(batch),
                "maxResults": BATCH_SIZE,
            },
        )
        for item in data.get("items", []):
            results[item["id"]] = item

    return results


async def fetch_full_playlist(url_or_id: str) -> YouTubePlaylistMeta:
    """
    Main entry point: fetches complete playlist data including all tracks.

    Args:
        url_or_id: YouTube playlist URL or bare playlist ID.

    Returns:
        YouTubePlaylistMeta with all tracks populated.

    Raises:
        ValueError: If URL/ID is invalid or playlist not found.
        YouTubeQuotaError: If API quota is exhausted.
        YouTubeAPIError: For other API failures.
    """
    if not _API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not configured")

    playlist_id = extract_playlist_id(url_or_id)
    logger.info("Fetching YouTube playlist: %s", playlist_id)

    async with httpx.AsyncClient() as client:
        # 1. Playlist metadata
        meta_raw = await fetch_playlist_metadata(playlist_id)

        # 2. All video IDs with positions
        id_position_pairs = await _fetch_playlist_item_ids(client, playlist_id)
        if not id_position_pairs:
            logger.warning("Playlist %s returned 0 playable items", playlist_id)
            return YouTubePlaylistMeta(
                playlist_id=playlist_id,
                title=meta_raw["title"],
                channel_name=meta_raw["channel_name"],
                thumbnail_url=meta_raw["thumbnail_url"],
                total_items=0,
                tracks=[],
            )

        video_ids = [vid for vid, _ in id_position_pairs]
        position_map = {vid: pos for vid, pos in id_position_pairs}

        # 3. Video details in batches
        video_details = await _fetch_video_details(client, video_ids)

    # 4. Build normalised track list
    tracks: list[YouTubeTrack] = []
    for video_id in video_ids:
        detail = video_details.get(video_id)
        if not detail:
            logger.debug("No detail returned for video_id=%s (likely unavailable)", video_id)
            continue

        snippet = detail.get("snippet", {})
        content = detail.get("contentDetails", {})

        duration_ms = _iso_duration_to_ms(content.get("duration", "")) if content.get("duration") else None

        tracks.append(
            YouTubeTrack(
                video_id=video_id,
                title=snippet.get("title", "Unknown Title"),
                channel_name=snippet.get("channelTitle", ""),
                thumbnail_url=_best_thumbnail(snippet.get("thumbnails", {})),
                duration_ms=duration_ms,
                youtube_url=f"https://www.youtube.com/watch?v={video_id}",
                position=position_map[video_id],
            )
        )

    # Sort by original playlist position
    tracks.sort(key=lambda t: t.position)

    logger.info(
        "Playlist %s fetched: %d/%d tracks",
        playlist_id, len(tracks), len(id_position_pairs),
    )

    return YouTubePlaylistMeta(
        playlist_id=playlist_id,
        title=meta_raw["title"],
        channel_name=meta_raw["channel_name"],
        thumbnail_url=meta_raw["thumbnail_url"],
        total_items=len(id_position_pairs),
        tracks=tracks,
    )