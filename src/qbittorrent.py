# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""qBittorrent webhook payload parsing and duplicate suppression."""

import re
import json
from pathlib import Path
from dataclasses import field, dataclass
from typing import Any, Dict, List, Tuple, Mapping, Optional

from .logger import logger
from .config.config_manager import cm
from .utils.path import QB_INDEX_PATH

ANIME_TAGS = {"anime", "动漫", "动画", "bangumi", "番剧"}
MOVIE_TAGS = {"movie", "电影", "剧场版", "剧场"}
IGNORE_TAGS = {"no_process", "noprocess", "skip"}
TRUTHY = {"1", "true", "yes", "on"}


def decode_form_value(value: Any) -> str:
    """Decode qBittorrent's URL-encoded UTF-8 form values safely."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("latin1", errors="replace")
    text = str(value)
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _split_tags(value: str) -> List[str]:
    return [
        item.strip().casefold()
        for item in re.split(r"[,;，；]", value or "")
        if item.strip()
    ]


@dataclass
class QbTask:
    path: Path
    tags: List[str] = field(default_factory=list)
    category: str = ""
    torrent_hash: str = ""
    name: str = ""
    force: bool = False
    source: str = "qbittorrent"


def parse_payload(form: Mapping[str, Any]) -> QbTask:
    raw_path = decode_form_value(form.get("path") or form.get("content_path"))
    save_path = decode_form_value(form.get("save_path"))
    name = decode_form_value(form.get("name"))
    if not raw_path and save_path and name:
        raw_path = str(Path(save_path) / name)
    if not raw_path:
        raise ValueError("缺少 path/content_path 参数")

    tags_value = decode_form_value(form.get("tags") or form.get("tag"))
    tags = _split_tags(tags_value)
    if decode_form_value(form.get("no_process")).strip().casefold() in TRUTHY:
        tags.append("no_process")
    category = decode_form_value(form.get("category")).strip().casefold()
    torrent_hash = decode_form_value(form.get("hash")).strip().lower()
    force = decode_form_value(form.get("force")).strip().casefold() in TRUTHY

    return QbTask(
        path=Path(raw_path).expanduser(),
        tags=tags,
        category=category,
        torrent_hash=torrent_hash,
        name=name,
        force=force,
    )


def classify(task: QbTask) -> Tuple[Optional[bool], Optional[bool], bool]:
    """Return (is_anime, is_movie, should_skip)."""
    values = set(task.tags)
    if task.category:
        values.add(task.category)

    ignore_category = str(cm.get_config("qb_category_ignore") or "").casefold()
    if values & IGNORE_TAGS or (ignore_category and ignore_category in values):
        return None, None, True

    anime_category = str(cm.get_config("qb_category_anime") or "").casefold()
    movie_category = str(cm.get_config("qb_category_movie") or "").casefold()

    is_anime: Optional[bool] = None
    is_movie: Optional[bool] = None
    if values & ANIME_TAGS or (anime_category and anime_category in values):
        is_anime = True
    if values & MOVIE_TAGS or (movie_category and movie_category in values):
        is_movie = True
    return is_anime, is_movie, False


def index_path(torrent_hash: str) -> Path:
    return QB_INDEX_PATH / f"{torrent_hash}.json"


def load_index(torrent_hash: str) -> Dict[str, Any]:
    if not torrent_hash:
        return {}
    path = index_path(torrent_hash)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_duplicate(task: QbTask) -> bool:
    if task.force or not task.torrent_hash:
        return False
    record = load_index(task.torrent_hash)
    if record.get("status") != "success":
        return False
    return Path(str(record.get("path", ""))).expanduser() == task.path


def record_index(
    task: QbTask,
    *,
    task_uuid: str,
    status: str,
) -> None:
    if not task.torrent_hash:
        return
    path = index_path(task.torrent_hash)
    payload = {
        "path": str(task.path),
        "uuid": task_uuid,
        "status": status,
        "tags": task.tags,
        "category": task.category,
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"[qBittorrent] 写入索引失败: {exc}")
