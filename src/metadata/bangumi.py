# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Bangumi (bgm.tv) metadata provider."""

import re
from datetime import date
from urllib.parse import quote
from typing import Any, Dict, List, Iterable, Optional

from ..logger import logger
from ..config.config_manager import cm
from ..__version__ import __url__, __version__
from .base import NotFound, BaseHttpProvider, ProviderUnavailable
from .models import (
    MovieInfo,
    SearchRef,
    SeasonInfo,
    SeriesInfo,
    EpisodeInfo,
)

DEFAULT_BASE_URL = "https://api.bgm.tv"
DEFAULT_UA = f"Bangumi_Auto_Rename/{__version__} (+{__url__})"
MAIN_TYPE = 0
SPECIAL_TYPE = 1
EXTRA_TYPES = {2, 3, 4, 5, 6}


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (text or "").casefold())


def _parse_year(value: Any) -> int:
    match = re.search(r"(\d{4})", str(value or ""))
    return int(match.group(1)) if match else 0


def _parse_duration_seconds(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d+)\s*[:：]\s*(\d+)", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.search(r"(\d+)\s*(?:m|min|分钟)", text, re.I)
    if match:
        return int(match.group(1)) * 60
    match = re.search(r"(\d+)\s*(?:s|sec|秒)", text, re.I)
    if match:
        return int(match.group(1))
    return None


