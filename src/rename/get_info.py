# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Compatibility facade for the legacy ``Search`` API.

The actual work is delegated to :class:`src.metadata.resolver.MetadataResolver`.
Existing callers keep using ``get_tv_info`` / ``get_movie_info`` /
``fill_season_info``.
"""

from typing import Any, Dict, List, Tuple, Optional

from ..metadata.resolver import MetadataResolver


class Search:
    def __init__(self) -> None:
        self.resolver = MetadataResolver()

    @property
    def TMDB_KEY(self) -> str:
        return self.resolver.tmdb.api_key

    def available_providers(self) -> List[str]:
        return self.resolver.available_providers()

    def has_required_config(self) -> bool:
        return self.resolver.has_required_config()

    def get_tv_info(
        self,
        query: str,
        year: int,
        is_anime_hint: Optional[bool] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        info = self.resolver.search_tv(query, year, is_anime_hint)
        if not info:
            return "", None
        return str(info.get("name") or ""), info

    def get_movie_info(
        self,
        query: str,
        year: int,
        is_anime_hint: Optional[bool] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        info = self.resolver.search_movie(query, year, is_anime_hint)
        if not info:
            return "", None
        return str(info.get("name") or ""), info

    def get_tv_info_with_seasons(
        self,
        query: str,
        year: int,
        is_anime_hint: Optional[bool] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        return self.get_tv_info(query, year, is_anime_hint)

    def fill_season_info(self, tv_info: Dict[str, Any]) -> Dict[str, Any]:
        return self.resolver.fill_season_info(tv_info)

    def get_series_by_id(
        self, provider_id: int, provider: str = "bangumi"
    ) -> Optional[Dict[str, Any]]:
        return self.resolver.get_series_by_id(provider_id, provider)
