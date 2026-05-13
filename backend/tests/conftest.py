import pytest
from pathlib import Path
from importlib import reload

@pytest.fixture(autouse=True)
def _isolated_data(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("skip_isolate"):
        yield
        return
    uni = tmp_path / "uni"; uni.mkdir()
    (uni / "FA583" / "Week 1 - Tangible non-current assets").mkdir(parents=True)
    (uni / "FN585" / "Week 1_ Basic Probability").mkdir(parents=True)
    (uni / "FA565" / "Part 1_ Business Ethics").mkdir(parents=True)
    monkeypatch.setenv("UNI_DIR", str(uni))
    monkeypatch.setenv("UNI_DATA_DIR", str(tmp_path / "data"))
    import app.settings, app.main
    reload(app.settings); reload(app.main)
    yield