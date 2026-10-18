import os

import pytest

from src.rename.trans import Trans

CONFIG = {
    "mode": "链接",
    "qb_safe_mode": True,
    "qb_link_fallback": "copy",
}


@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    monkeypatch.setattr(
        "src.rename.trans.cm.get_config", lambda key: CONFIG.get(key)
    )


def test_hardlink_transfer_keeps_source(tmp_path):
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    target = tmp_path / "library" / "target.mkv"
    trans = Trans({source: target}, "uuid")
    assert trans.trans_file() is None
    assert target.exists()
    assert os.stat(source).st_ino == os.stat(target).st_ino
    assert source.read_bytes() == b"video"


def test_existing_target_is_not_overwritten(tmp_path):
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    target = tmp_path / "target.mkv"
    target.write_bytes(b"old")
    assert Trans({source: target}, "uuid").trans_file() is None
    assert target.read_bytes() == b"old"
    assert source.exists()


def test_cross_device_fallback_copy(tmp_path, monkeypatch):
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    target = tmp_path / "library" / "target.mkv"
    monkeypatch.setattr(Trans, "_same_device", staticmethod(lambda *_: False))
    assert Trans({source: target}, "uuid").trans_file() is None
    assert target.read_bytes() == b"video"
    assert source.read_bytes() == b"video"
    assert os.stat(source).st_ino != os.stat(target).st_ino


def test_qb_safe_mode_forces_hardlink(tmp_path, monkeypatch):
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    target = tmp_path / "library" / "target.mkv"
    monkeypatch.setattr(
        "src.rename.trans.cm.get_config",
        lambda key: {"mode": "剪切", "qb_safe_mode": True}.get(key),
    )
    trans = Trans({source: target}, "uuid", qb_mode=True)
    assert trans.mode == "链接"
    assert trans.trans_file() is None
    assert source.exists()
    assert target.exists()
