from backend.app.services.suggestion_service import local_suggestions, suggestions


def test_initial_suggestions_are_three_distinct_items():
    values = local_suggestions("xieyi", "")
    assert len(values) == 3
    assert len(set(values)) == 3


def test_context_changes_the_suggestion_pool():
    values = local_suggestions("xieyi", "雨后的山里有水声")
    assert len(values) == 3
    assert any(any(word in item for word in ("雨", "山", "水", "云雾", "空谷")) for item in values)


def test_excluded_suggestions_do_not_repeat():
    first = local_suggestions("tiaoxin", "我很悲伤")
    second = local_suggestions("tiaoxin", "我很悲伤", first)
    assert not set(first) & set(second)


def test_service_has_local_fallback_without_gpu():
    result = suggestions("tiaoxin", "最近有点疲惫", [])
    assert len(result["suggestions"]) == 3
    assert result["source"] in {"local", "qwen"}
