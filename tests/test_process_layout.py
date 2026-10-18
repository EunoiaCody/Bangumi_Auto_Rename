from pathlib import Path

import pytest

from src.rename.process import Rename


@pytest.fixture
def fake_rename(tmp_path, monkeypatch):
    monkeypatch.setattr("src.rename.process.TASK_PATH", tmp_path / "task")
    (tmp_path / "task").mkdir()
    monkeypatch.setattr("src.rename.trans.RECORD_PATH", tmp_path / "record")
    (tmp_path / "record").mkdir()
    cfg = {
        "bangumi_path": str(tmp_path / "TV"),
        "movie_path": str(tmp_path / "Movies"),
        "anime_path": str(tmp_path / "Anime"),
        "anime_movie_path": str(tmp_path / "AnimeMovies"),
        "mode": "链接",
        "qb_safe_mode": False,
        "qb_link_fallback": "copy",
        "rename_style": "jellyfin",
        "filename_title_language": "zh",
    }
    monkeypatch.setattr(
        "src.rename.process.cm.get_config",
        lambda key: cfg.get(key, ""),
    )

    info = {
        "provider": "bangumi",
        "provider_id": 1,
        "media_type": "tv",
        "name": "Test Show",
        "names": {"bangumi": "Test Show"},
        "year": 2020,
        "first_air_date": "2020-04-01",
        "is_anime": True,
        "seasons": [
            {
                "season_number": 0,
                "name": "Specials",
                "episode_count": 1,
                "episodes": [{"episode_number": 1, "name": "OVA"}],
            },
            {
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 2,
                "episodes": [
                    {"episode_number": 1, "name": "第一话"},
                    {"episode_number": 2, "name": "第二话"},
                ],
            },
        ],
    }

    rename = Rename()
    rename.ANIME_PATH = tmp_path / "Anime"
    rename.MOVIE_PATH = tmp_path / "Movies"
    rename.ANIME_MOVIE_PATH = tmp_path / "AnimeMovies"
    rename.BANGUMI_PATH = tmp_path / "TV"
    for path in (
        rename.ANIME_PATH,
        rename.MOVIE_PATH,
        rename.ANIME_MOVIE_PATH,
        rename.BANGUMI_PATH,
    ):
        path.mkdir(exist_ok=True)
    rename.style = "jellyfin"
    rename.title_language = "zh"
    rename.search.get_tv_info = lambda query, year, hint=None: (
        "Test Show",
        info,
    )
    rename.search.get_movie_info = lambda query, year, hint=None: ("", None)
    rename.search.has_required_config = lambda: True
    rename.search.fill_season_info = lambda value: value
    rename.ai_processor.ai_client.is_available = lambda: False

    source = tmp_path / "download" / "Test Show S01"
    source.mkdir(parents=True)
    for name in (
        "[Group] Test Show - 01.mkv",
        "[Group] Test Show - 02.mkv",
        "[Group] Test Show - OVA.mkv",
        "[Group] Test Show - NCOP.mkv",
    ):
        (source / name).write_bytes(b"video")
    (source / "[Group] Test Show - 01.zh.ass").write_text("sub")
    return rename, source, tmp_path


def test_jellyfin_layout(fake_rename):
    rename, source, tmp_path = fake_rename
    assert rename.process(source, True, False) is True
    root = tmp_path / "Anime" / "Test Show (2020)"
    assert (
        root / "Season 01" / "Test Show (2020) S01E01 - 第一话.mkv"
    ).exists()
    assert (
        root / "Season 01" / "Test Show (2020) S01E01 - 第一话.zh.ass"
    ).exists()
    assert (root / "Season 00" / "Test Show (2020) S00E01 - OVA.mkv").exists()
    assert (root / "extras" / "[Group] Test Show - NCOP.mkv").exists()
    assert not list(root.rglob("*.nfo"))
    assert source.exists()