class BangumiProvider(BaseHttpProvider):
    name = "bangumi"

    def __init__(self) -> None:
        base_url = cm.get_config("bangumi_base_url") or DEFAULT_BASE_URL
        token = cm.get_config("bangumi_access_token") or ""
        user_agent = cm.get_config("bangumi_user_agent") or DEFAULT_UA
        super().__init__(
            base_url=base_url,
            user_agent=user_agent,
            token=token,
            min_interval=1.0,
            timeout=15.0,
            retries=3,
        )

    def available(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self, query: str, year: int, media_type: str = "tv"
    ) -> List[SearchRef]:
        query = (query or "").strip()
        if not query:
            return []
        self.set_query(query, year)

        raw_items: List[Dict[str, Any]] = []
        try:
            data = self._request(
                "POST",
                "/v0/search/subjects",
                params={"limit": 15},
                json_body={
                    "keyword": query,
                    "sort": "match",
                    "filter": {"type": [2]},
                },
                cache_ttl=24 * 3600,
            )
            raw_items = list(data.get("data") or [])
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[Bangumi] v0 搜索失败，尝试旧接口: {exc}")

        if not raw_items:
            try:
                legacy = self._request(
                    "GET",
                    f"/search/subject/{quote(query, safe='')}",
                    params={"type": 2, "responseGroup": "large"},
                    cache_ttl=24 * 3600,
                )
                raw_items = list(legacy.get("list") or [])
            except (ProviderUnavailable, NotFound) as exc:
                logger.warning(f"[Bangumi] 旧搜索接口也失败: {exc}")
                return []

        refs = [
            self._to_ref(item, media_type)
            for item in raw_items
            if item and not item.get("nsfw")
        ]
        refs = [ref for ref in refs if ref is not None]
        self._franchise_bonus(refs)
        for index, ref in enumerate(refs):
            ref["score"] = ref.get("score", 0.0) + max(
                0.0, 0.3 * (1 - index / max(len(refs), 1))
            )
        refs.sort(
            key=lambda ref: (ref.get("score", 0.0), -ref.get("year", 0)),
            reverse=True,
        )

        if refs:
            logger.debug(
                "[Bangumi] 搜索候选: "
                + " | ".join(
                    f"{r['name']}({r.get('year', 0)}) "
                    f"{r.get('score', 0):.1f}"
                    for r in refs[:3]
                )
            )
        return refs  # type: ignore[return-value]

    def _to_ref(
        self, item: Dict[str, Any], media_type: str
    ) -> Optional[SearchRef]:
        subject_id = item.get("id")
        if not subject_id:
            return None
        name = str(item.get("name") or "")
        name_cn = str(item.get("name_cn") or "")
        year = _parse_year(item.get("date") or item.get("air_date"))
        platform = str(item.get("platform") or "")
        episode_count = item.get("eps") or item.get("eps_count")
        try:
            episode_count = int(episode_count or 0)
        except (TypeError, ValueError):
            episode_count = 0

        is_movie = "剧场版" in platform or "电影" in platform
        if media_type == "movie" and not is_movie and episode_count > 1:
            return None
        if media_type == "tv" and is_movie:
            return None

        score = self._score(
            item,
            name=name,
            name_cn=name_cn,
            year=year,
            platform=platform,
            media_type=media_type,
        )
        return {
            "provider": "bangumi",
            "provider_id": int(subject_id),
            "media_type": media_type,  # type: ignore[typeddict-item]
            "name": name,
            "name_cn": name_cn,
            "year": year,
            "platform": platform,
            "episode_count": episode_count,
            "score": score,
            "raw": item,
        }

    @staticmethod
    def _franchise_bonus(refs: List[SearchRef]) -> None:
        names = []
        for ref in refs:
            names.append(
                {
                    _normalize(str(ref.get("name") or "")),
                    _normalize(str(ref.get("name_cn") or "")),
                }
            )
        for index, ref in enumerate(refs):
            own = {name for name in names[index] if len(name) >= 2}
            for other_index, other_names in enumerate(names):
                if other_index == index:
                    continue
                for own_name in own:
                    if any(
                        other.startswith(own_name) and other != own_name
                        for other in other_names
                        if len(other) > len(own_name)
                    ):
                        ref["score"] = ref.get("score", 0.0) + 0.8
                        break
                else:
                    continue
                break

    def _score(
        self,
        item: Dict[str, Any],
        *,
        name: str,
        name_cn: str,
        year: int,
        platform: str,
        media_type: str,
    ) -> float:
        query = self._query or ""
        q = _normalize(query)
        score = 0.0
        if q:
            for candidate in (name, name_cn):
                c = _normalize(candidate)
                if not c:
                    continue
                if c == q:
                    score += 6.0
                elif c.startswith(q) or q.startswith(c):
                    score += 4.0
                elif q in c or c in q:
                    score += 3.0
            if re.search(r"[\u4e00-\u9fff]", query) and _normalize(name_cn):
                score += 0.5

        if year and self._query_year:
            diff = abs(year - self._query_year)
            if diff == 0:
                score += 2.5
            elif diff == 1:
                score += 1.0

        if media_type == "movie" and "剧场版" in platform:
            score += 2.0
        if media_type == "tv" and platform in {"TV", "Web", "OVA"}:
            score += 1.0

        rating = item.get("rating") or {}
        try:
            score += min(float(rating.get("score") or 0) / 20.0, 0.5)
        except (TypeError, ValueError):
            pass
        return score

    def set_query(self, query: str, year: int) -> None:
        self._query = query
        self._query_year = year

    # ------------------------------------------------------------------
    # Subject / relations / episodes
    # ------------------------------------------------------------------
    def get_subject(self, subject_id: int) -> Dict[str, Any]:
        data = self._request(
            "GET",
            f"/v0/subjects/{subject_id}",
            cache_ttl=7 * 24 * 3600,
        )
        if not isinstance(data, dict):
            raise ProviderUnavailable("Bangumi: 条目响应格式错误")
        return data

    def get_relations(self, subject_id: int) -> List[Dict[str, Any]]:
        data = self._request(
            "GET",
            f"/v0/subjects/{subject_id}/subjects",
            cache_ttl=7 * 24 * 3600,
        )
        return list(data or [])

    def get_episodes(self, subject_id: int) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        offset = 0
        limit = 100
        while True:
            data = self._request(
                "GET",
                "/v0/episodes",
                params={
                    "subject_id": subject_id,
                    "limit": limit,
                    "offset": offset,
                },
                cache_ttl=7 * 24 * 3600,
            )
            items = list(data.get("data") or [])
            result.extend(items)
            total = int(data.get("total") or 0)
            offset += len(items)
            if not items or offset >= total:
                break
        return result

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------
    def build_series(self, provider_id: int) -> Optional[SeriesInfo]:
        try:
            subject = self.get_subject(provider_id)
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[Bangumi] 获取条目失败 {provider_id}: {exc}")
            return None

        chain = self._season_chain(subject)
        if not chain:
            return None

        seasons: List[SeasonInfo] = []
        specials: List[EpisodeInfo] = []
        movies: List[Dict[str, Any]] = []

        for index, node in enumerate(chain, start=1):
            node_id = int(node.get("id") or 0)
            name = str(node.get("name_cn") or node.get("name") or "")
            aliases = self._aliases(node)
            year = _parse_year(node.get("date"))
            episodes_raw = self.get_episodes(node_id)

            regular: List[EpisodeInfo] = []
            used_numbers: set[int] = set()
            next_number = 1
            for raw in episodes_raw:
                ep_type = int(raw.get("type") or 0)
                if ep_type != MAIN_TYPE:
                    continue
                number, fractional = self._episode_number(raw)
                if number is None:
                    continue
                if fractional:
                    specials.append(
                        self._episode_info(
                            raw,
                            episode_number=0,
                            episode_type="special",
                            source_season=index,
                        )
                    )
                    continue
                if number in used_numbers:
                    while next_number in used_numbers:
                        next_number += 1
                    number = next_number
                used_numbers.add(number)
                regular.append(
                    self._episode_info(
                        raw,
                        episode_number=number,
                        episode_type="regular",
                        source_season=index,
                    )
                )

            regular.sort(key=lambda item: item["episode_number"])
            seasons.append(
                {
                    "season_number": index,
                    "name": name,
                    "aliases": aliases,
                    "year": year or None,
                    "episode_count": len(regular),
                    "episodes": regular,
                    "provider_id": node_id,
                    "platform": str(node.get("platform") or ""),
                }
            )

            for raw in episodes_raw:
                ep_type = int(raw.get("type") or 0)
                if ep_type == SPECIAL_TYPE:
                    specials.append(
                        self._episode_info(
                            raw,
                            episode_number=0,
                            episode_type="special",
                            source_season=index,
                        )
                    )

        # Related movies are exposed for logging / future use, but not mapped.
        for relation in self.get_relations(provider_id):
            if "剧场版" in str(relation.get("platform") or ""):
                movies.append(
                    {
                        "provider": "bangumi",
                        "provider_id": relation.get("id"),
                        "name": relation.get("name_cn")
                        or relation.get("name"),
                        "year": _parse_year(relation.get("date")),
                    }
                )

        specials.sort(
            key=lambda item: (
                item.get("source_season", 0),
                item.get("sort", 0.0),
            )
        )
        for index, special in enumerate(specials, start=1):
            special["episode_number"] = index
        if specials:
            seasons.insert(
                0,
                {
                    "season_number": 0,
                    "name": "Specials",
                    "aliases": ["sp", "special", "ova", "oad", "特典"],
                    "year": None,
                    "episode_count": len(specials),
                    "episodes": specials,
                    "provider_id": 0,
                    "platform": "Special",
                },
            )

        seasons = [
            season
            for season in seasons
            if int(season.get("episode_count") or 0) > 0
            or int(season.get("season_number") or 0) == 0
        ]

        root = chain[0]
        display_name = str(root.get("name_cn") or root.get("name") or "")
        names = {"bangumi": display_name}
        first_air_date = str(root.get("date") or "")
        year = _parse_year(first_air_date)

        return {
            "provider": "bangumi",
            "provider_id": provider_id,
            "media_type": "tv",
            "name": display_name,
            "names": names,
            "name_original": str(root.get("name") or ""),
            "name_cn": str(root.get("name_cn") or ""),
            "aliases": self._aliases(root),
            "year": year,
            "first_air_date": first_air_date,
            "is_anime": True,
            "seasons": seasons,
            "movies": movies,
        }

    def build_movie(self, provider_id: int) -> Optional[MovieInfo]:
        try:
            subject = self.get_subject(provider_id)
        except (ProviderUnavailable, NotFound) as exc:
            logger.warning(f"[Bangumi] 获取电影条目失败 {provider_id}: {exc}")
            return None

        name = str(subject.get("name_cn") or subject.get("name") or "")
        year = _parse_year(subject.get("date"))
        runtime = None
        try:
            episodes = self.get_episodes(provider_id)
            for episode in episodes:
                if int(episode.get("type") or 0) == MAIN_TYPE:
                    seconds = _parse_duration_seconds(
                        episode.get("duration_seconds")
                        or episode.get("duration")
                    )
                    if seconds:
                        runtime = max(1, round(seconds / 60))
                        break
        except (ProviderUnavailable, NotFound):
            pass

        return {
            "provider": "bangumi",
            "provider_id": provider_id,
            "media_type": "movie",
            "name": name,
            "names": {"bangumi": name},
            "name_original": str(subject.get("name") or ""),
            "name_cn": str(subject.get("name_cn") or ""),
            "year": year,
            "release_date": str(subject.get("date") or ""),
            "runtime": runtime,
            "is_anime": True,
            "overview": str(subject.get("summary") or ""),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _episode_number(
        self, raw: Dict[str, Any]
    ) -> tuple[Optional[int], bool]:
        ep = raw.get("ep")
        sort = raw.get("sort")
        value: Optional[float] = None
        if isinstance(ep, (int, float)):
            value = float(ep)
        elif isinstance(sort, (int, float)):
            value = float(sort)
        if value is None:
            return None, False
        if abs(value - round(value)) > 0.01:
            return None, True
        return int(round(value)), False

    def _episode_info(
        self,
        raw: Dict[str, Any],
        *,
        episode_number: int,
        episode_type: str,
        source_season: int,
    ) -> EpisodeInfo:
        seconds = _parse_duration_seconds(
            raw.get("duration_seconds") or raw.get("duration")
        )
        return {
            "episode_number": episode_number,
            "sort": float(raw.get("sort") or 0.0),
            "name": str(raw.get("name_cn") or raw.get("name") or ""),
            "name_original": str(raw.get("name") or ""),
            "air_date": str(raw.get("airdate") or "") or None,
            "runtime": max(1, round(seconds / 60)) if seconds else None,
            "episode_type": episode_type,  # type: ignore[typeddict-item]
            "provider_id": int(raw.get("id") or 0),
            "source_season": source_season,
        }

    def _aliases(self, subject: Dict[str, Any]) -> List[str]:
        aliases: List[str] = []
        for key in ("name", "name_cn"):
            value = str(subject.get(key) or "")
            if value:
                aliases.append(value)
        for item in subject.get("infobox") or []:
            if not isinstance(item, dict):
                continue
            if item.get("key") not in {"别名", "别名（中文）", "英文名"}:
                continue
            value = item.get("value")
            if isinstance(value, str):
                aliases.append(value)
            elif isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        aliases.append(str(entry.get("v") or ""))
                    else:
                        aliases.append(str(entry))
        return sorted({alias for alias in aliases if alias})

    def _season_chain(self, subject: Dict[str, Any]) -> List[Dict[str, Any]]:
        subject_id = int(subject.get("id") or 0)
        if not subject_id:
            return []
        visited = {subject_id}
        chain = [subject]

        # Walk backwards through 前传.
        current = subject
        for _ in range(20):
            previous = self._related_subject(current, "前传")
            if not previous:
                break
            previous_id = int(previous.get("id") or 0)
            if not previous_id or previous_id in visited:
                break
            visited.add(previous_id)
            chain.insert(0, previous)
            current = previous

        # Walk forwards through 续集 from the root.
        current = chain[0]
        for _ in range(20):
            following = self._related_subject(current, "续集")
            if not following:
                break
            following_id = int(following.get("id") or 0)
            if not following_id or following_id in visited:
                break
            visited.add(following_id)
            chain.append(following)
            current = following

        # Drop movies from the season chain.
        return [
            node
            for node in chain
            if "剧场版" not in str(node.get("platform") or "")
        ] or [subject]

    def _related_subject(
        self, subject: Dict[str, Any], relation: str
    ) -> Optional[Dict[str, Any]]:
        subject_id = int(subject.get("id") or 0)
        if not subject_id:
            return None
        try:
            relations = self.get_relations(subject_id)
        except (ProviderUnavailable, NotFound):
            return None
        candidates = [
            item
            for item in relations
            if item.get("relation") == relation
            and int(item.get("type") or 0) == 2
            and "剧场版" not in str(item.get("platform") or "")
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                str(item.get("date") or ""),
                int(item.get("eps") or 0),
            )
        )
        chosen = candidates[0]
        chosen_id = int(chosen.get("id") or 0)
        if not chosen_id:
            return None
        try:
            return self.get_subject(chosen_id)
        except (ProviderUnavailable, NotFound):
            return chosen

    def _query_state(self) -> None:
        # Query/year are only used for scoring; keep them per-call via
        # set_query() and reset defensively.
        if not hasattr(self, "_query"):
            self._query = ""
        if not hasattr(self, "_query_year"):
            self._query_year = 0
