# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Provider-neutral metadata models.

The rest of the application consumes these dictionaries.  Both the Bangumi
and TMDB providers normalize their responses into this shape, so the rename
pipeline and the AI prompts no longer depend on TMDB-specific fields.
"""

from typing import Dict, List, Literal, Optional, TypedDict

Provider = Literal["bangumi", "tmdb"]
MediaType = Literal["tv", "movie"]
EpisodeType = Literal["regular", "special", "extra"]


class EpisodeInfo(TypedDict, total=False):
    episode_number: int
    sort: float
    name: str
    name_original: str
    air_date: Optional[str]
    runtime: Optional[int]
    episode_type: EpisodeType
    provider_id: int
    source_season: int


class SeasonInfo(TypedDict, total=False):
    season_number: int
    name: str
    aliases: List[str]
    year: Optional[int]
    episode_count: int
    episodes: List[EpisodeInfo]
    provider_id: int
    platform: str


class SeriesInfo(TypedDict, total=False):
    provider: Provider
    provider_id: int
    media_type: MediaType
    name: str
    names: Dict[str, str]
    name_original: str
    name_cn: str
    aliases: List[str]
    year: int
    first_air_date: str
    is_anime: bool
    seasons: List[SeasonInfo]
    movies: List[Dict]


class MovieInfo(TypedDict, total=False):
    provider: Provider
    provider_id: int
    media_type: MediaType
    name: str
    names: Dict[str, str]
    name_original: str
    name_cn: str
    year: int
    release_date: str
    runtime: Optional[int]
    is_anime: bool
    overview: str


class SearchRef(TypedDict, total=False):
    provider: Provider
    provider_id: int
    media_type: MediaType
    name: str
    name_cn: str
    year: int
    platform: str
    episode_count: int
    score: float
    raw: Dict
