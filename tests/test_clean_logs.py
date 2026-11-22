from clean_logs import validate, transform


def good_event():
    """A correct record that every test starts from."""
    return {
        "event_id": "e1",
        "user_id": "U1",
        "event_type": "purchase",
        "product_id": "P101",
        "price": 499.5,
        "timestamp": "2026-11-21T10:30:00",
    }


def test_good_event_passes():
    assert validate(good_event()) is None


def test_missing_field_is_rejected():
    event = good_event()
    del event["user_id"]
    assert validate(event) == "missing_field:user_id"


def test_empty_field_is_rejected():
    event = good_event()
    event["product_id"] = ""
    assert validate(event) == "missing_field:product_id"


def test_negative_price_is_rejected():
    event = good_event()
    event["price"] = -5
    assert validate(event) == "negative_price"


def test_price_as_text_is_rejected():
    event = good_event()
    event["price"] = "free"
    assert validate(event) == "price_not_a_number"


def test_bad_timestamp_is_rejected():
    event = good_event()
    event["timestamp"] = "not-a-date"
    assert validate(event) == "bad_timestamp"


def test_unknown_event_type_is_rejected():
    event = good_event()
    event["event_type"] = "refund"
    assert validate(event) == "invalid_event_type"


def test_non_object_is_rejected():
    assert validate("hello") == "not_a_json_object"


def test_transform_trims_spaces_and_adds_date():
    event = good_event()
    event["user_id"] = "  U1  "
    result = transform(event)
    assert result["user_id"] == "U1"
    assert result["date"] == "2026-11-21"


def test_transform_rounds_price():
    event = good_event()
    event["price"] = 10.126
    assert transform(event)["price"] == 10.13