from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes import samples, screenings
from app.services.screening import shutdown_pool

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    # Stop the parsing worker processes along with the server.
    shutdown_pool()


app = FastAPI(title="AI Recruiter OS", version="0.2.0", lifespan=lifespan)
app.include_router(screenings.router)
app.include_router(samples.router)


# HEAD too, because uptime monitors often use it.
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def index() -> FileResponse:
    # "no-cache" means "check for a newer version first", so people get
    # updates straight away instead of a stale copy from their browser.
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {"status": "ok"}
