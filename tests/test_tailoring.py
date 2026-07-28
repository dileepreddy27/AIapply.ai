from career_autopilot.tailoring import _parse_tailoring_response, TAILOR_MODES


def test_parse_fenced_json():
    raw = '```json\n{"tailored_text": "Hello", "changes": ["a", "b"], "keywords": ["python"]}\n```'
    out = _parse_tailoring_response(raw)
    assert out["tailored_text"] == "Hello"
    assert out["changes"] == ["a", "b"]
    assert out["keywords"] == ["python"]


def test_parse_bare_json():
    out = _parse_tailoring_response('{"tailored_text": "Hi", "changes": [], "keywords": []}')
    assert out["tailored_text"] == "Hi"


def test_parse_plaintext_fallback():
    out = _parse_tailoring_response("no json here, just prose")
    assert out["tailored_text"] == "no json here, just prose"
    assert out["changes"] == []
    assert out["keywords"] == []


def test_parse_missing_keys_are_defaulted():
    out = _parse_tailoring_response('{"tailored_text": "x"}')
    assert out["tailored_text"] == "x"
    assert out["changes"] == []
    assert out["keywords"] == []


def test_modes():
    assert TAILOR_MODES == {"resume", "cover_letter"}
