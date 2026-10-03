import asyncio

import httpx

from app.main import app
from app.models import UserDetails


class StubScraper:
    async def search(
        self,
        account_code: str | None = None,
        identity_document: str | None = None,
    ) -> list[UserDetails]:
        query = account_code or identity_document or ""
        return [
            UserDetails(
                username="user01",
                account_code=query,
                contract_number="CTR001",
                contract_date="2026-01-15",
                full_name="MARIA LIZ ARANDIA JIMENEZ",
            )
        ]


async def _post_search(payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/search", json=payload)


def test_search_endpoint_returns_user_details() -> None:
    app.state.scraper = StubScraper()
    response = asyncio.run(_post_search({"account_code": " AC001 "}))

    assert response.status_code == 200
    assert response.json() == {
        "query": "AC001",
        "results": [
            {
                "username": "user01",
                "account_code": "AC001",
                "contract_number": "CTR001",
                "contract_date": "2026-01-15",
                "full_name": "MARIA LIZ ARANDIA JIMENEZ",
            }
        ],
    }


def test_search_endpoint_validates_the_account_code() -> None:
    app.state.scraper = StubScraper()
    response = asyncio.run(_post_search({"account_code": "   "}))

    assert response.status_code == 422
