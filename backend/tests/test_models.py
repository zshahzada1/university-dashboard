from app.models import Topic

def test_topic_defaults():
    t = Topic(id="fa583-t01", title="Inventory", folder="Topic 2", week=2)
    assert t.confidence is None
    assert t.updated_at is None

def test_topic_confidence_bounds():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Topic(id="x", title="x", folder="x", week=1, confidence=6)
    with pytest.raises(ValidationError):
        Topic(id="x", title="x", folder="x", week=1, confidence=0)