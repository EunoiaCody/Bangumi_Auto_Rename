# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
import re
import json
import uuid
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Union, Optional

from . import naming
from .trans import Trans
from ..logger import logger
from .get_info import Search
from ..utils.path import TASK_PATH
from .ai_processor import AIProcessor
from ..config.config_manager import cm
from ..ai.models import AIAnalysisResult
from .utils import S0_TAG, EXTRA_TAG, IGNORE_DIR, VIDEO_SUFFIX, IGNORE_SUFFIX
from .cleaner import (
    remove_tag,
    remove_code,
    remove_season,
    divide_by_year,
    extract_number,
    extract_season,
    remove_episode,
    extract_base_num,
    match_and_extract,
    remove_similar_part,
    find_unique_parts_in_videos,
)


class Rename:
    def __init__(self) -> None:
        self.BANGUMI_PATH = Path(cm.get_config("bangumi_path"))
        self.MOVIE_PATH = Path(cm.get_config("movie_path"))
        self.ANIME_PATH = Path(cm.get_config("anime_path"))
        self.ANIME_MOVIE_PATH = Path(cm.get_config("anime_movie_path"))

        self.ANIME_MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.MOVIE_PATH.mkdir(parents=True, exist_ok=True)
        self.ANIME_PATH.mkdir(parents=True, exist_ok=True)
        self.BANGUMI_PATH.mkdir(parents=True, exist_ok=True)
        self.search = Search()
        self.ai_processor = AIProcessor()
        self.style = cm.get_config("rename_style") or "jellyfin"
        self.title_language = cm.get_config("filename_title_language") or "zh"
        self.R: Dict[Path, Path] = {}
        self._special_counters: Dict[Path, int] = {}
        self._trigger = "manual"

    # ------------------------------------------------------------------
    # Season detection
    # ------------------------------------------------------------------
    def get_season_id(
        self,
        tv_info: Dict,
        work_path: Path,
        path: Path,
        titles: Optional[List[Dict]] = None,
    ) -> int:
        seasons = tv_info.get("seasons") or []
        if not seasons:
            return 1

        season_numbers = {
            int(season.get("season_number", -1))
            for season in seasons
            if int(season.get("season_number", -1)) > 0
        }
        path_season = extract_season(path.name)
        if path_season > 0 and path_season in season_numbers:
            logger.info(f"[处理任务] 从路径提取季号: {path_season}")
            return path_season

        path_text = naming.sanitize_component(
            remove_tag(path.name) or path.stem
        ).casefold()
        best_number = 1
        best_ratio = 0.0
        for season in seasons:
            number = int(season.get("season_number", -1))
            if number <= 0:
                continue
            candidates = [str(season.get("name") or "")]
            candidates.extend(str(item) for item in season.get("aliases", []))
            for candidate in candidates:
                candidate = naming.sanitize_component(candidate).casefold()
                if len(candidate) < 2:
                    continue
                if candidate in path_text:
                    logger.info(
                        f"[处理任务] 季度名称命中: {candidate} -> S{number}"
                    )
                    return number
                ratio = SequenceMatcher(None, candidate, path_text).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_number = number
        if best_ratio >= 0.45:
            logger.info(
                f"[处理任务] 季度相似度识别: S{best_number} "
                f"({best_ratio:.2f})"
            )
            return best_number
        logger.info("[处理任务] 未识别到季度，默认第 1 季")
        return 1

    # ------------------------------------------------------------------
    # Per-file mapping
    # ------------------------------------------------------------------
    def process_sub(
        self,
        item_main_name: str,
        item_repeat: Optional[List[str]],
        item_path: Path,
        work_path: Path,
        season_id: int,
        *,
        series_info: Optional[Dict] = None,
        series_title: str = "",
        series_year: int = 0,
    ) -> None:
        item_name = item_path.name
        item_suffix = item_path.suffix.lower()

        if not item_path.is_file():
            return
        if item_suffix not in VIDEO_SUFFIX:
            # Associated subtitles/audio are attached to the video mapping.
            return

        if item_repeat:
            item_name_remove = remove_similar_part(item_repeat, item_path.stem)
        else:
            item_name_remove = item_path.stem
        item_name_l = item_name_remove.lower()
        n_item_name_l = item_name.replace(item_main_name, "").lower()

        lower_name = item_name.casefold()
        if any(
            marker in lower_name
            for marker in ("padding_file", "desktop.ini", ".ds_store")
        ):
            logger.info(f"[处理任务] 忽略 qB/系统临时文件：{item_path.name}")
            return
        for ignore_dir in IGNORE_DIR:
            if ignore_dir in item_path.name:
                logger.info(f"[处理任务] 忽略文件：{item_path.name}")
                return
        for ignore_tag in IGNORE_SUFFIX:
            if ignore_tag in item_suffix:
                logger.info(f"[处理任务] 忽略文件：{item_path.name}")
                return

        extra_pattern = r"[a-zA-Z\u4e00-\u9fa5]"
        for extra in EXTRA_TAG:
            if re.search(
                rf"(?<!{extra_pattern}){extra.lower()}(?!{extra_pattern})",
                n_item_name_l,
            ):
                folder = "extra" if self.style == "legacy" else "extras"
                target = work_path / folder / naming.extra_filename(item_name)
                self.R[item_path] = target
                logger.info(
                    f"[处理任务] 识别为 extra，映射到 {folder}/: {item_name}"
                )
                return

        for special in S0_TAG:
            if re.search(rf"{special.lower()}[\d]{{0,3}}", item_name_l):
                self._map_special(
                    item_path,
                    work_path,
                    series_info,
                    series_title,
                    series_year,
                )
                return

        _item_name = remove_code(remove_season(item_name_l))
        epp = extract_base_num(_item_name)
        ep = int(epp) if epp is not None else extract_number(_item_name)
        if ep is None and _item_name.isdigit():
            ep = int(_item_name)

        if ep is None:
            folder = "extra" if self.style == "legacy" else "extras"
            target = work_path / folder / naming.extra_filename(item_name)
            self.R[item_path] = target
            logger.warning(
                f"[处理任务] 未识别到集数，作为 extra 处理: {item_name}"
            )
            return

        _idata = match_and_extract(item_name)
        if _idata:
            season_id, ep = int(_idata[0]), int(_idata[1])

        title = naming.episode_title(
            series_info or {},
            int(season_id),
            int(ep),
            self.title_language,
        )
        target_name = naming.episode_filename(
            series_title,
            series_year,
            int(season_id),
            int(ep),
            title,
            item_suffix,
            style=self.style,
            original_name=item_name,
        )
        target = (
            work_path
            / naming.season_folder(int(season_id), style=self.style)
            / target_name
        )
        self.R[item_path] = target
        logger.info(f"[处理任务] 映射: {item_name} -> {target_name}")

    def _map_special(
        self,
        item_path: Path,
        work_path: Path,
        series_info: Optional[Dict],
        series_title: str,
        series_year: int,
    ) -> None:
        if self.style == "legacy":
            target = work_path / "Season0" / item_path.name
        else:
            number = self._special_counters.get(work_path, 0) + 1
            self._special_counters[work_path] = number
            title = naming.episode_title(
                series_info or {}, 0, number, self.title_language
            )
            target = (
                work_path
                / naming.season_folder(0)
                / naming.episode_filename(
                    series_title,
                    series_year,
                    0,
                    number,
                    title or item_path.stem,
                    item_path.suffix,
                    style=self.style,
                    original_name=item_path.name,
                )
            )
        self.R[item_path] = target
        logger.info(
            f"[处理任务] 识别为特典: {item_path.name} -> {target.name}"
        )

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    def process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
        metadata_id: Optional[int] = None,
        qb_mode: bool = False,
    ):
        if path.is_dir():
            is_video = any(
                sub.is_file() and sub.suffix in VIDEO_SUFFIX
                for sub in path.iterdir()
            )
            if is_video:
                return self._process(
                    path,
                    _is_anime,
                    _is_movie,
                    _tuuid,
                    cus_name,
                    cus_season_id,
                    metadata_id,
                    qb_mode,
                )
            else:
                results = []
                for sub_path in path.iterdir():
                    results.append(
                        self._process(
                            sub_path,
                            _is_anime,
                            _is_movie,
                            _tuuid,
                            cus_name,
                            cus_season_id,
                            metadata_id,
                            qb_mode,
                        )
                    )
                errors = [
                    result for result in results if isinstance(result, str)
                ]
                return False if errors else True
        else:
            return self._process(
                path,
                _is_anime,
                _is_movie,
                _tuuid,
                cus_name,
                cus_season_id,
                metadata_id,
                qb_mode,
            )

    def check_task_type(
        self,
        _uuid: str,
        rtpath_name: str,
        year: int,
        path: Path,
        is_anime: Optional[bool] = None,
        is_movie: Optional[bool] = None,
    ) -> Union[Tuple[str, Dict, bool, bool], str]:
        pos = 0.0
        logger.info("[处理任务] 开始判断媒体类型（动画/剧集/电影）")

        tv_name, tv_info = self.search.get_tv_info(rtpath_name, year, is_anime)
        logger.info(f"[处理任务] 剧集候选: {tv_name}")
        if not tv_name and year != 0:
            tv_name, tv_info = self.search.get_tv_info(
                rtpath_name, 0, is_anime
            )
            logger.info(f"[处理任务] 去除年份后剧集候选: {tv_name}")

        movie_name, movie_info = self.search.get_movie_info(
            rtpath_name, year, is_anime
        )
        logger.info(f"[处理任务] 电影候选: {movie_name}")
        if not movie_name and year != 0:
            movie_name, movie_info = self.search.get_movie_info(
                rtpath_name, 0, is_anime
            )
            logger.info(f"[处理任务] 去除年份后电影候选: {movie_name}")

        season_id = extract_season(rtpath_name)
        if tv_name:
            pos += 1
        elif movie_name:
            pos -= 1
        if season_id == -1:
            pos -= 0.6
            if path.is_file():
                pos -= 0.5
        else:
            pos += 0.6
            if path.is_file():
                pos += 0.5
        if path.is_dir():
            file_count = len([i for i in path.iterdir() if i.is_file()])
            pos += 0.4 if file_count > 6 else -0.4

        # Explicit user tags take precedence over the heuristic score.
        if is_movie is True and movie_info:
            pos = min(pos, -1.0)
        elif is_anime is True and tv_info and is_movie is not True:
            pos = max(pos, 1.0)
        elif is_movie is False and tv_info:
            pos = max(pos, 1.0)

        if pos > 0 or (is_movie is not None and not is_movie):
            logger.info("[处理任务] 判定为剧集")
            if not tv_info:
                return f"[元数据] 未搜索到剧集信息, 跳过{rtpath_name}"
            if is_anime is None:
                is_anime = bool(tv_info.get("is_anime", False))
            return tv_name, tv_info, is_anime, False

        logger.info("[处理任务] 判定为电影")
        if not movie_info:
            return self.error_reply(
                _uuid,
                f"[元数据] 未搜索到电影信息, 跳过{rtpath_name}",
                path,
                is_anime,
            )
        if is_anime is None:
            is_anime = bool(movie_info.get("is_anime", False))
        return movie_name, movie_info, is_anime, True

    def _process(
        self,
        path: Path,
        _is_anime: Optional[bool] = None,
        _is_movie: Optional[bool] = None,
        _tuuid: Optional[str] = None,
        cus_name: Optional[str] = None,
        cus_season_id: Optional[int] = None,
        metadata_id: Optional[int] = None,
        qb_mode: bool = False,
    ):
        _uuid = _tuuid or str(uuid.uuid4())
        self._trigger = "qbittorrent" if qb_mode else "manual"

        if not self.search.has_required_config():
            return self.error_reply(
                _uuid,
                "未配置元数据源：请配置 Bangumi 或 TMDB。",
                path,
                _is_anime,
                _is_movie,
            )

        logger.info(f"[处理任务] 开始处理 {path.name}")
        year = 0
        rtpath_name = remove_tag(path.name)
        if not rtpath_name:
            rtpath_name = remove_tag(path.name, True)
        if len(re.split(r"[\s-]+", rtpath_name)) > 3:
            rtpath_name = " ".join(re.split(r"[\s-]+", rtpath_name))
        if rtpath_name.count(".") >= 3:
            rtpath_name = " ".join(rtpath_name.split("."))
            rtpath_name, year = divide_by_year(rtpath_name)
        rtpath_name = remove_episode(remove_season(rtpath_name)).strip("!")
        logger.info(f"[处理任务] 搜索名称: {rtpath_name}")

        if path.is_file() and path.suffix.lower() not in VIDEO_SUFFIX:
            logger.info(f"[处理任务] {path.name} 不是视频，跳过")
            return

        if cus_name:
            rtpath_name = cus_name

        if metadata_id:
            info = self.search.get_series_by_id(int(metadata_id))
            if not info:
                return self.error_reply(
                    _uuid,
                    f"[元数据] 指定的 Bangumi 条目不存在: {metadata_id}",
                    path,
                    _is_anime,
                    _is_movie,
                )
            name = str(info.get("name") or "")
            is_movie = info.get("media_type") == "movie"
            is_anime = True
        else:
            task_type = self.check_task_type(
                _uuid,
                rtpath_name,
                year,
                path,
                _is_anime,
                _is_movie,
            )
            if isinstance(task_type, str):
                return self.error_reply(
                    _uuid,
                    task_type,
                    path,
                    _is_anime,
                    _is_movie,
                )
            name, info, is_anime, is_movie = task_type

        media_year = naming.media_year(info or {})
        metadata_source = str((info or {}).get("provider") or "")
        metadata_provider_id = (info or {}).get("provider_id")

        if is_movie:
            if not name:
                return self.error_reply(
                    _uuid,
                    f"[元数据] 未搜索到电影信息, 跳过{rtpath_name}",
                    path,
                    is_anime,
                    is_movie,
                )
            work_root = self.ANIME_MOVIE_PATH if is_anime else self.MOVIE_PATH
            work_path = work_root / naming.movie_folder(
                name, media_year, style=self.style
            )
            work_path.mkdir(parents=True, exist_ok=True)
            self._map_movie_files(path, work_path, name, media_year)
            season_id = 0
            self._map_associated_files()
        else:
            if not name:
                return self.error_reply(
                    _uuid,
                    f"[元数据] 未搜索到剧集信息, 跳过{rtpath_name}",
                    path,
                    is_anime,
                    is_movie,
                )
            work_root = self.ANIME_PATH if is_anime else self.BANGUMI_PATH
            work_path = work_root / naming.series_folder(
                name, media_year, style=self.style
            )
            work_path.mkdir(parents=True, exist_ok=True)
            season_id = self.get_season_id(
                info or {}, work_path, path, (info or {}).get("aliases")
            )
            if cus_season_id:
                season_id = int(cus_season_id)

            use_ai = is_anime and self.ai_processor.ai_client.is_available()
            if use_ai:
                ai_result: Optional[AIAnalysisResult] = (
                    self.ai_processor.analyze_anime_files(path, info or {})
                )
                if self._should_use_ai(ai_result):
                    logger.info("[处理任务] 使用 AI 映射")
                    self.R = self.ai_processor.apply_ai_mapping(
                        ai_result=ai_result,
                        base_path=path,
                        work_path=work_path,
                        series_info=info,
                        series_title=name,
                        series_year=media_year,
                        style=self.style,
                        title_language=self.title_language,
                    )
                    if not self.R:
                        logger.warning(
                            "[处理任务] AI 无有效映射，回退传统流程"
                        )
                        self._process_traditional(
                            path,
                            rtpath_name,
                            work_path,
                            season_id,
                            series_info=info,
                            series_title=name,
                            series_year=media_year,
                        )
                else:
                    logger.info("[处理任务] AI 置信度不足，使用传统流程")
                    self._process_traditional(
                        path,
                        rtpath_name,
                        work_path,
                        season_id,
                        series_info=info,
                        series_title=name,
                        series_year=media_year,
                    )
            else:
                self._process_traditional(
                    path,
                    rtpath_name,
                    work_path,
                    season_id,
                    series_info=info,
                    series_title=name,
                    series_year=media_year,
                )
            self._map_associated_files()

        task_data = {
            "path": str(path),
            "is_anime": is_anime,
            "is_movie": is_movie,
            "name": name,
            "season_id": season_id,
            "uuid": str(_uuid),
            "error": None,
            "status": "success",
            "use_ai": bool(
                is_anime and self.ai_processor.ai_client.is_available()
            ),
            "metadata_source": metadata_source,
            "metadata_id": metadata_provider_id,
            "trigger": "qbittorrent" if qb_mode else "manual",
        }
        trans_result = Trans(self.R, _uuid, qb_mode=qb_mode).trans_file()
        self.R = {}
        if isinstance(trans_result, str):
            return self.error_reply(
                _uuid,
                trans_result,
                path,
                is_anime,
                is_movie,
                name,
                season_id,
            )
        task_path = TASK_PATH / f"{_uuid}.json"
        with open(task_path, "w", encoding="UTF-8") as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return True

    def _should_use_ai(self, ai_result: Optional[AIAnalysisResult]) -> bool:
        if not ai_result:
            return False
        threshold = cm.get_config("ai_confidence_threshold")
        if threshold == "High":
            return ai_result.confidence == "High"
        if threshold == "Medium":
            return ai_result.confidence in {"High", "Medium"}
        return True

    def _map_movie_files(
        self,
        path: Path,
        work_path: Path,
        name: str,
        year: int,
    ) -> None:
        if path.is_file():
            files = [path]
        else:
            files = sorted(
                [item for item in path.iterdir() if item.is_file()],
                key=naming.natural_key,
            )
        videos = [
            item for item in files if item.suffix.lower() in VIDEO_SUFFIX
        ]
        for index, item in enumerate(videos, start=1):
            match = re.search(
                r"(?:cd|part|disc|disk)[\s._-]?(\d+)",
                item.stem,
                re.I,
            )
            part = (
                int(match.group(1))
                if match
                else (index if len(videos) > 1 else None)
            )
            part_type = (
                "cd" if match and "cd" in match.group(0).lower() else "part"
            )
            target_name = naming.movie_filename(
                name,
                year,
                item.suffix,
                style=self.style,
                original_name=item.name,
                part=part,
                part_type=part_type,
            )
            self.R[item] = work_path / target_name
            logger.info(f"[处理任务] 电影映射: {item.name} -> {target_name}")

    def _map_associated_files(self) -> None:
        snapshot = list(self.R.items())
        for source, target in snapshot:
            if source.suffix.lower() not in VIDEO_SUFFIX:
                continue
            if not source.parent.exists():
                continue
            for sibling in source.parent.iterdir():
                if not sibling.is_file() or sibling == source:
                    continue
                if sibling.suffix.lower() in VIDEO_SUFFIX:
                    continue
                if sibling.suffix.lower() == ".nfo":
                    continue
                if sibling in self.R:
                    continue
                if siblings_match(source, sibling):
                    suffix = sibling.name[len(source.stem) :]
                    new_target = target.with_name(f"{target.stem}{suffix}")
                    self.R[sibling] = new_target

    def _process_traditional(
        self,
        path: Path,
        rtpath_name: str,
        work_path: Path,
        season_id: int,
        *,
        series_info: Optional[Dict] = None,
        series_title: str = "",
        series_year: int = 0,
    ) -> None:
        if path.is_file():
            logger.info(f"[处理任务] 处理单文件: {path.name}")
            self.process_sub(
                rtpath_name,
                None,
                path,
                work_path,
                season_id,
                series_info=series_info,
                series_title=series_title,
                series_year=series_year,
            )
            return

        logger.info(f"[处理任务] 处理文件夹: {path.name}")
        repeat = find_unique_parts_in_videos(path)
        for item_path in path.iterdir():
            if item_path.is_dir():
                repeat_2 = find_unique_parts_in_videos(item_path)
                for sub_item in item_path.iterdir():
                    self.process_sub(
                        rtpath_name,
                        repeat_2,
                        sub_item,
                        work_path,
                        season_id,
                        series_info=series_info,
                        series_title=series_title,
                        series_year=series_year,
                    )
            else:
                self.process_sub(
                    rtpath_name,
                    repeat,
                    item_path,
                    work_path,
                    season_id,
                    series_info=series_info,
                    series_title=series_title,
                    series_year=series_year,
                )

    def error_reply(
        self,
        _uuid: str,
        error: str,
        path: Path,
        is_anime: Optional[bool] = None,
        is_movie: Optional[bool] = None,
        name: Optional[str] = None,
        season_id: Optional[int] = None,
        *,
        trigger: Optional[str] = None,
    ):
        task_path = TASK_PATH / f"{_uuid}.json"
        task_data = {
            "path": str(path),
            "is_anime": is_anime,
            "is_movie": is_movie,
            "name": name,
            "season_id": season_id,
            "uuid": str(_uuid),
            "error": error,
            "status": "error",
            "trigger": trigger or self._trigger,
        }
        with open(task_path, "w", encoding="UTF-8") as file:
            json.dump(task_data, file, indent=4, ensure_ascii=False)
        return error


def siblings_match(video: Path, sibling: Path) -> bool:
    return (
        sibling.name.startswith(f"{video.stem}.") or sibling.stem == video.stem
    )
