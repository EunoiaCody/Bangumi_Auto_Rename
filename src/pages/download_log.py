# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
from nicegui import ui

from ..utils.path import log_path


def download_log():
    ui.download(log_path, log_path.name)
