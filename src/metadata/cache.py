# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Small JSON disk cache used by metadata providers."""

import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Any, Optional

from ..logger import logger
from ..utils.path import CACHE_PATH


class JsonCache:
    def __init__(
        self,
        namespace: str,
        *,
        default_ttl: int = 7 * 24 * 3600,
        directory: Optional[Path] = None,
    ) -> None:
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.directory = (directory or CACHE_PATH) / namespace
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with self._lock:
                payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("expires_at", 0) < time.time():
                path.unlink(missing_ok=True)
                return None
            return payload.get("value")
        except (OSError, ValueError) as exc:
            logger.warning(f"[缓存] 读取失败 {path.name}: {exc}")
            return None

    def set(self, key: str, value: Any, *, ttl: Optional[int] = None) -> None:
        path = self._path(key)
        payload = {
            "expires_at": time.time() + (ttl or self.default_ttl),
            "value": value,
        }
        try:
            with self._lock:
                path.write_text(
                    json.dumps(payload, ensure_ascii=False),
                    encoding="utf-8",
                )
        except (OSError, TypeError) as exc:
            logger.warning(f"[缓存] 写入失败 {path.name}: {exc}")
