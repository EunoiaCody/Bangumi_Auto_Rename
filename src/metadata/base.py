# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Provider abstractions and resilient HTTP helpers."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests

from ..logger import logger
from .cache import JsonCache
from .models import Provider, MediaType, MovieInfo, SearchRef, SeriesInfo


class MetadataError(RuntimeError):
    """Base class for metadata provider errors."""


class ProviderUnavailable(MetadataError):
    """The provider could not be reached or returned an invalid response."""


class NotFound(MetadataError):
    """The requested metadata entry does not exist."""


class MetadataProvider(ABC):
    name: Provider

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(
        self, query: str, year: int, media_type: MediaType
    ) -> List[SearchRef]:
        raise NotImplementedError

    @abstractmethod
    def build_series(self, provider_id: int) -> Optional[SeriesInfo]:
        raise NotImplementedError

    @abstractmethod
    def build_movie(self, provider_id: int) -> Optional[MovieInfo]:
        raise NotImplementedError


class BaseHttpProvider(MetadataProvider, ABC):
    """JSON HTTP provider with throttling, retries and a disk cache."""

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        token: str = "",
        min_interval: float = 1.0,
        timeout: float = 15.0,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.token = token
        self.min_interval = max(0.0, min_interval)
        self.timeout = timeout
        self.retries = max(1, retries)
        self.cache = JsonCache(self.name)
        self.session = requests.Session()
        self._last_request = 0.0

    def _headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.monotonic()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        cache_ttl: Optional[int] = None,
        use_cache: bool = True,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        cache_key = (
            f"{method}:{url}:{sorted((params or {}).items())}:"
            f"{json_body or {}}"
        )
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    f"[{self.name}] 请求失败({attempt}/{self.retries}): {exc}"
                )
                time.sleep(min(2**attempt, 10))
                continue

            if response.status_code == 404:
                raise NotFound(f"{self.name}: {url} 不存在")
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After", "")
                wait = min(2**attempt, 15)
                try:
                    wait = max(wait, float(retry_after))
                except (TypeError, ValueError):
                    pass
                last_error = ProviderUnavailable(
                    f"{self.name}: HTTP {response.status_code}"
                )
                logger.warning(
                    f"[{self.name}] HTTP {response.status_code}，"
                    f"{wait:.0f}s 后重试({attempt}/{self.retries})"
                )
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                raise ProviderUnavailable(
                    f"{self.name}: HTTP {response.status_code} {response.text[:200]}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderUnavailable(
                    f"{self.name}: 响应不是合法 JSON"
                ) from exc

            if use_cache:
                self.cache.set(
                    cache_key,
                    data,
                    ttl=cache_ttl,
                )
            return data

        raise ProviderUnavailable(
            f"{self.name}: 请求失败，已重试 {self.retries} 次"
        ) from last_error
