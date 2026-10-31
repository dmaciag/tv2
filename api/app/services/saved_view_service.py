from app.arithmetic.expression import normalize
from app.models.saved_view import SavedView
from app.repositories.saved_view_repository import SavedViewRepository
from app.schemas.saved_view import SavedViewWrite


class SavedViewNotFoundError(Exception):
    pass


class SavedViewService:
    def __init__(self, repository: SavedViewRepository):
        self.repository = repository

    def list_views(self) -> list[SavedView]:
        return self.repository.list()

    def save_view(self, data: SavedViewWrite) -> SavedView:
        return self.repository.upsert(
            normalize(data.ticker), data.interval, data.range_from, data.range_to
        )

    def delete_view(self, view_id: int) -> None:
        view = self.repository.get(view_id)
        if view is None:
            raise SavedViewNotFoundError(view_id)
        self.repository.delete(view)
