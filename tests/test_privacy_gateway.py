from privacy_gateway.data import ahv_check_digit, generate, iban_check_digits
from privacy_gateway.evaluate import leaked
from privacy_gateway.regex_baseline import redact


def test_check_digits_match_official_examples():
    assert ahv_check_digit("756921707698") == 5  # 756.9217.0769.85
    assert iban_check_digits("00762011623852957") == 93  # CH93 0076 2011 6238 5295 7


def test_every_planted_entity_is_in_its_document():
    for doc in generate(per_kind=3):
        assert all(e["value"] in doc["text"] for e in doc["pii"])
        assert all(not leaked(e, "") for e in doc["pii"])


def test_regex_redacts_structured_data_but_not_bare_names():
    text = "Anna Meier, CH93 0076 2011 6238 5295 7, 079 123 45 67, Rosenweg 3, 6003 Luzern"
    redacted = redact(text)
    assert redacted == "Anna Meier, <IBAN>, <PHONE>, <ADDRESS>"


def test_reformatted_numbers_still_count_as_leaked():
    entity = {"type": "PHONE", "value": "+41 79 123 45 67"}
    assert leaked(entity, "Rückruf an 0791234567")
    assert not leaked(entity, "Rückruf an <PHONE>")
