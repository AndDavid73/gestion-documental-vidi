from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routes import documentos


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara la base de datos al iniciar la aplicacion."""

    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Prototipo local para registro, almacenamiento y validacion documental.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
app.include_router(documentos.router)
