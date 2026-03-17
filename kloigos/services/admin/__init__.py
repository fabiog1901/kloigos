from .api_keys import ApiKeysAdminService
from .events import EventsAdminService
from .playbooks import PlaybooksAdminService
from .servers import ServersAdminService


class AdminService(
    ApiKeysAdminService,
    EventsAdminService,
    PlaybooksAdminService,
    ServersAdminService,
):
    pass
