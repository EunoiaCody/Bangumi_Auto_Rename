# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
from typing import Dict, List, Literal, Optional

from pydantic import (
    Field,
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


def _migrate_legacy_keys(data):
    """Accept analysis JSON produced by older TMDB-only versions."""
    if not isinstance(data, dict):
        return data
    data = dict(data)
    aliases = {
        "maps_to_tmdb_seasons": "maps_to_seasons",
        "tmdb_season": "season",
        "tmdb_episode": "episode",
    }
    for old, new in aliases.items():
        if old in data and new not in data:
            data[new] = data[old]
    return data


class SeasonMapping(BaseModel):
    """季度映射对象"""

    local_group_name: str = Field(..., description="本地组名称，例如目录名")
    maps_to_seasons: List[int] = Field(
        ..., description="对应的元数据季度列表，无需包括第0季"
    )

    @field_validator("maps_to_seasons")
    @classmethod
    def validate_seasons(cls, v):
        if not isinstance(v, list):
            raise ValueError("maps_to_seasons必须是列表类型")
        for season in v:
            if not isinstance(season, int) or season < 0:
                raise ValueError(f"季度号必须是非负整数: {season}")
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy(cls, data):
        return _migrate_legacy_keys(data)

    model_config = ConfigDict(populate_by_name=True)


class EpisodeMapping(BaseModel):
    """单个剧集映射"""

    file_path: str = Field(..., description="本地文件的相对路径")
    season: int = Field(..., ge=0, description="元数据季号")
    episode: int = Field(..., ge=1, description="元数据集号")
    episode_type: Literal["regular", "special", "movie"] = Field(
        default="regular", description="剧集类型"
    )
    confidence: Literal["High", "Medium", "Low"] = Field(
        default="Medium", description="置信度等级"
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy(cls, data):
        return _migrate_legacy_keys(data)

    model_config = ConfigDict(populate_by_name=True)


class AIAnalysisResult(BaseModel):
    """AI分析结果"""

    confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="总体置信度等级"
    )
    reason: str = Field(..., description="分析理由说明")
    season_mapping: List[SeasonMapping] = Field(
        default_factory=list,
        description="季度映射列表，如整个子路径下均无匹配命中项，则无需包含",
    )
    file_mapping: List[EpisodeMapping] = Field(
        default_factory=list, description="剧集映射列表"
    )
    extra_notes: Optional[str] = Field(
        default=None, description="额外特殊情况说明"
    )

    @field_validator("file_mapping")
    @classmethod
    def validate_mapping_not_empty(cls, v, info):
        if hasattr(info, "data") and info.data:
            confidence = info.data.get("confidence", "Low")
            if confidence in ["High", "Medium"] and not v:
                raise ValueError("高置信度结果必须包含映射信息")
        return v

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def model_json_schema(
        cls, by_alias: bool = True, ref_template: str = "#/$defs/{model}"
    ) -> Dict:
        schema = super().model_json_schema(
            by_alias=by_alias, ref_template=ref_template
        )

        def remove_additional_properties(obj):
            if isinstance(obj, dict):
                obj.pop("additionalProperties", None)
                for value in obj.values():
                    remove_additional_properties(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_additional_properties(item)

        remove_additional_properties(schema)
        return schema

    @classmethod
    def schema(
        cls, by_alias: bool = True, ref_template: str = "#/definitions/{model}"
    ) -> Dict:
        return cls.model_json_schema(
            by_alias=by_alias, ref_template=ref_template
        )
