"""Saved sessions. Local only: there are no accounts, so no other machine may read or change them."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.schemas.screening import ScreeningResult
from app.schemas.workspace import SeenElsewhere, SeenRequest, Session, SessionIn, SessionSummary, SessionUpdate, WorkspaceInfo
from app.services.clarify import ClarificationError, apply
from app.services.workspace import NotFound, TooLarge, Workspace

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "workspace.db"
LOCAL_CLIENTS = frozenset({"127.0.0.1", "::1"})
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})
WRITE_HEADER = "x-workspace"
OFF_NOTE = "Saving sessions is switched off on this copy. It works when the app runs on your own computer."

_store: Workspace | None = None


def workspace_path() -> Path:
    return Path(os.environ.get("WORKSPACE_DB") or DEFAULT_PATH)


def enabled() -> bool:
    return os.environ.get("RECRUITER_WORKSPACE", "on").lower() not in ("off", "0", "false", "no")


def get_store() -> Workspace:
    global _store
    path = workspace_path()
    if _store is None or _store.path != path:
        _store = Workspace(path)
    return _store


def _hostname(header: str) -> str:
    return header.split("]")[0] + "]" if header.startswith("[") else header.rsplit(":", 1)[0]


def local_only(request: Request) -> None:
    """Refuse anything that isn't this computer talking to itself.

    The client address must be the loopback address, the Host header must be a local name (which
    stops a web page reaching in through DNS rebinding), and changes need a header that browsers
    won't add to a cross-site request.
    """
    if not enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=OFF_NOTE)
    client = request.client.host if request.client else ""
    if client not in LOCAL_CLIENTS or _hostname(request.headers.get("host", "")) not in LOCAL_HOSTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Saved sessions can only be used from the computer they are on.")
    if request.method not in ("GET", "HEAD") and request.headers.get(WRITE_HEADER) != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Refused: missing the page's request header.")


info_router = APIRouter(prefix="/api/workspace", tags=["workspace"])
router = APIRouter(prefix="/api/workspace", tags=["workspace"], dependencies=[Depends(local_only)])


@info_router.get("", response_model=WorkspaceInfo)
def workspace_info(request: Request) -> WorkspaceInfo:
    """Whether sessions can be saved here, and where. Safe to call from anywhere: it reveals no session data."""
    try:
        local_only(request)
    except HTTPException as error:
        return WorkspaceInfo(enabled=False, location=None, note=str(error.detail))
    return WorkspaceInfo(enabled=True, location=str(workspace_path()),
                         note="Sessions are saved in a file on this computer. Resume files themselves are not kept.")


def _found(call, *args):
    try:
        return call(*args)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That session no longer exists.") from None
    except TooLarge as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from None


def _check(result, clarifications) -> None:
    """A session is only saved if its answers actually apply to its result."""
    try:
        apply(result, clarifications)
    except ClarificationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[dict]:
    return get_store().list()


@router.post("/sessions", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionIn) -> dict:
    _check(body.result, body.clarifications)
    clarifications = {name: entry.model_dump() for name, entry in body.clarifications.items()}
    return _found(get_store().create, body.name, body.job_description, body.form, body.result, clarifications, body.submission)


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: str) -> dict:
    return _found(get_store().get, session_id)


@router.patch("/sessions/{session_id}", response_model=Session)
def update_session(session_id: str, body: SessionUpdate) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if body.clarifications is not None:
        current = _found(get_store().get, session_id)
        _check(ScreeningResult(**current["result"]), body.clarifications)
        changes["clarifications"] = {name: entry.model_dump() for name, entry in body.clarifications.items()}
    return _found(get_store().update, session_id, changes)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    _found(get_store().delete, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/seen", response_model=list[SeenElsewhere])
def seen_elsewhere(body: SeenRequest) -> list[dict]:
    """Which candidates in this result are also in another saved session (same phone number or email)."""
    return get_store().seen_elsewhere(body.result, body.exclude_session)
