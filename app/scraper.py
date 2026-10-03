import json
import logging
from typing import Final

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from .config import Settings
from .models import UserDetails

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base error for failures while automating the backoffice."""


class AuthenticationError(ScraperError):
    """The backoffice did not accept the configured credentials."""


class NoResultsError(ScraperError):
    """The account filter completed without matching users."""


class ScraperTimeoutError(ScraperError):
    """The backoffice did not complete an expected operation in time."""


class DetailExtractionError(ScraperError):
    """The detail view did not contain all expected fields."""


class BrowserManager:
    """Owns one Playwright browser and creates an isolated context per search."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @property
    def is_ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> None:
        if self.is_ready:
            return

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.headless,
            )
        except Exception:
            await self._playwright.stop()
            self._playwright = None
            raise RuntimeError(
                "No se pudo iniciar Chromium. Ejecuta "
                "'python -m playwright install chromium'."
            ) from None

    async def new_context(self) -> BrowserContext:
        if self._browser is None:
            raise RuntimeError("El navegador Playwright no está iniciado")

        return await self._browser.new_context(
            ignore_https_errors=self.settings.ignore_https_errors,
        )

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


class BackofficeScraper:
    LOGIN_USERNAME_SELECTOR: Final[str] = "#username"
    LOGIN_PASSWORD_SELECTOR: Final[str] = "#password"
    ACCOUNT_CODE_SELECTOR: Final[str] = "#accountCode"
    ADMIN_MENU_SELECTOR: Final[str] = 'a[href="#"]'
    CLIENTS_LINK_SELECTOR: Final[str] = 'a[href="#/admin/client"]'
    DETAIL_BUTTON_SELECTOR: Final[str] = 'button[title="Ver Detalle"]:visible'
    FULL_NAME_SELECTOR: Final[str] = ".ui-dialog-title:visible"
    DETAIL_SELECTORS: Final[dict[str, str]] = {
        "username": "#idaccount",
        "account_code": "#vaccountCode",
        "contract_number": "#idcontractNumber",
        "contract_date": "#idcontractDate",
    }
    def __init__(self, settings: Settings, browser_manager: BrowserManager) -> None:
        self.settings = settings
        self.browser_manager = browser_manager

    async def search(
        self,
        account_code: str | None = None,
        identity_document: str | None = None,
    ) -> list[UserDetails]:
        context = await self.browser_manager.new_context()
        page = await context.new_page()
        page.set_default_timeout(self.settings.selector_timeout_ms)
        page.set_default_navigation_timeout(self.settings.navigation_timeout_ms)

        try:
            await self._login_and_open_clients(page)
            await self._apply_filter(page, account_code, identity_document)
            return await self._collect_details(
                page,
                account_code,
                identity_document,
            )
        except (ScraperError, AuthenticationError, NoResultsError):
            raise
        except PlaywrightTimeoutError as exc:
            raise ScraperTimeoutError(
                "El backoffice no respondió dentro del tiempo esperado."
            ) from exc
        except PlaywrightError as exc:
            raise ScraperError(
                "Playwright no pudo completar la interacción con el backoffice."
            ) from exc
        finally:
            await context.close()

    async def _login_and_open_clients(self, page: Page) -> None:
        await page.goto(self.settings.target_url, wait_until="commit")
        await self._login_if_present(page)
        await self._wait_for_clients_page(page)

    async def _login_if_present(self, page: Page) -> None:
        if await self._is_visible(page.locator(self.ACCOUNT_CODE_SELECTOR)):
            return

        username = page.locator(self.LOGIN_USERNAME_SELECTOR)
        try:
            await username.wait_for(
                state="visible",
                timeout=self.settings.selector_timeout_ms,
            )
        except PlaywrightTimeoutError:
            return
        await self._login(page)

    async def _login(self, page: Page) -> None:
        username = page.locator(self.LOGIN_USERNAME_SELECTOR)
        password = page.locator(self.LOGIN_PASSWORD_SELECTOR)
        await username.fill(self.settings.username)
        await password.fill(self.settings.password.get_secret_value())

        login_button = page.locator("button[type='submit']").filter(
            has_text="Ingresar"
        ).first
        if await login_button.count() == 0:
            login_button = page.get_by_role("button", name="Ingresar", exact=True)

        await login_button.click()

    async def _wait_for_clients_page(self, page: Page) -> None:
        account_code_input = page.locator(self.ACCOUNT_CODE_SELECTOR)
        # The dashboard does not contain the client filter. Check immediately
        # so a large selector timeout does not delay opening the menu.
        if await self._is_visible(account_code_input):
            return

        await self._open_administration_menu(page)

        clients_link = page.get_by_role(
            "link",
            name="Clientes",
            exact=True,
        ).first
        if await clients_link.count() > 0:
            try:
                # Angular expands the submenu after the parent click.
                await clients_link.wait_for(state="visible", timeout=5_000)
            except PlaywrightTimeoutError:
                clients_link = page.locator(self.CLIENTS_LINK_SELECTOR).first

        if await clients_link.count() > 0 and await clients_link.is_visible():
            # The Angular menu can leave a transparent parent over this link.
            await clients_link.click(force=True)
        else:
            await page.goto(self.settings.client_url, wait_until="commit")

        try:
            await account_code_input.wait_for(
                state="visible",
                timeout=self.settings.selector_timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            if await self._is_visible(page.locator(self.LOGIN_USERNAME_SELECTOR)):
                raise AuthenticationError(
                    "La sesión del backoffice no pudo autenticarse."
                ) from exc

            # A menu click can update the Angular route without rendering the
            # component. Reload the known route before reporting a failure.
            await page.goto(self.settings.client_url, wait_until="commit")
            try:
                await account_code_input.wait_for(
                    state="visible",
                    timeout=self.settings.selector_timeout_ms,
                )
            except PlaywrightTimeoutError as route_exc:
                raise ScraperTimeoutError(
                    "No se pudo abrir la sección Clientes del backoffice."
                ) from route_exc

    async def _open_administration_menu(self, page: Page) -> None:
        administration_link = page.get_by_role(
            "link",
            name="Administración",
            exact=True,
        ).first
        if await administration_link.count() == 0:
            administration_link = page.locator(self.ADMIN_MENU_SELECTOR).filter(
                has_text="Administración"
            ).first

        try:
            await administration_link.wait_for(
                state="visible",
                timeout=self.settings.selector_timeout_ms,
            )
        except PlaywrightTimeoutError:
            logger.debug("No se encontró el menú Administración; se usará la ruta directa")
            return

        # The submenu is collapsed on the dashboard after a fresh login.
        await administration_link.click(force=True)

    async def _apply_filter(
        self,
        page: Page,
        account_code: str | None,
        identity_document: str | None,
    ) -> None:
        # The value came from the public search form, but this is a separate
        # browser page, so it must be written into the backoffice form.
        await page.locator(self.ACCOUNT_CODE_SELECTOR).fill(account_code or "")
        await page.locator("#ci").fill(identity_document or "")
        filter_button = page.locator("button").filter(has_text="Filtrar").first
        if await filter_button.count() == 0:
            filter_button = page.get_by_role("button", name="Filtrar", exact=True)

        try:
            async with page.expect_response(
                lambda response: self._is_matching_client_list_response(
                    response,
                    account_code,
                    identity_document,
                ),
                timeout=self.settings.search_timeout_ms,
            ) as response_info:
                await filter_button.click()
            response = await response_info.value
        except PlaywrightTimeoutError as exc:
            raise ScraperTimeoutError(
                "La petición del filtro no terminó dentro del tiempo esperado."
            ) from exc

        if not response.ok:
            raise ScraperError("El servicio de clientes devolvió un error al filtrar.")
        await self._wait_for_search_completion(page)

    async def _wait_for_search_completion(self, page: Page) -> None:
        detail_buttons = page.locator(self.DETAIL_BUTTON_SELECTOR)
        try:
            await detail_buttons.first.wait_for(
                state="visible",
                timeout=self.settings.selector_timeout_ms,
            )
        except PlaywrightTimeoutError:
            raise NoResultsError("No se encontraron usuarios para ese código de cuenta.")

    @staticmethod
    def _is_matching_client_list_response(
        response,
        account_code: str | None,
        identity_document: str | None = None,
    ) -> bool:
        request = response.request
        if request.method != "POST" or "/cl/client/list" not in request.url:
            return False

        try:
            payload = json.loads(request.post_data or "{}")
        except json.JSONDecodeError:
            return False

        client_dto = payload.get("clientDto", {})
        response_account_code = str(client_dto.get("accountCode") or "").strip()
        response_identity_document = str(client_dto.get("ci") or "").strip()
        if account_code and response_account_code != account_code:
            return False
        if identity_document and response_identity_document != identity_document:
            return False
        return bool(account_code or identity_document)

    async def _collect_details(
        self,
        page: Page,
        account_code: str | None,
        identity_document: str | None,
    ) -> list[UserDetails]:
        detail_buttons = page.locator(self.DETAIL_BUTTON_SELECTOR)
        expected_count = await detail_buttons.count()
        if expected_count == 0:
            raise NoResultsError("No se encontraron usuarios para ese código de cuenta.")

        results: list[UserDetails] = []
        for index in range(expected_count):
            detail_buttons = page.locator(self.DETAIL_BUTTON_SELECTOR)
            if await detail_buttons.count() <= index:
                await self._restore_results_page(
                    page,
                    account_code,
                    identity_document,
                    expected_count,
                )
                detail_buttons = page.locator(self.DETAIL_BUTTON_SELECTOR)
            if await detail_buttons.count() <= index:
                raise DetailExtractionError(
                    "El resultado dejó de estar disponible mientras se leía el detalle."
                )

            try:
                await detail_buttons.nth(index).click()
                await self._wait_for_detail_fields(page)
                results.append(await self._read_detail(page))
            except PlaywrightTimeoutError as exc:
                raise DetailExtractionError(
                    "El detalle del usuario no cargó todos los campos esperados."
                ) from exc

            if index < expected_count - 1:
                await self._restore_results_page(
                    page,
                    account_code,
                    identity_document,
                    expected_count,
                )

        return results

    async def _wait_for_detail_fields(self, page: Page) -> None:
        await page.locator(self.FULL_NAME_SELECTOR).first.wait_for(
            state="visible",
            timeout=self.settings.selector_timeout_ms,
        )
        for selector in self.DETAIL_SELECTORS.values():
            await page.locator(selector).wait_for(
                state="visible",
                timeout=self.settings.selector_timeout_ms,
            )

    async def _read_detail(self, page: Page) -> UserDetails:
        values: dict[str, str] = {
            "full_name": (
                await page.locator(self.FULL_NAME_SELECTOR).first.text_content() or ""
            ).strip()
        }
        for field_name, selector in self.DETAIL_SELECTORS.items():
            values[field_name] = (await page.locator(selector).input_value()).strip()
        return UserDetails(**values)

    async def _restore_results_page(
        self,
        page: Page,
        account_code: str | None,
        identity_document: str | None,
        expected_count: int,
    ) -> None:
        for selector in (
            'button[title="Cerrar"]',
            'button[aria-label="Close"]',
            ".ui-dialog-titlebar-close",
        ):
            close_buttons = page.locator(selector)
            for index in range(await close_buttons.count()):
                close_button = close_buttons.nth(index)
                if await close_button.is_visible():
                    await close_button.click()
                    if await self._has_expected_results(page, expected_count):
                        return

        if await self._has_expected_results(page, expected_count):
            return

        try:
            await page.go_back(
                wait_until="commit",
                timeout=self.settings.navigation_timeout_ms,
            )
        except PlaywrightTimeoutError:
            logger.debug("No fue posible volver con history.back(); se recargará Clientes")

        if await self._has_expected_results(page, expected_count):
            return

        await page.goto(self.settings.client_url, wait_until="commit")
        await self._login_if_present(page)
        await self._wait_for_clients_page(page)
        await self._apply_filter(page, account_code, identity_document)

    async def _has_expected_results(self, page: Page, expected_count: int) -> bool:
        if not await self._is_visible(page.locator(self.ACCOUNT_CODE_SELECTOR)):
            return False
        return await page.locator(self.DETAIL_BUTTON_SELECTOR).count() >= expected_count

    @staticmethod
    async def _is_visible(locator) -> bool:
        try:
            return await locator.is_visible()
        except Exception:
            return False
