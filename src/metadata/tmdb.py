# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""TMDB metadata provider (fallback for anime, primary for live action)."""

import re
from time import sleep
from typing import Any, Dict, List, Optional

import tmdbsimple as tmdb

from ..logger import logger
from ..config.config_manager import cm
from .base import NotFound, MetadataProvider, ProviderUnavailable
from .models import (
    MovieInfo,
    SearchRef,
    SeasonInfo,
    SeriesInfo,
    EpisodeInfo,
)


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (text or "").casefold())


def _parse_year(value: Any) -> int:
    match = re.search(r"(\d{4})", str(value or ""))
    return int(match.group(1)) if match else 0


def _is_anime(genres: List[Dict[str, Any]]) -> bool:
    for genre in genres or []:
        name = str(genre.get("name") or "").lower()
        if name in {"animation", "anime"}:
            return True
    return False


class TMDBProvider(MetadataProvider):
    name = "tmdb"
    language = "zh-CN"

    def __init__(self) -> None:
        self.api_key = cm.get_config("api_key") or ""
        tmdb.API_KEY = self.api_key

    def available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self, query: str, year: int, media_type: str = "tv"
    ) -> List[SearchRef]:
        if not self.available() or not query:
            return []
        results = self._search_raw(query, year, media_type)
        refs: List[SearchRef] = []
        for item in results:
            if media_type == "tv":
                name = str(item.get("name") or "")
                original = str(item.get("original_name") or "")
                date = str(item.get("first_air_date") or "")
            else:
                name = str(item.get("title") or "")
                original = str(item.get("original_title") or "")
                date = str(item.get("release_date") or "")
            refs.append(
                {
                    "provider": "tmdb",
                    "provider_id": int(item.get("id") or 0),
                    "media_type": media_type,  # type: ignore[typeddict-item]
                    "name": name,
                    "name_cn": name,
                    "year": _parse_year(date),
                    "platform": "",
                    "episode_count": 0,
                    "score": self._score(query, name, original, date, year),
                    "raw": item,
                }
            )
        refs.sort(key=lambda ref: ref.get("score", 0.0), reverse=True)
        return refs

    def _search_raw(
        self, query: str, year: int, media_type: str
    ) -> List[Dict[str, Any]]:
        search = tmdb.Search()
        for attempt in range(1, 4):
            try:
                if media_type == "tv":
                    search.tv(
                        query=query,
                        language=self.language,
                        first_air_date_year=year or None,
                    )
                else:
                    search.movie(
                        query=query,
                        language=self.language,
                        year=year or None,
                    )
                return list(search.__dict__.get("results") or [])
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[TMDB] 搜索失败({attempt}/3): {exc}")
                sleep(2)
        raise ProviderUnavailable("TMDB: 搜索请求失败")

    def _score(
        self, query: str, name: str, original: str, date: str, year: int
    ) -> float:
        q = _normalize(query)
        score = 0.0
        if q:
            for candidate in (name, original):
                c = _normalize(candidate)
                if not c:
                    continue
                if c == q:
                    score += 6.0
                elif c.startswith(q) or q.startswith(c):
                    score += 4.0
                elif q in c or c in q:
                    score += 3.0
        release_year = _parse_year(date)
        if year and release_year:
            diff = abs(year - release_year)
            if diff == 0:
                score += 2.5
            elif diff == 1:
                score += 1.0
        return score

    # ------------------------------------------------------------------
    # Series / movie
    # ------------------------------------------------------------------
    def get_title(
        self, provider_id: int, media_type: str = "tv"
    ) -> Optional[Dict[str, Any]]:
        if not self.available():
            return None
        for attempt in range(1, 4):
            try:
                if media_type == "tv":
                    info = tmdb.TV(provider_id).info(language=self.language)
                    return {
                        "name": info.get("name") or "",
                        "original_name": info.get("original_name") or "",
                        "date": info.get("first_air_date") or "",
                        "is_anime": _is_anime(info.get("genres") or []),
                    }
                info = tmdb.Movies(provider_id).info(language=self.language)
                return {
                    "name": info.get("title") or "",
                    "original_name": info.get("original_title") or "",
                    "date": info.get("release_date") or "",
                    "is_anime": _is_anime(info.get("genres") or []),
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[TMDB] 获取标题失败({attempt}/3): {exc}")
                sleep(2)
        return None

    def build_series(self, provider_id: int) -> Optional[SeriesInfo]:
        if not self.available():
            return None
        for attempt in range(1, 4):
            try:
                info = tmdb.TV(provider_id).info(language=self.language)
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[TMDB] 获取剧集失败({attempt}/3): {exc}")
                sleep(2)
        else:
            return None

        seasons: List[SeasonInfo] = []
        for season in info.get("seasons") or []:
            season_number = season.get("season_number")
            if season_number is None:
                continue
            detailed = self._get_season(provider_id, int(season_number))
            episodes: List[EpisodeInfo] = []
            for episode in (detailed or {}).get("episodes") or []:
                episode_number = episode.get("episode_number")
                if episode_number is None:
                    continue
                raw_type = str(episode.get("episode_type") or "standard")
                episode_type = (
                    "special" if raw_type == "special" else "regular"
                )
                episodes.append(
                    {
                        "episode_number": int(episode_number),
                        "sort": float(episode_number),
                        "name": str(episode.get("name") or ""),
                        "name_original": str(episode.get("name") or ""),
                        "air_date": episode.get("air_date"),
                        "runtime": episode.get("runtime"),
                        "episode_type": episode_type,  # type: ignore[typeddict-item]
                        "provider_id": int(episode.get("id") or 0),
                        "source_season": int(season_number),
                    }
                )
            episodes.sort(key=lambda item: item["episode_number"])
            seasons.append(
                {
                    "season_number": int(season_number),
                    "name": str(
                        detailed.get("name")
                        if detailed
                        else season.get("name") or ""
                    ),
                    "aliases": [],
                    "year": _parse_year(
                        (detailed or {}).get("air_date")
                        or season.get("air_date")
                    )
                    or None,
                    "episode_count": len(episodes),
                    "episodes": episodes,
                    "provider_id": int((detailed or {}).get("id") or 0),
                    "platform": "",
                }
            )

        name = str(info.get("name") or "")
        return {
            "provider": "tmdb",
            "provider_id": provider_id,
            "media_type": "tv",
            "name": name,
            "names": {"tmdb": name},
            "name_original": str(info.get("original_name") or ""),
            "name_cn": name,
            "aliases": [
                str(info.get("name") or ""),
                str(info.get("original_name") or ""),
            ],
            "year": _parse_year(info.get("first_air_date")),
            "first_air_date": str(info.get("first_air_date") or ""),
            "is_anime": _is_anime(info.get("genres") or []),
            "seasons": seasons,
            "movies": [],
        }

    def build_movie(self, provider_id: int) -> Optional[MovieInfo]:
        if not self.available():
            return None
        for attempt in range(1, 4):
            try:
                info = tmdb.Movies(provider_id).info(language=self.language)
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[TMDB] 获取电影失败({attempt}/3): {exc}")
                sleep(2)
        else:
            return None

        name = str(info.get("title") or "")
        return {
            "provider": "tmdb",
            "provider_id": provider_id,
            "media_type": "movie",
            "name": name,
            "names": {"tmdb": name},
            "name_original": str(info.get("original_title") or ""),
            "name_cn": name,
            "year": _parse_year(info.get("release_date")),
            "release_date": str(info.get("release_date") or ""),
            "runtime": info.get("runtime"),
            "is_anime": _is_anime(info.get("genres") or []),
            "overview": str(info.get("overview") or ""),
        }

    def _get_season(
        self, provider_id: int, season_number: int
    ) -> Optional[Dict[str, Any]]:
        for attempt in range(1, 4):
            try:
                season = tmdb.TV_Seasons(provider_id, season_number)
                return season.info(language=self.language)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[TMDB] 获取季度失败({attempt}/3): {exc}")
                sleep(2)
        return None
