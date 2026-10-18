# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody

from nicegui import ui

from ..element.red import RedButton
from ..__version__ import (
    __url__,
    __author__,
    __license__,
    __version__,
    __original_url__,
)


class AboutPage(ui.dialog):
    """Original author and fork attribution."""

    def __init__(self) -> None:
        super().__init__()
        with self, ui.card().style("width: 520px; max-width: 90vw;"):
            ui.label("关于 Bangumi_Auto_Rename").style(
                "font-size: 20px; font-weight: bold"
            )
            ui.separator()
            ui.label(f"版本：v{__version__}")
            ui.label(f"作者：{__author__}")
            ui.label("原始项目：KimigaiiWuyi").style("font-size: 13px")
            ui.link(
                "上游仓库（KimigaiiWuyi）",
                __original_url__,
                new_tab=True,
            )
            ui.label("本修改版：EunoiaCody").style("font-size: 13px")
            ui.link("Fork 仓库（EunoiaCody）", __url__, new_tab=True)
            ui.separator()
            ui.label(
                "本程序基于 GNU General Public License v3 发布，"
                "原始版权归 KimigaiiWuyi 所有；"
                "本修改版同样以 GPL-3.0-or-later 发布。"
            ).style("font-size: 12px; line-height: 1.6")
            ui.label(f"许可证：{__license__}").style("font-size: 12px")
            with ui.row().classes("w-full justify-end"):
                RedButton("关闭", on_click=self.close).props("outline")


def about_page() -> None:
    AboutPage().open()
