from fastapi import APIRouter, HTTPException, status

from app.schemas.fractal import FractalMatch, FractalRequest
from app.services.fractal_service import FractalService, NoFractalError

router = APIRouter(prefix="/api/fractal", tags=["fractal"])


@router.post("", response_model=FractalMatch)
def find_fractal(data: FractalRequest):
    try:
        return FractalService().find(data.candles)
    except NoFractalError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
