import json
from types import SimpleNamespace

from app.scraper import BackofficeScraper


def make_response(account_code: str, identity_document: str | None = None) -> SimpleNamespace:
    request = SimpleNamespace(
        method="POST",
        url="https://ws-apiv2.comarapa.coop/ws-client/cl/client/list",
        post_data=json.dumps(
            {
                "clientDto": {
                    "accountCode": account_code,
                    "ci": identity_document or "",
                }
            }
        ),
    )
    return SimpleNamespace(request=request)


def test_matches_the_response_for_the_requested_account_code() -> None:
    response = make_response("AC001")

    assert BackofficeScraper._is_matching_client_list_response(response, "AC001")


def test_ignores_the_initial_unfiltered_client_list_response() -> None:
    response = make_response("")

    assert not BackofficeScraper._is_matching_client_list_response(response, "AC001")


def test_matches_the_response_for_identity_document() -> None:
    response = make_response("", "1234567")

    assert BackofficeScraper._is_matching_client_list_response(
        response,
        None,
        "1234567",
    )


def test_matches_the_response_for_both_filters() -> None:
    response = make_response("AC001", "1234567")

    assert BackofficeScraper._is_matching_client_list_response(
        response,
        "AC001",
        "1234567",
    )
