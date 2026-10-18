# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Metadata provider selection, fallback and title-source policy."""

from typing import Dict, List, Tuple, Optional

from ..logger import logger
from .tmdb import TMDBProvider
from .bangumi import BangumiProvider
from ..config.config_manager import cm
from .base import NotFound, ProviderUnavailable
from .models import MovieInfo, SearchRef, SeriesInfo


class MetadataResolver:
    def __init__(self) -> None:
        self.bangumi = BangumiProvider()
        self.tmdb = TMDBProvider()
        self.metadata_source = cm.get_config("metadata_source") or "bangumi"
        self.title_source = cm.get_config("naming_title_source") or "auto"

    def available_providers(self) -> List[str]:
        providers = []
        if self.bangumi.available():
            providers.append("bangumi")
        if self.tmdb.available():
            providers.append("tmdb")
        return providers

    def has_required_config(self) -> bool:
        if self.metadata_source == "bangumi":
            return self.bangumi.available()
        return self.tmdb.available()

    # ------------------------------------------------------------------
    # TV
    # ------------------------------------------------------------------
    def search_tv(
        self,
        query: str,
        year: int,
        is_anime_hint: Optional[bool] = None,
    ) -> Optional[SeriesInfo]:
        if self.metadata_source == "bangumi" and is_anime_hint is not False:
            series = self._search_bangumi_tv(query, year, is_anime_hint)
            if series:
                return self._decorate_bangumi_titles(series)

        series = self._search_tmdb_tv(query, year)
        if series and is_anime_hint is True:
            series["is_anime"] = True
        return series

    def _search_bangumi_tv(
        self, query: str, year: int, is_anime_hint: Optional[bool]
    ) -> Optional[SeriesInfo]:
        try:
            refs = self.bangumi.search(query, year, "tv")
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[元数据] Bangumi 搜索失败: {exc}")
            return None
        ref = self._pick(refs, min_score=2.0)
        if not ref:
            return None
        try:
            series = self.bangumi.build_series(int(ref["provider_id"]))
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[元数据] Bangumi 条目解析失败: {exc}")
            return None
        if series:
            logger.info(
                f"[元数据] Bangumi 命中: {series['name']} "
                f"({series.get('year', 0)})"
            )
        return series

    def _search_tmdb_tv(self, query: str, year: int) -> Optional[SeriesInfo]:
        if not self.tmdb.available():
            return None
        try:
            refs = self.tmdb.search(query, year, "tv")
        except ProviderUnavailable as exc:
            logger.warning(f"[元数据] TMDB 搜索失败: {exc}")
            return None
        ref = self._pick(refs, min_score=2.5)
        if not ref:
            return None
        series = self.tmdb.build_series(int(ref["provider_id"]))
        if series:
            logger.info(
                f"[元数据] TMDB 命中: {series['name']} "
                f"({series.get('year', 0)})"
            )
        return series

    # ------------------------------------------------------------------
    # Movie
    # ------------------------------------------------------------------
    def search_movie(
        self,
        query: str,
        year: int,
        is_anime_hint: Optional[bool] = None,
    ) -> Optional[MovieInfo]:
        if self.metadata_source == "bangumi" and is_anime_hint is True:
            movie = self._search_bangumi_movie(query, year, is_anime_hint)
            if movie:
                return self._decorate_bangumi_movie(movie)

        movie = self._search_tmdb_movie(query, year)
        if movie:
            if is_anime_hint is True:
                movie["is_anime"] = True
            return movie

        # Anime movies without an explicit tag: try Bangumi as a last resort.
        if self.metadata_source == "bangumi" and is_anime_hint is not False:
            movie = self._search_bangumi_movie(query, year, is_anime_hint)
            if movie:
                return self._decorate_bangumi_movie(movie)
        return None

    def _search_bangumi_movie(
        self, query: str, year: int, is_anime_hint: Optional[bool]
    ) -> Optional[MovieInfo]:
        try:
            refs = self.bangumi.search(query, year, "movie")
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[元数据] Bangumi 电影搜索失败: {exc}")
            return None
        ref = self._pick(refs, min_score=2.0)
        if not ref:
            return None
        try:
            movie = self.bangumi.build_movie(int(ref["provider_id"]))
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[元数据] Bangumi 电影解析失败: {exc}")
            return None
        if movie:
            logger.info(
                f"[元数据] Bangumi 电影命中: {movie['name']} "
                f"({movie.get('year', 0)})"
            )
        return movie

    def _search_tmdb_movie(self, query: str, year: int) -> Optional[MovieInfo]:
        if not self.tmdb.available():
            return None
        try:
            refs = self.tmdb.search(query, year, "movie")
        except ProviderUnavailable as exc:
            logger.warning(f"[元数据] TMDB 电影搜索失败: {exc}")
            return None
        ref = self._pick(refs, min_score=2.5)
        if not ref:
            return None
        movie = self.tmdb.build_movie(int(ref["provider_id"]))
        if movie:
            logger.info(
                f"[元数据] TMDB 电影命中: {movie['name']} "
                f"({movie.get('year', 0)})"
            )
        return movie

    # ------------------------------------------------------------------
    # Classification and compatibility
    # ------------------------------------------------------------------
    def classify(
        self, query: str, year: int
    ) -> Tuple[Optional[SeriesInfo], Optional[MovieInfo]]:
        return (
            self.search_tv(query, year, None),
            self.search_movie(query, year, None),
        )

    def fill_season_info(self, info: Dict) -> Dict:
        # Both providers already return fully populated seasons.
        return info

    def get_series_by_id(
        self, provider_id: int, provider: str
    ) -> Optional[SeriesInfo]:
        if provider == "bangumi":
            series = self.bangumi.build_series(provider_id)
            return self._decorate_bangumi_titles(series) if series else None
        return self.tmdb.build_series(provider_id)

    # ------------------------------------------------------------------
    # Title source policy
    # ------------------------------------------------------------------
    def _decorate_bangumi_titles(self, series: SeriesInfo) -> SeriesInfo:
        bangumi_name = (
            series["names"].get("bangumi") or series.get("name") or ""
        )
        series["names"].setdefault("bangumi", bangumi_name)
        if (
            self.title_source != "bangumi"
            and self.tmdb.available()
            and bangumi_name
        ):
            title = self._lookup_tmdb_title(
                [bangumi_name, series.get("name_cn", "")],
                series.get("year", 0),
                "tv",
                series.get("media_type", "tv"),
            )
            if title:
                series["names"]["tmdb"] = title["name"]
                if title.get("year"):
                    series["year"] = title["year"]
        series["name"] = self._choose_name(series)
        return series

    def _decorate_bangumi_movie(self, movie: MovieInfo) -> MovieInfo:
        bangumi_name = movie["names"].get("bangumi") or movie.get("name") or ""
        movie["names"].setdefault("bangumi", bangumi_name)
        if (
            self.title_source != "bangumi"
            and self.tmdb.available()
            and bangumi_name
        ):
            title = self._lookup_tmdb_title(
                [bangumi_name, movie.get("name_cn", "")],
                movie.get("year", 0),
                "movie",
                "movie",
            )
            if title:
                movie["names"]["tmdb"] = title["name"]
                if title.get("year"):
                    movie["year"] = title["year"]
        movie["name"] = self._choose_name(movie)
        return movie

    def _choose_name(self, info: Dict) -> str:
        names = info.get("names") or {}
        if self.title_source == "bangumi":
            return (
                names.get("bangumi")
                or names.get("tmdb")
                or info.get("name", "")
            )
        if self.title_source == "tmdb":
            return (
                names.get("tmdb")
                or names.get("bangumi")
                or info.get("name", "")
            )
        return (
            names.get("tmdb") or names.get("bangumi") or info.get("name", "")
        )

    def _lookup_tmdb_title(
        self,
        candidates: List[str],
        year: int,
        media_type: str,
        provider_media_type: str,
    ) -> Optional[Dict]:
        seen = set()
        for candidate in candidates:
            candidate = (candidate or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                refs = self.tmdb.search(candidate, year, media_type)
            except ProviderUnavailable:
                continue
            ref = self._pick(refs, min_score=3.0)
            if not ref:
                continue
            title = self.tmdb.get_title(
                int(ref["provider_id"]), provider_media_type
            )
            if title:
                return title
        return None

    @staticmethod
    def _pick(
        refs: List[SearchRef], *, min_score: float
    ) -> Optional[SearchRef]:
        for ref in refs:
            if ref.get("score", 0.0) >= min_score:
                return ref
        return None
