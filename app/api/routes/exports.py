from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.screening import ScreeningResult
from app.services.export import to_csv

router = APIRouter(prefix="/api", tags=["exports"])

# A screening returns at most 200 candidates. Anything much bigger isn't one of our results.
MAX_EXPORT_ROWS = 250


@router.post("/exports/csv")
def export_csv(result: ScreeningResult) -> Response:
    """Turn a screening result back into a CSV file. Nothing is stored: the result is sent in and the file comes back."""
    if len(result.candidates) > MAX_EXPORT_ROWS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Export at most {MAX_EXPORT_ROWS} candidates at a time.")
    return Response(
        content=to_csv(result).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shortlist.csv"'},
    )
