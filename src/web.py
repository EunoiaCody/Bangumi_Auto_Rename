# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
from pathlib import Path
from typing import Optional

from nicegui import ui, app
from fastapi import Request

from . import qbittorrent
from .logger import logger
from .main_page import main_page
from .utils.utils import no_scroll_bar
from .task_queue import new_task, task_queue
from .pages.data_table_page import create_table

TRUTHY = {"1", "true", "yes", "on"}


@ui.page("/")
def main():
    ui.add_head_html(no_scroll_bar)
    main_page()


def _bool_or_none(value) -> Optional[bool]:
    text = str(value or "").strip().casefold()
    if text in TRUTHY:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


@app.post("/sendTask")
async def _send_task(request: Request):
    form = dict(await request.form())
    try:
        qb_task = qbittorrent.parse_payload(form)
    except ValueError as exc:
        logger.error(f"[收到任务] 参数错误: {exc}")
        return {"code": 400, "data": str(exc)}

    path = qb_task.path
    logger.info(
        f"[收到任务] path={path} tags={qb_task.tags} "
        f"category={qb_task.category} hash={qb_task.torrent_hash}"
    )

    if not path.exists():
        logger.error(f"[结束任务] 路径不存在: {path}")
        return {"code": 404, "data": f"路径不存在: {path}"}

    is_anime = _bool_or_none(form.get("is_anime"))
    is_movie = _bool_or_none(form.get("is_movie"))
    tag_anime, tag_movie, skip = qbittorrent.classify(qb_task)
    if is_anime is None:
        is_anime = tag_anime
    if is_movie is None:
        is_movie = tag_movie

    if skip:
        logger.info(f"[结束任务] 标签要求忽略: {path}")
        return {"code": 202, "data": "已忽略，不处理"}

    if qbittorrent.is_duplicate(qb_task):
        logger.info(f"[结束任务] 重复触发，跳过: {path}")
        return {
            "code": 202,
            "data": "重复触发，跳过",
            "duplicate": True,
        }

    metadata_id = form.get("metadata_id")
    try:
        metadata_id_int = int(metadata_id) if metadata_id else None
    except (TypeError, ValueError):
        metadata_id_int = None

    queued = new_task(
        path=path,
        is_anime=is_anime,
        is_movie=is_movie,
        metadata_id=metadata_id_int,
        qb_mode=bool(qb_task.torrent_hash or qb_task.tags or qb_task.category),
        qb_task=qb_task,
    )
    task_queue.enqueue(queued)
    create_table.refresh()

    wait = (
        str(form.get("wait", "")).casefold() in TRUTHY
        or str(request.query_params.get("wait", "")).casefold() in TRUTHY
    )
    if wait:
        result = task_queue.wait(queued.uuid, timeout=3600)
        if result is True:
            return {
                "code": 200,
                "data": "处理完成",
                "uuid": queued.uuid,
            }
        return {
            "code": 500,
            "data": str(result or "处理失败"),
            "uuid": queued.uuid,
        }

    return {
        "code": 202,
        "data": "已加入队列",
        "uuid": queued.uuid,
    }
