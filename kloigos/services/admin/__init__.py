from .events import EventsAdminService
from .playbooks import PlaybooksAdminService
from .servers import ServersAdminService


class AdminService(EventsAdminService, PlaybooksAdminService, ServersAdminService):
    pass
