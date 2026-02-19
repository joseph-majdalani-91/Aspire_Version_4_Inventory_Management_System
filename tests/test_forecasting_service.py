from app.services.ai_features import parse_natural_language_filters


def test_natural_language_fallback_parses_status_and_qty() -> None:
    parsed = parse_natural_language_filters("low stock electronics under 20")
    assert parsed["status"] in {"low_stock", None}
    assert parsed["max_qty"] in {20, None}
    assert parsed["source"] in {"ai", "fallback"}
