import json
from pathlib import Path

import pytest

from src.metadata.bangumi import BangumiProvider
from src.metadata.base import ProviderUnavailable

FIXTURES = Path(__file__).parent / "fixtures" / "bangumi"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeBangumi(BangumiProvider):
    def __init__(self, fail_search=False):
        super().__init__()
        self.fail_search = fail_search
        self.search_data = _load("search_rezero.json")
        self.subjects = _load("subjects.json")
        self.relations = _load("relations.json")
        self.episodes = _load("episodes.json")

    def _request(self, method, path, **kwargs):
        if path == "/v0/search/subjects":
            if self.fail_search:
                raise ProviderUnavailable("offline")
            return self.search_data
        if path.startswith("/search/subject/"):
            return {"list": []}
        if path.startswith("/v0/subjects/") and path.endswith("/subjects"):
            return self.relations.get(path.split("/")[3], [])
        if path.startswith("/v0/subjects/"):
            return self.subjects[path.split("/")[3]]
        if path == "/v0/episodes":
            subject_id = str(kwargs["params"]["subject_id"])
            return self.episodes[subject_id]
        raise AssertionError(path)


def test_search_ranks_base_title_first():
    provider = FakeBangumi()
    refs = provider.search("Test Anime", 0, "tv")
    assert refs[0]["provider_id"] == 100


def test_search_movie_filter():
    provider = FakeBangumi()
    refs = provider.search("Test Anime Movie", 0, "movie")
    assert [ref["provider_id"] for ref in refs] == [300]


def test_build_series_chain_and_specials():
    provider = FakeBangumi()
    series = provider.build_series(100)
    assert series["name"] == "测试动画"
    assert series["year"] == 2020
    seasons = {season["season_number"]: season for season in series["seasons"]}
    assert set(seasons) == {0, 1, 2}
    assert seasons[1]["episode_count"] == 12
    assert seasons[2]["episode_count"] == 12
    assert seasons[0]["episode_count"] == 1
    assert seasons[1]["episodes"][0]["name"] == "S1 第1话"
    assert "Test Anime EN" in seasons[1]["aliases"]


def test_build_movie():
    provider = FakeBangumi()
    movie = provider.build_movie(300)
    assert movie["name"] == "测试动画 剧场版"
    assert movie["year"] == 2023
    assert movie["runtime"] == 24


def test_search_failure_returns_empty():
    provider = FakeBangumi(fail_search=True)
    assert provider.search("anything", 0, "tv") == []
