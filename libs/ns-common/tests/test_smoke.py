from ns_common import TOPICS, __version__


def test_smoke():
    assert __version__ == "0.1.0"
    assert "alarms.raw" in TOPICS
    assert len(TOPICS) == 4
