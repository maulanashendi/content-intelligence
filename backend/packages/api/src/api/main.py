import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pythonjsonlogger import jsonlogger

from api.routes import articles, clusters, health, sources


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _configure_logging()
    yield


app = FastAPI(title="Editor Intelligence API", version="1.0.0", lifespan=_lifespan)
app.include_router(articles.router, prefix="/api/v1")
app.include_router(clusters.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
