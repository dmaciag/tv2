from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_state_db
from app.repositories.saved_view_repository import SavedViewRepository
from app.schemas.saved_view import SavedViewRead, SavedViewWrite
from app.services.saved_view_service import SavedViewNotFoundError, SavedViewService

router = APIRouter(prefix="/api/saved-views", tags=["saved views"])


def get_saved_view_service(db: Session = Depends(get_state_db)) -> SavedViewService:
    return SavedViewService(SavedViewRepository(db))


@router.get("", response_model=list[SavedViewRead])
def list_saved_views(service: SavedViewService = Depends(get_saved_view_service)):
    return service.list_views()


@router.put("", response_model=SavedViewRead)
def save_view(data: SavedViewWrite, service: SavedViewService = Depends(get_saved_view_service)):
    return service.save_view(data)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_view(view_id: int, service: SavedViewService = Depends(get_saved_view_service)):
    try:
        service.delete_view(view_id)
    except SavedViewNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved view not found")
