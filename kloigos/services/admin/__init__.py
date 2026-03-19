from .api_keys import ApiKeysAdminService
from .events import EventsAdminService
from .playbooks import PlaybooksAdminService
from .servers import ServersAdminService
from .settings import SettingsAdminService


class AdminService(
    ApiKeysAdminService,
    EventsAdminService,
    PlaybooksAdminService,
    ServersAdminService,
    SettingsAdminService,
):
    pass
