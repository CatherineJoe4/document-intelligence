import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.models.document import Document


# ============================================================
# Configuration
# ============================================================

settings = get_settings()

configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


# ============================================================
# Database
# ============================================================

# Create database tables if they do not already exist.
Base.metadata.create_all(bind=engine)


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "AI-powered document extraction and financial validation API "
        "for invoices and financial statements."
    ),
)


# ============================================================
# Frontend
# ============================================================

templates = Jinja2Templates(
    directory="frontend/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="frontend/static"),
    name="static",
)


# ============================================================
# API Routes
# ============================================================

app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    documents_router,
    prefix="/api/v1",
)


# ============================================================
# Frontend Route
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
        },
    )