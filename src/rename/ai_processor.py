# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
from pathlib import Path
from typing import Dict, List, Optional

from . import naming
from ..logger import logger
from .utils import VIDEO_SUFFIX
from ..ai.client import AIClient
from ..ai.models import AIAnalysisResult
from ..ai.video_analyzer import VideoAnalyzer


class AIProcessor:
    """AI辅助处理器，用于智能分析和重命名"""

    def __init__(self):
        self.ai_client = AIClient()
        self.video_analyzer = VideoAnalyzer()

    def analyze_anime_files(
        self, path: Path, anime_info: Dict
    ) -> Optional[AIAnalysisResult]:
        """
        使用AI分析动漫文件的映射关系

        Args:
            path: 本地文件路径
            anime_info: 统一元数据（Bangumi/TMDB）

        Returns:
            验证后的AI分析结果
        """
        if not self.ai_client.is_available():
            logger.info("[AI处理] AI功能未启用，跳过AI分析")
            return None

        # 收集视频文件
        video_files = self._collect_video_files(path)
        if not video_files:
            logger.warning("[AI处理] 未找到视频文件")
            return None

        # 分析视频文件
        file_analysis = self.video_analyzer.analyze_video_files(
            path, video_files
        )

        # 使用AI分析映射关系
        ai_result = self.ai_client.analyze_episode_mapping(
            anime_info, file_analysis
        )

        if ai_result:
            logger.info(f"[AI处理] AI分析完成，置信度: {ai_result.confidence}")

            # 记录低置信度结果到单独日志
            if ai_result.confidence == "Low":
                self._log_low_confidence_result(path, ai_result)

        return ai_result

    def apply_ai_mapping(
        self,
        ai_result: AIAnalysisResult | None,
        base_path: Path,
        work_path: Path,
        *,
        series_info: Optional[Dict] = None,
        series_title: str = "",
        series_year: int = 0,
        style: str = "jellyfin",
        title_language: str = "zh",
    ) -> Dict[Path, Path]:
        """Apply an AI mapping using the same Jellyfin naming rules."""
        if not ai_result or not ai_result.file_mapping:
            logger.info("[AI处理] 无有效AI分析结果，返回空映射")
            return {}

        new_mapping: Dict[Path, Path] = {}
        all_local_files = (
            list(base_path.rglob("*"))
            if base_path.is_dir()
            else list(base_path.parent.iterdir())
        )

        try:
            if ai_result.season_mapping:
                logger.info("[AI处理] AI季度映射:")
                for season_map in ai_result.season_mapping:
                    logger.info(
                        f"  {season_map.local_group_name} -> 季度: "
                        f"{season_map.maps_to_seasons}"
                    )

            for mapping in ai_result.file_mapping:
                source_path = (base_path / mapping.file_path).resolve()
                if not source_path.exists():
                    logger.warning(
                        f"[AI处理] AI返回的文件路径不存在: {source_path}"
                    )
                    continue

                season = int(mapping.season)
                episode = int(mapping.episode)
                episode_type = mapping.episode_type
                confidence = mapping.confidence

                if episode_type == "special":
                    season = 0
                    target_dir = work_path / naming.season_folder(
                        0, style=style
                    )
                    title = (
                        naming.episode_title(
                            series_info or {},
                            0,
                            episode,
                            title_language,
                        )
                        or source_path.stem
                    )
                elif episode_type == "movie":
                    target_dir = work_path / (
                        "extra" if style == "legacy" else "extras"
                    )
                    title = ""
                else:
                    target_dir = work_path / naming.season_folder(
                        season, style=style
                    )
                    title = naming.episode_title(
                        series_info or {},
                        season,
                        episode,
                        title_language,
                    )

                target_dir.mkdir(parents=True, exist_ok=True)

                if episode_type == "movie":
                    new_video_filename = naming.extra_filename(
                        source_path.name
                    )
                else:
                    new_video_filename = naming.episode_filename(
                        series_title,
                        series_year,
                        season,
                        episode,
                        title,
                        source_path.suffix,
                        style=style,
                        original_name=source_path.name,
                    )

                target_video_path = target_dir / new_video_filename
                new_mapping[source_path] = target_video_path
                logger.info(
                    f"[AI处理] 映射: {source_path.name} -> "
                    f"{new_video_filename} (类型: {episode_type}, "
                    f"置信度: {confidence})"
                )

                video_filename = source_path.stem
                for other_file in all_local_files:
                    if not other_file.is_file() or other_file == source_path:
                        continue
                    if other_file.name.startswith(f"{video_filename}."):
                        suffix_part = other_file.name[len(video_filename) :]
                        new_video_stem = new_video_filename.rsplit(".", 1)[0]
                        new_associated_filename = (
                            f"{new_video_stem}{suffix_part}"
                        )
                        new_mapping[other_file] = (
                            target_dir / new_associated_filename
                        )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[AI处理] 应用AI映射时发生严重错误: {exc}", exc_info=True
            )
            return {}

        return new_mapping

    def _collect_video_files(self, path: Path) -> List[Path]:
        """收集指定路径下的所有视频文件"""
        video_files = []

        if path.is_file():
            if path.suffix.lower() in VIDEO_SUFFIX:
                video_files.append(path)
        else:
            for item in path.rglob("*"):
                if item.is_file() and item.suffix.lower() in VIDEO_SUFFIX:
                    video_files.append(item)

        return sorted(video_files)

    def _log_low_confidence_result(
        self, path: Path, ai_result: AIAnalysisResult
    ):
        """记录低置信度结果到单独日志"""
        confidence = ai_result.confidence
        reason = ai_result.reason

        logger.warning(
            f"[AI低置信度] 路径: {path} | 置信度: {confidence} | "
            f"理由: {reason} | 映射数量: {len(ai_result.file_mapping)}"
        )

        # 记录季度映射
        if ai_result.season_mapping:
            for season_map in ai_result.season_mapping:
                logger.warning(
                    f"[AI低置信度] 季度映射: {season_map.local_group_name} -> {season_map.maps_to_seasons}"
                )

        # 详细记录每个映射的置信度
        for mapping in ai_result.file_mapping:
            if mapping.confidence == "Low":
                logger.warning(
                    f"[AI低置信度文件] {mapping.file_path} -> "
                    f"S{mapping.season:02d}E{mapping.episode:02d} "
                    f"(类型: {mapping.episode_type}, 置信度: {mapping.confidence})"
                )

        # 记录额外说明
        if ai_result.extra_notes:
            logger.warning(f"[AI低置信度] 额外说明: {ai_result.extra_notes}")
