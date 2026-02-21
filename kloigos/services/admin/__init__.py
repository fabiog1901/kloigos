from .playbooks import PlaybooksAdminService
from .servers import ServersAdminService


class AdminService(PlaybooksAdminService, ServersAdminService):
    pass
