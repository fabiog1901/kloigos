from ...models import Event, LogMsg, Playbook
from ...util import request_id_ctx
from .base import AdminServiceBase


class PlaybooksAdminService(AdminServiceBase):
    def update_playbooks(self, playbook: Playbook, b64: str) -> None:
        self.repo.playbook_update_content(playbook, b64)

        self.repo.log_event(
            LogMsg(
                user_id="fabio",
                action=Event.UPDATE_PLAYBOOK,
                details={"playbook": playbook},
                request_id=request_id_ctx.get(),
            )
        )

    def get_playbook(self, playbook: Playbook) -> str:
        return self.repo.playbook_get_content(playbook)
