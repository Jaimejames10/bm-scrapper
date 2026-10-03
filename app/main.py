import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import get_settings
from .models import SearchRequest, SearchResponse
from .scraper import (
    AuthenticationError,
    BackofficeScraper,
    BrowserManager,
    DetailExtractionError,
    NoResultsError,
    ScraperError,
    ScraperTimeoutError,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Faltan SCRAPER_USERNAME y/o SCRAPER_PASSWORD. "
            "Configúralos en el archivo .env."
        ) from exc

    browser_manager = BrowserManager(settings)
    await browser_manager.start()
    app.state.settings = settings
    app.state.browser_manager = browser_manager
    app.state.scraper = BackofficeScraper(settings, browser_manager)
    try:
        yield
    finally:
        await browser_manager.stop()


app = FastAPI(
    title="Buscador de usuarios",
    description="Consulta usuarios del backoffice mediante automatización Playwright.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def get_scraper(request: Request) -> BackofficeScraper:
    scraper = getattr(request.app.state, "scraper", None)
    if scraper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El motor de búsqueda todavía no está disponible.",
        )
    return scraper


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/health")
async def health(request: Request):
    browser_manager: BrowserManager | None = getattr(
        request.app.state,
        "browser_manager",
        None,
    )
    return {
        "status": "ok" if browser_manager and browser_manager.is_ready else "starting",
        "browser_ready": bool(browser_manager and browser_manager.is_ready),
    }


@app.post("/api/search", response_model=SearchResponse)
async def search_users(
    payload: SearchRequest,
    scraper: BackofficeScraper = Depends(get_scraper),
) -> SearchResponse:
    try:
        results = await scraper.search(
            payload.account_code,
            payload.identity_document,
        )
    except NoResultsError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AuthenticationError as exc:
        logger.error("El backoffice rechazó la autenticación configurada")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible iniciar sesión en el backoffice.",
        ) from exc
    except (ScraperTimeoutError, DetailExtractionError) as exc:
        logger.warning("Fallo controlado del scraper: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except ScraperError as exc:
        logger.exception("Error controlado del scraper")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El backoffice no pudo completar la búsqueda.",
        ) from exc

    query = " / ".join(
        value for value in (payload.account_code, payload.identity_document) if value
    )
    return SearchResponse(query=query, results=results)
