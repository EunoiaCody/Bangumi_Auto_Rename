from src.rename import naming


def test_sanitize_invalid_characters():
    assert naming.sanitize_component("A/B:C*D?") == "A B C D"


def test_series_and_season_folders():
    assert naming.series_folder("Test Anime", 2020) == "Test Anime (2020)"
    assert naming.season_folder(0) == "Season 00"
    assert naming.season_folder(1) == "Season 01"
    assert naming.season_folder(1, style="legacy") == "Season1"


def test_episode_filename_jellyfin():
    name = naming.episode_filename(
        "Test Anime", 2020, 1, 2, "Episode Title", ".mkv"
    )
    assert name == "Test Anime (2020) S01E02 - Episode Title.mkv"


def test_episode_filename_without_title_and_parts():
    assert (
        naming.episode_filename("Test", 2020, 1, 2, "", ".mkv")
        == "Test (2020) S01E02.mkv"
    )
    assert (
        naming.episode_filename("Test", 2020, 1, 2, "Title", ".mkv", part=1)
        == "Test (2020) S01E02 - Title - part1.mkv"
    )


def test_legacy_episode_filename():
    assert (
        naming.episode_filename(
            "Test",
            2020,
            1,
            2,
            "",
            ".mkv",
            style="legacy",
            original_name="raw.mkv",
        )
        == "S01E02 - raw.mkv"
    )


def test_movie_filename_parts():
    assert naming.movie_filename("Movie", 2021, ".mkv") == "Movie (2021).mkv"
    assert (
        naming.movie_filename("Movie", 2021, ".mkv", part=1)
        == "Movie (2021) - part1.mkv"
    )


def test_episode_title_language():
    series = {
        "seasons": [
            {
                "season_number": 1,
                "episodes": [
                    {
                        "episode_number": 1,
                        "name": "中文标题",
                        "name_original": "日本語タイトル",
                    }
                ],
            }
        ]
    }
    assert naming.episode_title(series, 1, 1, "zh") == "中文标题"
    assert naming.episode_title(series, 1, 1, "ja") == "日本語タイトル"
    assert naming.episode_title(series, 1, 1, "none") == ""
    assert naming.episode_title(series, 2, 1) == ""
