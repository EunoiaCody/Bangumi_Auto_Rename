# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Jellyfin-first naming helpers.

Metadata is used only to decide the directory layout and file names.  This
module never writes NFO files or downloads artwork.
"""

import re
from pathlib import Path
from typing import Optional

from ..metadata.models import MovieInfo, SeriesInfo, EpisodeInfo

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")


def sanitize_component(value: str, *, max_bytes: int = 200) -> str:
    value = INVALID_CHARS.sub(" ", value or "")
    value = WHITESPACE.sub(" ", value).strip(" .")
    if not value:
        return "Unknown"
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    encoded = encoded[:max_bytes]
    while encoded:
        try:
            return encoded.decode("utf-8").rstrip(" .")
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return "Unknown"


def _year(year: Optional[int]) -> str:
    return f" ({year})" if year and int(year) > 0 else ""


def series_folder(
    name: str, year: Optional[int], *, style: str = "jellyfin"
) -> str:
    if style == "legacy":
        return sanitize_component(f"{name}{_year(year)}")
    return sanitize_component(f"{name}{_year(year)}")


def season_folder(number: int, *, style: str = "jellyfin") -> str:
    if style == "legacy":
        return f"Season{int(number)}"
    return f"Season {int(number):02d}"


def _ext(ext: str) -> str:
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def episode_filename(
    series_name: str,
    year: Optional[int],
    season: int,
    episode: int,
    title: str = "",
    ext: str = ".mkv",
    *,
    style: str = "jellyfin",
    original_name: str = "",
    part: Optional[int] = None,
) -> str:
    ext = _ext(ext)
    tag = f"S{int(season):02d}E{int(episode):02d}"
    part_tag = f" - part{part}" if part else ""

    if style == "legacy":
        tail = str(Path(original_name).stem) if original_name else title
        suffix = (
            f" - {sanitize_component(tail, max_bytes=120)}" if tail else ""
        )
        return f"{tag}{suffix}{part_tag}{ext}"

    base = f"{sanitize_component(series_name)}{_year(year)} {tag}"
    if title:
        base += f" - {sanitize_component(title, max_bytes=120)}"
    return f"{base}{part_tag}{ext}"


def movie_folder(
    name: str, year: Optional[int], *, style: str = "jellyfin"
) -> str:
    return sanitize_component(f"{name}{_year(year)}")


def movie_filename(
    name: str,
    year: Optional[int],
    ext: str = ".mkv",
    *,
    style: str = "jellyfin",
    original_name: str = "",
    part: Optional[int] = None,
    part_type: str = "part",
) -> str:
    ext = _ext(ext)
    if style == "legacy":
        base = sanitize_component(name)
        suffix = (
            f" - {sanitize_component(original_name)}" if original_name else ""
        )
        return f"{base}{suffix}{ext}"
    base = f"{sanitize_component(name)}{_year(year)}"
    if part:
        base += f" - {part_type}{part}"
    return f"{base}{ext}"


def extra_filename(original_name: str) -> str:
    return sanitize_component(original_name)


def episode_title(
    series: SeriesInfo,
    season: int,
    episode: int,
    language: str = "zh",
) -> str:
    if language == "none":
        return ""
    for season_info in series.get("seasons", []):
        if int(season_info.get("season_number", -1)) != int(season):
            continue
        for item in season_info.get("episodes", []):
            if int(item.get("episode_number", -1)) != int(episode):
                continue
            return _select_title(item, language)
    return ""


def _select_title(episode: EpisodeInfo, language: str) -> str:
    if language == "ja":
        return str(episode.get("name_original") or episode.get("name") or "")
    return str(episode.get("name") or episode.get("name_original") or "")


def media_year(info: dict) -> int:
    year = info.get("year")
    if year:
        return int(year)
    for key in ("first_air_date", "release_date", "air_date"):
        match = re.search(r"(\d{4})", str(info.get(key) or ""))
        if match:
            return int(match.group(1))
    return 0


def series_name(series: SeriesInfo) -> str:
    return str(series.get("name") or series.get("name_cn") or "Unknown")


def movie_name(movie: MovieInfo) -> str:
    return str(movie.get("name") or movie.get("name_cn") or "Unknown")


def natural_key(path: Path):
    """Sort helper for CD1/CD2 and episode-like file names."""
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]
