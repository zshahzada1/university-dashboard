from pathlib import Path
from app.services.seeding import ensure_seeded
from app.settings import Settings

def _settings(uni: Path, data: Path) -> Settings:
    return Settings(university_dir=uni, data_dir=data)

import pytest

@pytest.mark.skip_isolate
def test_seeds_modules_topics_assignments_when_missing(tmp_path: Path):
    uni = tmp_path / "uni"
    (uni / "FA583" / "Week 1 - Tangible non-current assets").mkdir(parents=True)
    (uni / "FA583" / "Module Information").mkdir()
    (uni / "FN585" / "Week 1_ Basic Probability").mkdir(parents=True)
    (uni / "FA565" / "Part 1_ Business Ethics").mkdir(parents=True)

    s = _settings(uni, tmp_path / "data")
    ensure_seeded(s)

    import json
    mods = json.loads(s.modules_path.read_text())
    assert {m["code"] for m in mods} == {"FA583", "FN585", "FA565"}
    topics = json.loads(s.topics_path.read_text())
    assert any(t["title"] == "Tangible non-current assets" for t in topics["FA583"])
    assert s.assignments_path.exists()
    assert s.tasks_path.exists() and json.loads(s.tasks_path.read_text()) == []
    assert s.events_path.exists() and json.loads(s.events_path.read_text()) == []

@pytest.mark.skip_isolate
def test_does_not_overwrite_existing(tmp_path: Path):
    uni = tmp_path / "uni"; uni.mkdir()
    data = tmp_path / "data"; data.mkdir()
    (data / "topics.json").write_text('{"FA583":[{"id":"x","title":"keep","folder":"x","week":1,"confidence":4}]}')
    s = _settings(uni, data)
    ensure_seeded(s)
    import json
    assert json.loads(s.topics_path.read_text())["FA583"][0]["title"] == "keep"