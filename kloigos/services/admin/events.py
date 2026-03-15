from ...models import LogMsg
from .base import AdminServiceBase


class EventsAdminService(AdminServiceBase):
    def list_events(self) -> list[LogMsg]:
        return self.repo.get_events()
