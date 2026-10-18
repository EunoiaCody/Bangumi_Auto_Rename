# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
import os
import json
import errno
import shutil
from pathlib import Path
from typing import Dict, Optional

from ..logger import logger
from ..utils.path import RECORD_PATH
from ..config.config_manager import cm


class Trans:
    def __init__(
        self,
        R: Dict[Path, Path],
        uuid: str,
        *,
        qb_mode: bool = False,
    ) -> None:
        self.mode = cm.get_config("mode") or "链接"
        self.R = R
        self.uuid = uuid
        self.qb_mode = qb_mode
        self.safe_mode = qb_mode and bool(cm.get_config("qb_safe_mode"))
        if self.safe_mode:
            if self.mode != "链接":
                logger.warning(
                    f"[处理迁移] qBittorrent 安全模式强制使用硬链接，"
                    f"忽略配置模式: {self.mode}"
                )
            self.mode = "链接"
        self.link_fallback = (
            cm.get_config("qb_link_fallback") or "copy"
        ).lower()

    def trans_file(self) -> Optional[str]:
        path = RECORD_PATH / f"{self.uuid}.json"
        with open(str(path), "w", encoding="utf-8") as file:
            json.dump(
                {str(k): str(v) for k, v in self.R.items()},
                file,
                ensure_ascii=False,
            )

        errors = []
        for source_path, target_path in self.R.items():
            error = self._transfer_one(source_path, target_path)
            if error:
                errors.append(error)
        return "; ".join(errors) if errors else None

    def _transfer_one(self, source: Path, target: Path) -> Optional[str]:
        try:
            if target.is_dir() or source.is_dir():
                return None
            if not source.exists():
                logger.warning(f"[处理迁移] 源文件不存在: {source}")
                return None
            if target.exists():
                try:
                    if os.path.samefile(source, target):
                        logger.info(
                            f"[处理迁移] 目标已存在同一文件，跳过: {target}"
                        )
                        return None
                except OSError:
                    pass
                logger.warning(f"[处理迁移] 目标已存在，跳过不覆盖: {target}")
                return None

            target.parent.mkdir(parents=True, exist_ok=True)

            if self.mode == "剪切":
                shutil.move(str(source), str(target))
                logger.info(f"[处理迁移] 移动: {source.name} -> {target}")
            elif self.mode == "复制":
                self._copy(source, target)
                logger.info(f"[处理迁移] 复制: {source.name} -> {target}")
            elif self.mode == "链接":
                if self._same_device(source, target.parent):
                    try:
                        os.link(source, target)
                    except OSError as exc:
                        if exc.errno == errno.EXDEV:
                            return self._cross_device(source, target)
                        raise
                    self._verify_link(source, target)
                    logger.info(
                        f"[处理迁移] 硬链接: {source.name} -> {target}"
                    )
                else:
                    return self._cross_device(source, target)
            else:
                return (
                    f"[处理迁移] 模式错误，仅支持剪切/复制/链接: {self.mode}"
                )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[处理迁移] 失败 {source} -> {target}: {exc}")
            return str(exc)

    def _copy(self, source: Path, target: Path) -> None:
        tmp = target.with_name(f"{target.name}.tmp")
        try:
            shutil.copy2(source, tmp)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def _cross_device(self, source: Path, target: Path) -> Optional[str]:
        fallback = self.link_fallback
        if fallback == "symlink":
            os.symlink(source, target)
            logger.warning(
                f"[处理迁移] 跨文件系统，已创建软链接（种子删除后会失效）: {target}"
            )
            return None
        if fallback == "skip":
            logger.warning(f"[处理迁移] 跨文件系统，按配置跳过: {target}")
            return None
        self._copy(source, target)
        logger.warning(f"[处理迁移] 跨文件系统，无法硬链接，已复制: {target}")
        return None

    @staticmethod
    def _same_device(source: Path, target_dir: Path) -> bool:
        try:
            return source.stat().st_dev == target_dir.stat().st_dev
        except OSError:
            return False

    @staticmethod
    def _verify_link(source: Path, target: Path) -> None:
        try:
            if source.stat().st_ino != target.stat().st_ino:
                raise OSError("硬链接 inode 校验失败")
        except OSError as exc:
            logger.warning(f"[处理迁移] 硬链接校验失败 {target}: {exc}")
