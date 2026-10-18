# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
from pathlib import Path

MAIN_PATH = Path(__file__).parents[1]
DATA_PATH = Path(__file__).parents[2] / "data"

IMAGE = MAIN_PATH / "images"
CONFIG_PATH = DATA_PATH / "config.json"
LOG_PATH = DATA_PATH / "log"
RECORD_PATH = DATA_PATH / "record"
TASK_PATH = DATA_PATH / "task"
AI_ANALYSIS_PATH = DATA_PATH / "ai_analysis"
CACHE_PATH = DATA_PATH / "cache"
QB_INDEX_PATH = DATA_PATH / "qb_index"

log_path = LOG_PATH / "BAR.log"
for i in [
    DATA_PATH,
    LOG_PATH,
    RECORD_PATH,
    TASK_PATH,
    AI_ANALYSIS_PATH,
    CACHE_PATH,
    QB_INDEX_PATH,
]:
    if not i.exists():
        i.mkdir(parents=True)
