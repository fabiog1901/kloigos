from .ip_pool import IpPoolAdminService
from .servers import ServersAdminService


class AdminService(
    IpPoolAdminService,
    ServersAdminService,
):
    pass
