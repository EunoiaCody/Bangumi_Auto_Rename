# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Metadata providers and resolver."""

from .tmdb import TMDBProvider
from .bangumi import BangumiProvider
from .resolver import MetadataResolver

__all__ = ["BangumiProvider", "TMDBProvider", "MetadataResolver"]
