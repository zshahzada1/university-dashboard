from app.services.folder_scan import parse_topic_folder

def test_topic_n_week_n_dash_title():
    r = parse_topic_folder("Topic 2 _ Week 2 - Inventory")
    assert r == {"week": 2, "title": "Inventory"}

def test_week_n_title():
    r = parse_topic_folder("Week 4 - AR model")
    assert r == {"week": 4, "title": "AR model"}

def test_week_n_colon_title():
    r = parse_topic_folder("Week 1_ Basic Probability")
    assert r == {"week": 1, "title": "Basic Probability"}

def test_part_n_underscore_title():
    r = parse_topic_folder("Part 1_ Business Ethics")
    assert r == {"week": None, "title": "Business Ethics"}

def test_long_name_no_week():
    r = parse_topic_folder("Markovitz and Diversification, CAPM")
    assert r is None  # not a topic folder

def test_module_information_skipped():
    assert parse_topic_folder("Module Information") is None
    assert parse_topic_folder("Study Skills") is None
    assert parse_topic_folder("Assessment Submission Points") is None

def test_scan_module_topics(tmp_path):
    (tmp_path / "Week 1 - Probability").mkdir()
    (tmp_path / "Topic 2 _ Week 2 - Inventory").mkdir()
    (tmp_path / "Module Information").mkdir()
    from app.services.folder_scan import scan_module_topics
    topics = scan_module_topics(tmp_path)
    titles = {t["title"] for t in topics}
    assert titles == {"Probability", "Inventory"}