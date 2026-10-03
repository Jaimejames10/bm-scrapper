import pytest
from pydantic import ValidationError

from app.models import SearchRequest, UserDetails


def test_search_request_strips_surrounding_whitespace() -> None:
    request = SearchRequest(account_code="  AC001  ")

    assert request.account_code == "AC001"


def test_search_request_rejects_blank_value() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(account_code="   ")


def test_search_request_accepts_identity_document_without_account_code() -> None:
    request = SearchRequest(identity_document=" 1234567 ")

    assert request.account_code is None
    assert request.identity_document == "1234567"


def test_search_request_converts_numeric_identity_document_to_string() -> None:
    request = SearchRequest(identity_document=1234567)

    assert request.identity_document == "1234567"


def test_search_request_accepts_both_filters() -> None:
    request = SearchRequest(account_code="AC001", identity_document="1234567")

    assert request.account_code == "AC001"
    assert request.identity_document == "1234567"


def test_search_request_rejects_more_than_thirty_characters() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(account_code="A" * 31)


def test_user_details_contains_the_four_expected_fields() -> None:
    details = UserDetails(
        username="user01",
        account_code="AC001",
        contract_number="CTR001",
        contract_date="2026-01-15",
    )

    assert details.model_dump() == {
        "username": "user01",
        "account_code": "AC001",
        "contract_number": "CTR001",
        "contract_date": "2026-01-15",
        "full_name": "",
    }
